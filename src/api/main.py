"""FastAPI REST API exposing the HR & IT Helpdesk AI Agent."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.graph import HelpdeskAgent

# Silence harmless Gemini schema warning about FastMCP's `additionalProperties` key
logging.getLogger("langchain_google_genai").setLevel(logging.ERROR)

agent = HelpdeskAgent()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await agent.initialize()
    yield


app = FastAPI(
    title="HR & IT Helpdesk AI Agent API",
    description="LangGraph + pgvector RAG + FastMCP PostgreSQL agent with 3-layer guardrails.",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User HR or IT helpdesk question.",
    )


class ChatResponse(BaseModel):
    query: str
    answer: str
    guardrail_status: str
    guardrail_stage: str
    guardrail_reason: str
    tools_called: list[str]
    sources: list[str]
    pii_redacted: bool
    redacted_pii_types: list[str]
    latency_ms: int


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "tools_loaded": [t.name for t in agent.tools],
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await agent.ask(request.query)
        return ChatResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc