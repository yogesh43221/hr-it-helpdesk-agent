"""Finds the policy chunks closest in meaning to a question (cosine similarity in pgvector)."""
import os

import psycopg
from dotenv import load_dotenv

from src.rag.embeddings import embed_text

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL")


def search_policies(query: str, top_k: int = 3, min_similarity: float = 0.65) -> list[dict]:
    """Return the best matching chunks, each with a ready-to-use citation string."""
    vec = str(embed_text(query, "RETRIEVAL_QUERY"))
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_file, section_title, content,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM policy_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec, vec, top_k),
            )
            rows = cur.fetchall()

    return [
        {
            "citation": f"[Source: {src} — {section}]",
            "source_file": src,
            "section_title": section,
            "content": content,
            "similarity": round(float(sim), 3),
        }
        for src, section, content, sim in rows
        if sim >= min_similarity  # low scores mean "not really about this", so drop them
    ]


if __name__ == "__main__":
    for q in ["How many annual leave days can I carry over?",
              "How long to replace a broken laptop?",
              "What is the ESOP vesting schedule?"]:
        print(f"\nQuery: {q}")
        hits = search_policies(q)
        if not hits:
            print("  (no relevant policy found)")
        for h in hits:
            print(f"  {h['similarity']} | {h['citation']}")