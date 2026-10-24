"""Settings loaded from the environment. The ONLY place secrets are read."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    model: str
    max_tokens: int
    llm_timeout_s: float

    def __repr__(self) -> str:  # never leak the key in logs or tracebacks
        key = "set" if self.anthropic_api_key else "missing"
        return f"Settings(anthropic_api_key=<{key}>, model={self.model!r}, max_tokens={self.max_tokens})"


def load_settings() -> Settings:
    """Read settings from env vars. Optionally loads .env via python-dotenv if it's installed."""
    try:  # optional dependency
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(override=False)
    except ImportError:
        pass
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model=os.environ.get("PROOFKIT_MODEL", "claude-sonnet-5-5"),
        max_tokens=int(os.environ.get("PROOFKIT_MAX_TOKENS", "4096")),
        llm_timeout_s=float(os.environ.get("PROOFKIT_LLM_TIMEOUT_S", "60")),
    )
