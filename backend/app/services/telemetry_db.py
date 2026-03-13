from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

DB_ENV = "TELEMETRY_DB_PATH"
DEFAULT_DB_FILENAME = "telemetry.sqlite"


def _db_path() -> Path:
    # Default to backend/telemetry.sqlite (project-local). In production you can
    # set TELEMETRY_DB_PATH.
    base = Path(__file__).resolve().parents[2]
    configured = os.getenv(DB_ENV)
    return Path(configured) if configured else (base / DEFAULT_DB_FILENAME)


def get_conn() -> sqlite3.Connection:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              received_ts_ms INTEGER NOT NULL,

              event_type TEXT NOT NULL,
              client_ts_ms INTEGER NOT NULL,

              session_id TEXT,
              install_id TEXT,

              page_url TEXT,
              page_domain TEXT,

              section_id TEXT,
              duration_ms INTEGER,

              link_url TEXT,
              link_domain TEXT,
              link_kind TEXT,

              meta_json TEXT
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_telemetry_event_type ON telemetry_events(event_type);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_telemetry_page_domain ON telemetry_events(page_domain);"
        )
        conn.commit()
    finally:
        conn.close()


def insert_event(
    *,
    event_type: str,
    client_ts_ms: int,
    session_id: str | None,
    install_id: str | None,
    page_url: str | None,
    page_domain: str | None,
    section_id: str | None,
    duration_ms: int | None,
    link_url: str | None,
    link_domain: str | None,
    link_kind: str | None,
    meta_json: str | None,
) -> int:
    conn = get_conn()
    try:
        received_ts_ms = int(time.time() * 1000)
        cur = conn.execute(
            """
            INSERT INTO telemetry_events (
              received_ts_ms,
              event_type,
              client_ts_ms,
              session_id,
              install_id,
              page_url,
              page_domain,
              section_id,
              duration_ms,
              link_url,
              link_domain,
              link_kind,
              meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                received_ts_ms,
                event_type,
                client_ts_ms,
                session_id,
                install_id,
                page_url,
                page_domain,
                section_id,
                duration_ms,
                link_url,
                link_domain,
                link_kind,
                meta_json,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()
