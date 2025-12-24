from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import AnalyzeRequest, AnalyzeResponse, ErrorEnvelope
from ..services.analyze import analyze_article

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
