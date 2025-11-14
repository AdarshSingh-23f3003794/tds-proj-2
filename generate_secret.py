#!/usr/bin/env python3
"""
Generate a test secret for local development.
For the actual quiz, use the secret you provide in the Google Form.
"""
import secrets

if __name__ == "__main__":
    secret = secrets.token_urlsafe(32)
    print(f"Generated test secret: {secret}")
    print(f"\nSet it as an environment variable:")
    print(f'export QUIZ_SECRET="{secret}"')
    print(f"\nOr add it to your .env file:")
    print(f'QUIZ_SECRET={secret}')

