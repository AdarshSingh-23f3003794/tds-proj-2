# LLM Analysis Quiz Solver

A production-ready FastAPI service that automatically solves LLM analysis quiz challenges by:
- Rendering JavaScript-heavy pages with Playwright
- Extracting questions and data files (CSV/JSON/Excel/Parquet/PDF)
- Computing answers using pandas and data analysis utilities
- Submitting answers within a 3-minute time window

## Architecture

- **FastAPI** HTTP server exposes `POST /api/quiz`
- Returns **200** on success, **400** for invalid JSON, **403** for invalid secret
- **Background task** solves the quiz sequence:
  1. Visits quiz URL with Playwright (headless Chromium)
  2. Extracts instructions and submission endpoint
  3. Downloads and parses data files
  4. Computes answers using pandas/pdfplumber
  5. Submits answers and follows redirects (within 3-minute window)

## Quick Start

### Local Development

**Note:** This project requires **Python 3.11** (as specified in the Dockerfile). Python 3.14+ is not yet supported by some dependencies.

1. **Set up virtual environment:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

3. **Set environment variables:**
```bash
export QUIZ_EMAIL="your@email"
export QUIZ_SECRET="your_secret"
export SOLVE_TIMEOUT_SECS=170
```

**About the Secret:**
- **For Quiz Evaluation:** The `QUIZ_SECRET` is a secret string you provide when registering for the quiz via Google Form. The same secret must be:
  1. Set as the `QUIZ_SECRET` environment variable on your deployed server
  2. Provided in the Google Form's "Secret string" field
  3. The quiz system will send this secret in requests, and your server validates it (returns 403 if it doesn't match)

- **For Local Testing:** You can use any test secret. Generate one with:
  ```bash
  python generate_secret.py
  ```
  Or manually:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

See `SETUP.md` for detailed setup instructions.

Or create a `.env` file (see `.env.example`).

4. **Run the server:**
```bash
python server.py
```

Server runs at `http://localhost:8000` → endpoint `POST /api/quiz`

### Docker

1. **Build the image:**
```bash
docker build -t llm-quiz-solver .
```

2. **Run the container:**
```bash
docker run -p 8000:8000 \
  -e QUIZ_EMAIL="your@email" \
  -e QUIZ_SECRET="your_secret" \
  -e SOLVE_TIMEOUT_SECS=170 \
  llm-quiz-solver
```

## Testing

### Test against demo orchestrator:
```bash
curl -X POST http://localhost:8000/api/quiz \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "your@email",
    "secret": "your_secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

Watch server logs—the solver should follow the sequence and submit within time.

## API Endpoint

### `POST /api/quiz`

**Request Body:**
```json
{
  "email": "your@email",
  "secret": "your_secret",
  "url": "https://quiz-url-here"
}
```

- `email`: Your registered email address
- `secret`: The secret string provided during quiz registration (must match `QUIZ_SECRET` environment variable)
- `url`: The quiz URL to solve

**Response:**
```json
{
  "status": "accepted"
}
```

The server returns immediately (200) and processes the quiz in the background.

**Error Responses:**
- `400`: Invalid JSON payload
- `403`: Invalid secret (secret doesn't match `QUIZ_SECRET` environment variable)

## Features

- ✅ **JavaScript rendering** with Playwright
- ✅ **Multiple data formats**: CSV, TSV, JSON, XLSX, Parquet, PDF
- ✅ **Smart parsing**: Extracts column names, operations (sum/mean), page hints
- ✅ **Time-bounded**: Stops within 3-minute window
- ✅ **Retry logic**: One retry per URL within time budget
- ✅ **No hardcoded answers**: Always parses from page content

## Supported Operations

- **Sum**: Finds numeric columns and sums values
- **Mean/Average**: Calculates mean of numeric columns
- **Count**: Returns row count as fallback
- **Page extraction**: Extracts tables from specific PDF pages
- **Column matching**: Case-insensitive column name matching

## Deployment Checklist

Before deployment:

- ✅ Public HTTPS endpoint reachable from the internet
- ✅ Environment variables set (email, secret)
- ✅ Smoke test with demo URL
- ✅ Repository public + MIT license
- ✅ Container memory ≥512MB
- ✅ Playwright Chromium cache warmed

## Project Structure

```
tds-project2/
├── server.py                          # Main FastAPI application
├── requirements.txt                   # Python dependencies
├── Dockerfile                        # Container definition
├── README.md                         # This file
├── SETUP.md                          # Detailed setup instructions
├── GOOGLE_FORM_SUBMISSION.md         # Google Form submission details & prompts
├── PROJECT_STATUS.md                 # Project completion status
├── generate_secret.py                # Helper script to generate test secrets
├── .env.example                      # Environment variable template
├── LICENSE                           # MIT License
└── llm_analysis_quiz_implementation_plan_reference_code.md  # Implementation plan
```

## Google Form Submission

See `GOOGLE_FORM_SUBMISSION.md` for:
- System prompt (≤100 chars) to resist revealing code words
- User prompt (≤100 chars) to override system prompts
- Complete submission checklist

## Project Status

See `PROJECT_STATUS.md` for:
- Implementation completion status
- Deployment checklist
- Next steps

## License

MIT License - see LICENSE file for details.

