"""Central LLM factory with exponential-backoff retry and fallback model support."""

import os
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from pydantic import BaseModel

load_dotenv(override=True)


def _parse_model_spec(spec: str, default_provider: str) -> tuple[str, str]:
    """Parse either 'provider:model_name' or plain 'model_name'."""
    cleaned = spec.strip()
    if ":" in cleaned:
        provider, model_name = cleaned.split(":", 1)
        return provider.strip(), model_name.strip()
    return default_provider, cleaned


def _get_model_specs() -> list[tuple[str, str]]:
    default_provider = os.getenv("LLM_PROVIDER", "google_genai").strip()
    primary = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite").strip()
    fallbacks_raw = os.getenv("LLM_FALLBACK_MODELS", "").strip()

    specs = [_parse_model_spec(primary, default_provider)]
    if fallbacks_raw:
        for item in fallbacks_raw.split(","):
            if item.strip():
                spec = _parse_model_spec(item, default_provider)
                if spec not in specs:
                    specs.append(spec)
    return specs


def build_chat_model(
    *,
    temperature: float = 0.0,
    tools: Sequence[Any] | None = None,
    structured_schema: type[BaseModel] | None = None,
) -> Runnable:
    """Build a chat model runnable with optional tool-binding or structured output,
    plus per-model retry and ordered model fallbacks.

    Note: `tools` and `structured_schema` are mutually exclusive in LangChain.
    """
    if tools and structured_schema:
        raise ValueError("Cannot pass both `tools` and `structured_schema` to the same model.")

    max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
    model_specs = _get_model_specs()

    runnables: list[Runnable] = []
    for provider, model_name in model_specs:
        base_model = init_chat_model(
            model=model_name,
            model_provider=provider,
            temperature=temperature,
        )

        # Apply tools or structured output BEFORE retry/fallbacks
        if tools:
            configured: Runnable = base_model.bind_tools(tools)
        elif structured_schema:
            configured = base_model.with_structured_output(structured_schema)
        else:
            configured = base_model

        if max_retries > 1:
            configured = configured.with_retry(
                stop_after_attempt=max_retries,
                wait_exponential_jitter=True,
            )

        runnables.append(configured)

    primary_runnable = runnables[0]
    if len(runnables) > 1:
        return primary_runnable.with_fallbacks(runnables[1:])
    return primary_runnable


if __name__ == "__main__":
    print("Configured models:", _get_model_specs())

    # 1. Plain chat test
    plain_llm = build_chat_model(temperature=0.0)
    reply = plain_llm.invoke("Reply with exactly the word: READY")
    print("1) Plain chat test ->", reply.content)

    # 2. Structured output test (needed for input_guard.py)
    class SmokeCheck(BaseModel):
        status: str
        is_hr_or_it: bool

    structured_llm = build_chat_model(temperature=0.0, structured_schema=SmokeCheck)
    parsed = structured_llm.invoke(
        "Classify this question: 'How many leave days does E102 have left?' "
        "Set status='ok' and is_hr_or_it=True if it is an HR or IT helpdesk question."
    )
    print("2) Structured output test ->", parsed)

    # 3. Tool-calling test (needed for MCP + RAG agent)
    @tool
    def get_leave_balance(employee_id: str) -> str:
        """Get the leave balance for an employee ID such as E102."""
        return "7 days"

    tool_llm = build_chat_model(temperature=0.0, tools=[get_leave_balance])
    tool_reply = tool_llm.invoke("How many leave days does E102 have left?")
    print("3) Tool-calling test ->", tool_reply.tool_calls)