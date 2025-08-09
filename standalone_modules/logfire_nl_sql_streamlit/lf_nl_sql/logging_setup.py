import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def _coerce_level(level: Optional[str | int]) -> int:
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.INFO)
    return logging.INFO


def init_logging(level: Optional[str | int] = None, log_dir: Optional[str | os.PathLike[str]] = None) -> Path:
    """
    Initialize app logging.

    - Writes rotating logs to <module_root>/logs/app.log by default.
    - Can be overridden via env:
      - LF_NL_SQL_LOG_LEVEL (e.g., INFO, DEBUG)
      - LF_NL_SQL_LOG_DIR (absolute or relative path)

    Returns the resolved log file path.
    """
    # Resolve defaults
    module_root = Path(__file__).resolve().parents[1]
    env_level = os.getenv("LF_NL_SQL_LOG_LEVEL")
    env_dir = os.getenv("LF_NL_SQL_LOG_DIR")

    level_num = _coerce_level(level or env_level or "INFO")
    base_dir = Path(log_dir or env_dir or (module_root / "logs"))
    base_dir.mkdir(parents=True, exist_ok=True)

    log_file = base_dir / "app.log"

    # Configure root logger once
    root = logging.getLogger()
    root.setLevel(level_num)

    # Avoid duplicate handlers on rerun
    existing_names = {getattr(h, "name", None) for h in root.handlers}

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if "lf_nl_sql_file" not in existing_names:
        fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
        fh.setLevel(level_num)
        fh.setFormatter(fmt)
        fh.name = "lf_nl_sql_file"
        root.addHandler(fh)

    if "lf_nl_sql_console" not in existing_names:
        ch = logging.StreamHandler()
        ch.setLevel(level_num)
        ch.setFormatter(fmt)
        ch.name = "lf_nl_sql_console"
        root.addHandler(ch)

    logging.getLogger(__name__).info("Logging initialized at %s, file=%s", logging.getLevelName(level_num), str(log_file))

    return log_file
