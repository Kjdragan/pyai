import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    # Load from current working directory first
    load_dotenv()
    # Also try module root .env to support running example app from project root
    try:
        module_root = Path(__file__).resolve().parents[1]
        alt_env = module_root / ".env"
        if alt_env.exists():
            load_dotenv(dotenv_path=alt_env, override=False)
    except Exception:
        pass
except Exception:
    pass


@dataclass
class Settings:
    logfire_api_base: str = os.getenv("LOGFIRE_API_BASE", "https://logfire-api.pydantic.dev")
    logfire_read_token: Optional[str] = os.getenv("LOGFIRE_READ_TOKEN")
    default_time_range: str = os.getenv("LOGFIRE_DEFAULT_TIME_RANGE", "24h")
    default_row_limit: int = int(os.getenv("LOGFIRE_DEFAULT_ROW_LIMIT", "1000"))
    accept_format: str = os.getenv("ACCEPT_FORMAT", "csv")  # csv|json|arrow

    llm_provider: str = os.getenv("LLM_PROVIDER", "none")  # none|openai
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")

    saved_queries_path: str = os.getenv("SAVED_QUERIES_PATH", "saved_queries.json")

    def validate(self) -> None:
        if not self.logfire_read_token:
            raise RuntimeError("LOGFIRE_READ_TOKEN is required. Set it in environment or .env file.")
        if self.accept_format not in {"csv", "json", "arrow"}:
            raise RuntimeError("ACCEPT_FORMAT must be one of: csv, json, arrow")
        if self.llm_provider not in {"none", "openai"}:
            raise RuntimeError("LLM_PROVIDER must be one of: none, openai")
