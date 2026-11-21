"""Reads policy markdown files, splits them by '## Section', embeds each chunk, stores in pgvector."""
import os
import re
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from src.rag.embeddings import embed_text

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
POLICIES_DIR = Path(__file__).resolve().parents[2] / "data" / "policies"


def chunk_markdown_by_section(file_path: Path) -> list[dict]:
    """Split a policy file at every '## ' heading so each chunk keeps its section title."""
    text = file_path.read_text(encoding="utf-8").strip()
    parts = re.split(r"(?m)^(?=##\s+)", text)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part.startswith("## "):  # skips the '# Title' line at the top
            continue
        lines = part.splitlines()
        section_title = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()
        if body:
            chunks.append({
                "source_file": file_path.name,
                "section_title": section_title,
                "content": f"{section_title}\n{body}",
            })
    return chunks


def ingest_policies() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env")

    all_chunks = []
    for md_file in sorted(POLICIES_DIR.glob("*.md")):
        all_chunks.extend(chunk_markdown_by_section(md_file))
    print(f"Found {len(all_chunks)} section chunks.")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE policy_chunks RESTART IDENTITY;")  # makes re-running safe
            for i, c in enumerate(all_chunks, start=1):
                vec = embed_text(c["content"], "RETRIEVAL_DOCUMENT")
                cur.execute(
                    "INSERT INTO policy_chunks (source_file, section_title, content, embedding) "
                    "VALUES (%s, %s, %s, %s::vector)",
                    (c["source_file"], c["section_title"], c["content"], str(vec)),
                )
                print(f"  [{i}/{len(all_chunks)}] {c['source_file']} - {c['section_title']}")
                time.sleep(0.3)  # gentle pacing for the free tier
        conn.commit()
    print("Done: policy chunks stored in pgvector.")


if __name__ == "__main__":
    ingest_policies()