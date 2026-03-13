from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from ..models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorEnvelope,
    TelemetryEvent,
    TelemetryIngestResponse,
)
from ..services.analyze import analyze_article
from ..services.telemetry_db import get_conn, insert_event

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    responses={
        400: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
        502: {"model": ErrorEnvelope},
    },
)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    if (not req.url or not req.url.strip()) and (not req.text or not req.text.strip()):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "EMPTY_INPUT",
                    "message": "Provide either url or text.",
                    "hint": "Paste an article link or paste the article text.",
                }
            },
        )


@router.post("/telemetry", response_model=TelemetryIngestResponse)
def ingest_telemetry(event: TelemetryEvent) -> TelemetryIngestResponse:
    # Minimal validation: keep the types flexible but prevent huge payloads.
    meta_json = None
    if event.meta is not None:
        meta_json = json.dumps(event.meta)[:8000]

    insert_event(
        event_type=event.event_type,
        client_ts_ms=event.ts_ms,
        session_id=event.session_id,
        install_id=event.install_id,
        page_url=event.page_url,
        page_domain=event.page_domain,
        section_id=event.section_id,
        duration_ms=event.duration_ms,
        link_url=event.link_url,
        link_domain=event.link_domain,
        link_kind=event.link_kind,
        meta_json=meta_json,
    )

    return TelemetryIngestResponse(ok=True, inserted=1)


@router.get("/telemetry/summary")
def telemetry_summary() -> dict:
    """Lightweight rollup for quick debugging (not a full analytics API)."""

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM telemetry_events").fetchone()["c"]
        by_type_rows = conn.execute(
            "SELECT event_type, COUNT(*) AS c FROM telemetry_events GROUP BY event_type ORDER BY c DESC"
        ).fetchall()

        # CTR: clicks / impressions for events that include link_kind.
        impressions = conn.execute(
            "SELECT COUNT(*) AS c FROM telemetry_events WHERE event_type = 'link_impression'"
        ).fetchone()["c"]
        clicks = conn.execute(
            "SELECT COUNT(*) AS c FROM telemetry_events WHERE event_type = 'link_click'"
        ).fetchone()["c"]
        ctr = (clicks / impressions) if impressions else None

        return {
            "total_events": total,
            "by_type": [{"event_type": r["event_type"], "count": r["c"]} for r in by_type_rows],
            "click_through": {
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
            },
        }
    finally:
        conn.close()

    try:
        return analyze_article(req)
    except HTTPException as e:
        raise e
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "code": "ANALYZE_FAILED",
                    "message": "Analysis failed.",
                    "hint": str(e),
                }
            },
        )
