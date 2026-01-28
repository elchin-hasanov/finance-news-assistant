from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .settings import get_settings
from .api.routes import router


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="De-Hype Financial News API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins including Chrome extensions
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _request_diagnostics(request: Request, call_next):
        # Helps debug issues like a browser getting 403 while direct curl/python succeeds.
        # We keep it lightweight and safe (no body logging).
        response = await call_next(request)
        if response.status_code in (401, 403, 405):
            origin = request.headers.get("origin")
            ua = request.headers.get("user-agent")
            # Uses stdlib logging through uvicorn (prints to console).
            print(
                f"WARN forbidden/method-not-allowed: {request.method} {request.url.path} -> {response.status_code}; "
                f"origin={origin!r}; ua={ua!r}"
            )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Normalize errors into our ErrorEnvelope shape across all status codes.
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            payload = {"detail": detail}
        else:
            payload = {
                "detail": {
                    "error": {
                        "code": "HTTP_ERROR",
                        "message": str(detail) if detail else "Request failed.",
                        "hint": None,
                    }
                }
            }

        return JSONResponse(status_code=exc.status_code, content=payload)

    app.include_router(router)

    return app


app = create_app()
