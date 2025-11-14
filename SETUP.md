# Setup Guide

## Secret Configuration

### For the Quiz Evaluation

1. **Register for the quiz** via the Google Form provided by your instructor
2. **You will receive a secret string** during registration
3. **Set this secret** as the `QUIZ_SECRET` environment variable:
   ```bash
   export QUIZ_SECRET="the_secret_from_google_form"
   ```
4. **Use the same secret** when filling out the Google Form's "Secret string" field

### For Local Testing

For local development and testing, you can use any secret string. Here's a quick way to generate a test secret:

```bash
# Generate a random test secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Then set it:
```bash
export QUIZ_SECRET="your_generated_test_secret"
export QUIZ_EMAIL="test@example.com"
```

### Important Notes

- **The secret you provide in the Google Form must match the `QUIZ_SECRET` environment variable** on your deployed server
- The quiz system will send requests with the secret you provided in the form
- Your server validates this secret and returns 403 if it doesn't match
- **For production deployment**, make sure to set the actual secret from the Google Form

## Environment Variables

Create a `.env` file or export these variables:

```bash
QUIZ_EMAIL=your@email.com          # Your registered email
QUIZ_SECRET=your_secret_string     # Secret from Google Form (for production) or test secret (for local)
SOLVE_TIMEOUT_SECS=170             # Timeout in seconds (must be < 180)
PORT=8000                          # Server port (optional, defaults to 8000)
```

## Testing with Demo Endpoint

You can test your implementation with the demo endpoint:

```bash
curl -X POST http://localhost:8000/api/quiz \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "your@email.com",
    "secret": "your_secret_string",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

Make sure the `secret` in the request matches your `QUIZ_SECRET` environment variable.

