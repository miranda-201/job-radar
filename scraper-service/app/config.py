from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    redis_url: str | None = field(default_factory=lambda: os.getenv("REDIS_URL"))
    rabbitmq_url: str | None = field(default_factory=lambda: os.getenv("RABBITMQ_URL"))
    jwt_secret: str = field(
        default_factory=lambda: os.getenv("JWT_SECRET", "dev-only-secret-change-me-dev-only-secret-change-me")
    )
    scrape_interval_seconds: int = field(default_factory=lambda: int(os.getenv("SCRAPE_INTERVAL_SECONDS", "900")))
    scrape_on_startup: bool = field(default_factory=lambda: os.getenv("SCRAPE_ON_STARTUP", "true") == "true")
    concurrency: int = field(default_factory=lambda: int(os.getenv("SCRAPE_CONCURRENCY", "4")))
    http_timeout: float = field(default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_SECONDS", "20")))
    user_agent: str = field(
        default_factory=lambda: os.getenv("USER_AGENT", "JobRadar/1.0 (+https://github.com/; educational project)")
    )
    targets_file: str = field(
        default_factory=lambda: os.getenv("TARGETS_FILE", os.path.join(os.path.dirname(__file__), "..", "targets.json"))
    )
