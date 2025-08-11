from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import logging


ACCEPT_MAP = {
    "csv": "text/csv",
    "json": "application/json",
    "arrow": "application/vnd.apache.arrow.stream",
}


class LogfireQueryClient:
    def __init__(self, base_url: str, read_token: str, default_accept: str = "csv") -> None:
        self._log = logging.getLogger(__name__)
        self.base_url = base_url.rstrip("/")
        self.read_token = read_token
        self.default_accept = default_accept
        self._client = httpx.Client(timeout=60.0)
        self._log.debug(
            "Initialized LogfireQueryClient base_url=%s default_accept=%s",
            self.base_url,
            self.default_accept,
        )

    def close(self) -> None:
        self._client.close()

    def _headers(self, accept: Optional[str]) -> Dict[str, str]:
        fmt = accept or self.default_accept
        return {
            "Authorization": f"Bearer {self.read_token}",
            "Accept": ACCEPT_MAP.get(fmt, ACCEPT_MAP["csv"]),
        }

    @retry(wait=wait_exponential(multiplier=0.5, min=1, max=10), stop=stop_after_attempt(3))
    def _request(self, params: Dict[str, str], accept: Optional[str]) -> httpx.Response:
        url = f"{self.base_url}/v1/query"
        self._log.info("HTTP GET %s params=%s accept=%s", url, json.dumps(params, ensure_ascii=False), accept or self.default_accept)
        try:
            resp = self._client.get(url, params=params, headers=self._headers(accept))
            self._log.info(
                "HTTP %s %s elapsed=%sms", resp.status_code, url, getattr(resp, "elapsed", None).total_seconds() * 1000 if getattr(resp, "elapsed", None) else "?"
            )
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            body = getattr(e.response, "text", "")
            self._log.error("HTTPStatusError %s body=%s", e, body[:2000])
            raise
        except httpx.RequestError as e:
            self._log.exception("RequestError: %s", e)
            raise

    def query(
        self,
        sql: str,
        *,
        accept: Optional[str] = None,
        min_ts: Optional[datetime] = None,
        max_ts: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Execute SQL against Logfire Query API and return (DataFrame, meta).

        Meta includes: {"accept": str, "status_code": int}
        """
        params: Dict[str, str] = {"sql": sql}
        if min_ts:
            params["min_timestamp"] = min_ts.isoformat()
        if max_ts:
            params["max_timestamp"] = max_ts.isoformat()
        if limit:
            params["limit"] = str(limit)

        self._log.debug("Query start accept=%s limit=%s min_ts=%s max_ts=%s", accept or self.default_accept, limit, min_ts, max_ts)
        resp = self._request(params, accept)
        fmt = (accept or self.default_accept).lower()
        meta = {"accept": fmt, "status_code": resp.status_code}

        if fmt == "csv":
            df = pd.read_csv(io.StringIO(resp.text))
        elif fmt == "json":
            payload = resp.json()
            # Accept either list-of-dicts or {"data": [...]} 
            if isinstance(payload, dict) and "data" in payload:
                rows = payload["data"]
            else:
                rows = payload
            df = pd.DataFrame(rows)
        elif fmt == "arrow":
            try:
                import pyarrow as pa
                import pyarrow.ipc as pa_ipc
            except Exception as e:  # pragma: no cover
                raise RuntimeError("pyarrow is required for Arrow responses") from e
            reader = pa_ipc.open_stream(resp.content)
            table = reader.read_all()
            df = table.to_pandas()
        else:
            raise ValueError(f"Unsupported accept format: {fmt}")

        self._log.info("Query success rows=%s format=%s status=%s", len(df.index), fmt, meta["status_code"])  # type: ignore[arg-type]
        return df, meta
