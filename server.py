# server.py
import asyncio, json, os, re, time
from typing import Any, Dict, Optional

import httpx
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, ValidationError
from playwright.async_api import async_playwright

EMAIL = os.getenv("QUIZ_EMAIL", "your@example.com")
SECRET = os.getenv("QUIZ_SECRET", "change_me")
SOLVE_TIMEOUT_SECS = int(os.getenv("SOLVE_TIMEOUT_SECS", "170"))  # < 180s for buffer

class QuizPayload(BaseModel):
    email: str
    secret: str
    url: str

app = FastAPI(title="LLM Analysis Quiz Solver")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "llm-analysis-quiz-solver"}

@app.post("/api/quiz")
async def receive_quiz(request: Request, bg: BackgroundTasks):
    try:
        body = await request.json()
        payload = QuizPayload(**body)
    except (json.JSONDecodeError, ValidationError):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if payload.secret != SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    # Fire-and-forget background solving; immediate 200 to grader
    bg.add_task(solve_sequence, payload.dict())
    return {"status": "accepted"}

async def solve_sequence(payload: Dict[str, Any]):
    start = time.time()
    next_url = payload["url"]
    while next_url and (time.time() - start) < SOLVE_TIMEOUT_SECS:
        try:
            answer, submit_url = await solve_single(next_url)
            submit_body = {
                "email": payload["email"],
                "secret": payload["secret"],
                "url": next_url,
                "answer": answer,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(submit_url, json=submit_body)
                r.raise_for_status()
                resp = r.json()
            # proceed if server gives a new URL
            next_url = resp.get("url")
        except Exception as e:
            # One retry per URL within time budget
            if (time.time() - start) >= SOLVE_TIMEOUT_SECS:
                break
            await asyncio.sleep(1.0)
            try:
                answer, submit_url = await solve_single(next_url)
                submit_body = {
                    "email": payload["email"],
                    "secret": payload["secret"],
                    "url": next_url,
                    "answer": answer,
                }
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(submit_url, json=submit_body)
                    r.raise_for_status()
                    resp = r.json()
                next_url = resp.get("url")
            except Exception:
                break

async def solve_single(url: str):
    # Render with Playwright to execute page JS
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        # Best effort: wait for network quiescence or content body
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        html = await page.content()
        await browser.close()

    text, submit_url = parse_instructions(html)
    answer = await compute_answer(text, base_url=url)
    if not submit_url:
        raise RuntimeError("Submit URL not found on quiz page")
    return answer, submit_url

# --- Parsing helpers ---
SUBMIT_PATTERN = re.compile(r"post\s+your\s+answer\s+to\s+(https?://\S+)", re.I)

def parse_instructions(html: str):
    soup = BeautifulSoup(html, "lxml")
    body_text = soup.get_text("\n", strip=True)
    # Find submit URL
    m = SUBMIT_PATTERN.search(body_text)
    submit_url = m.group(1) if m else None
    return body_text, submit_url

# --- Compute answer ---
async def compute_answer(page_text: str, base_url: str) -> Any:
    # 1) direct numeric/boolean/string prompts
    m_simple = re.search(r"answer\s*:\s*(\d+)", page_text, re.I)
    if m_simple:
        return int(m_simple.group(1))

    # 2) Look for a downloadable link
    link = find_first_download_link(page_text)
    if link:
        return await compute_from_download(link, page_text)

    # 3) As a fallback, try HTML tables on the same page (if provided inline)
    # (Usually pages link out; keeping this minimal.)
    return generic_extract_number(page_text)

DL_LINK = re.compile(r"https?://\S+\.(csv|tsv|json|xlsx|parquet|pq|pdf)")

def find_first_download_link(text: str) -> Optional[str]:
    m = DL_LINK.search(text)
    return m.group(0) if m else None

async def compute_from_download(url: str, page_text: str) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        content = r.content

    if url.endswith((".csv", "tsv")):
        sep = "," if url.endswith(".csv") else "\t"
        df = pd.read_csv(pd.io.common.BytesIO(content), sep=sep)
        return compute_from_dataframe(df, page_text)
    if url.endswith(".json"):
        data = json.loads(content)
        return compute_from_json(data, page_text)
    if url.endswith(".xlsx"):
        df = pd.read_excel(pd.io.common.BytesIO(content))
        return compute_from_dataframe(df, page_text)
    if url.endswith((".parquet", ".pq")):
        df = pd.read_parquet(pd.io.common.BytesIO(content))
        return compute_from_dataframe(df, page_text)
    if url.endswith(".pdf"):
        return compute_from_pdf(content, page_text)

    raise RuntimeError("Unsupported format")

# --- DataFrame tasks (sum/mean/filter/page hints) ---
COL_NAME_PATTERN = re.compile(r"\b(?:column|field)\s*\"([A-Za-z0-9_ \-/]+)\"", re.I)
OP_SUM = re.compile(r"\bsum\b", re.I)
OP_MEAN = re.compile(r"\bmean|average|avg\b", re.I)

PAGE_HINT = re.compile(r"page\s*(\d+)", re.I)

def compute_from_dataframe(df: pd.DataFrame, page_text: str) -> Any:
    # Pick column
    col = None
    m = COL_NAME_PATTERN.search(page_text)
    if m:
        candidate = m.group(1).strip()
        for c in df.columns:
            if c.strip().lower() == candidate.lower():
                col = c
                break
    # Default heuristic: first numeric column
    if col is None:
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not num_cols:
            raise RuntimeError("No numeric columns found")
        col = num_cols[0]

    if OP_SUM.search(page_text):
        return float(pd.to_numeric(df[col], errors="coerce").sum())
    if OP_MEAN.search(page_text):
        return float(pd.to_numeric(df[col], errors="coerce").mean())

    # Fallback: count
    return int(len(df))

# --- JSON tasks ---

def compute_from_json(data: Any, page_text: str) -> Any:
    # Look for a key named in quotes after the word value/column/field
    m = COL_NAME_PATTERN.search(page_text)
    if m and isinstance(data, (list, dict)):
        key = m.group(1).strip()
        if isinstance(data, list) and data and isinstance(data[0], dict) and key in data[0]:
            series = pd.Series([row.get(key) for row in data])
            if OP_SUM.search(page_text):
                return float(pd.to_numeric(series, errors="coerce").sum())
            if OP_MEAN.search(page_text):
                return float(pd.to_numeric(series, errors="coerce").mean())
    # Fallback: length if list
    if isinstance(data, list):
        return int(len(data))
    return data

# --- PDF tasks ---

def compute_from_pdf(content: bytes, page_text: str) -> Any:
    page_no = 0
    m = PAGE_HINT.search(page_text)
    if m:
        # Convert to 0-index
        page_no = max(0, int(m.group(1)) - 1)
    with pdfplumber.open(pd.io.common.BytesIO(content)) as pdf:
        page_no = min(page_no, len(pdf.pages) - 1)
        page = pdf.pages[page_no]
        tables = page.extract_tables()
        if not tables:
            text = page.extract_text() or ""
            return generic_extract_number(text)
        # Use largest table by cell count
        tbl = max(tables, key=lambda t: len(t) * len(t[0]) if t and t[0] else 0)
        df = pd.DataFrame(tbl[1:], columns=tbl[0])
        return compute_from_dataframe(df, page_text)

# --- Generic numeric fallback ---
GENERIC_NUM = re.compile(r"-?\d+(?:\.\d+)?")

def generic_extract_number(text: str) -> Any:
    nums = [float(x) for x in GENERIC_NUM.findall(text)]
    if not nums:
        raise RuntimeError("No numbers found to compute")
    return nums[0]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

