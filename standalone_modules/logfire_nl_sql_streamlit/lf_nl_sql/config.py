import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

ENV_VALUES = {}
ENV_SOURCE_PATH: Optional[Path] = None
try:  # Load ONLY a module-specific env file (or an explicitly specified one)
    from dotenv import dotenv_values  # type: ignore

    explicit_env = os.getenv("LF_NL_SQL_ENV_FILE")
    if explicit_env:
        env_path = Path(explicit_env)
    else:
        # Default to the module's own .env, not the repo root
        env_path = Path(__file__).resolve().parents[1] / ".env"

    if env_path.exists():
        ENV_VALUES = dotenv_values(str(env_path)) or {}
        ENV_SOURCE_PATH = env_path
except Exception:
    ENV_VALUES = {}


def _get(key: str, default: Optional[str] = None) -> Optional[str]:
    # Prefer module env file values; fallback to process env; then default
    if key in ENV_VALUES and ENV_VALUES[key] is not None:
        return str(ENV_VALUES[key])
    return os.getenv(key, default)


def get_env_source_path() -> Optional[Path]:
    """Return the env file path used by this module, if any."""
    return ENV_SOURCE_PATH


@dataclass
class Settings:
    logfire_api_base: str = _get("LOGFIRE_API_BASE", "https://logfire-api.pydantic.dev")  # type: ignore
    logfire_read_token: Optional[str] = _get("LOGFIRE_READ_TOKEN")
    default_time_range: str = _get("LOGFIRE_DEFAULT_TIME_RANGE", "24h")  # type: ignore
    default_row_limit: int = int(_get("LOGFIRE_DEFAULT_ROW_LIMIT", "1000") or "1000")
    accept_format: str = _get("ACCEPT_FORMAT", "csv")  # csv|json|arrow  # type: ignore

    llm_provider: str = _get("LLM_PROVIDER", "none")  # none|openai  # type: ignore
    llm_model: str = _get("LLM_MODEL", "gpt-4o-mini")  # type: ignore
    openai_api_key: Optional[str] = _get("OPENAI_API_KEY")

    saved_queries_path: str = _get("SAVED_QUERIES_PATH", "saved_queries.json")  # type: ignore

    def validate(self) -> None:
        if not self.logfire_read_token:
            raise RuntimeError("LOGFIRE_READ_TOKEN is required. Set it in environment or .env file.")
        if self.accept_format not in {"csv", "json", "arrow"}:
            raise RuntimeError("ACCEPT_FORMAT must be one of: csv, json, arrow")
        if self.llm_provider not in {"none", "openai"}:
            raise RuntimeError("LLM_PROVIDER must be one of: none, openai")
