"""Turns text into vectors using the Gemini embedding API (with retry)."""
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
DIM = int(os.getenv("EMBEDDING_DIM", "768"))
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:embedContent"


def embed_text(text: str, task_type: str, retries: int = 5) -> list[float]:
    """task_type is RETRIEVAL_DOCUMENT for policy chunks, RETRIEVAL_QUERY for user questions."""
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not set in .env")

    body = {
        "content": {"parts": [{"text": text}]},
        "taskType": task_type,
        "outputDimensionality": DIM,
    }
    for attempt in range(retries):
        resp = httpx.post(URL, headers={"x-goog-api-key": key}, json=body, timeout=30)
        if resp.status_code == 200:
            return resp.json()["embedding"]["values"]
        if resp.status_code in (429, 500, 503):  # busy or rate limited: wait and retry
            wait = 2 ** attempt
            print(f"  Gemini returned {resp.status_code}, retrying in {wait}s...")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Embedding failed: {resp.status_code} {resp.text[:200]}")
    raise RuntimeError("Embedding failed after all retries")