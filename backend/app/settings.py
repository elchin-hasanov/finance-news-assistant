from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel
from dotenv import load_dotenv
import os


class Settings(BaseModel):
    cors_origins: list[str]
    http_timeout_seconds: float
    user_agent: str
    alpha_vantage_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    cors = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    cors_origins = [o.strip() for o in cors.split(",") if o.strip()]
    
    # Always allow Chrome extension origins (they use chrome-extension:// scheme)
    # Also allow localhost variants for development
    default_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    for origin in default_origins:
        if origin not in cors_origins:
            cors_origins.append(origin)

    timeout = float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
    user_agent = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    )

    alpha_vantage_api_key = os.getenv("ALPHAVANTAGE_API_KEY") or os.getenv("ALPHA_VANTAGE_API_KEY")

    return Settings(
        cors_origins=cors_origins,
        http_timeout_seconds=timeout,
        user_agent=user_agent,
        alpha_vantage_api_key=alpha_vantage_api_key,
    )
