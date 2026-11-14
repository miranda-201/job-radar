"""scraper-service: watches ATS career pages and publishes new postings to RabbitMQ."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import Depends, FastAPI, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis

from app.auth import require_user
from app.config import Settings
from app.models import ScrapeReport, Target, TargetResult
from app.publisher import InMemoryPublisher, Publisher, RabbitPublisher
from app.scraper import ScrapeRunner
from app.store import InMemoryStore, RedisStore, Store, seed_targets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("scraper")


async def _connect_with_retry(publisher: RabbitPublisher, attempts: int = 15) -> None:
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            await publisher.connect()
            return
        except Exception as exc:
            log.warning("RabbitMQ not ready (attempt %d/%d): %s", attempt, attempts, exc)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 10)
    raise RuntimeError("could not connect to RabbitMQ")


async def _scheduler(runner: ScrapeRunner, settings: Settings) -> None:
    if not settings.scrape_on_startup:
        await asyncio.sleep(settings.scrape_interval_seconds)
    while True:
        try:
            await runner.run_all()
        except Exception:
            log.exception("scheduled sweep crashed")
        await asyncio.sleep(settings.scrape_interval_seconds)


def create_app(
    settings: Settings | None = None,
    store: Store | None = None,
    publisher: Publisher | None = None,
    client: httpx.AsyncClient | None = None,
    start_scheduler: bool = True,
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal store, publisher, client
        if store is None:
            store = (
                RedisStore(Redis.from_url(settings.redis_url, decode_responses=True))
                if settings.redis_url
                else InMemoryStore()
            )
        if publisher is None:
            if settings.rabbitmq_url:
                publisher = RabbitPublisher(settings.rabbitmq_url)
                await _connect_with_retry(publisher)
            else:
                log.warning("RABBITMQ_URL not set; events are kept in memory only")
                publisher = InMemoryPublisher()
        if client is None:
            client = httpx.AsyncClient(
                timeout=settings.http_timeout,
                headers={"User-Agent": settings.user_agent},
                follow_redirects=True,
            )

        seeded = await seed_targets(store, settings.targets_file)
        if seeded:
            log.info("seeded %d default targets", seeded)

        app.state.store = store
        app.state.publisher = publisher
        app.state.runner = ScrapeRunner(store, publisher, client, concurrency=settings.concurrency)

        task = asyncio.create_task(_scheduler(app.state.runner, settings)) if start_scheduler else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await publisher.close()
        await client.aclose()

    app = FastAPI(
        title="JobRadar Scraper Service",
        version="1.0.0",
        description="Polls Greenhouse, Lever and Workday career pages and emits job.discovered events.",
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.get("/health", tags=["ops"])
    async def health(response: Response) -> dict:
        redis_ok = await app.state.store.ping()
        rabbit_ok = app.state.publisher.is_connected()
        healthy = redis_ok and rabbit_ok
        if not healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "UP" if healthy else "DOWN", "redis": redis_ok, "rabbitmq": rabbit_ok}

    @app.get("/metrics", tags=["ops"])
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    api = "/api/scraper"

    @app.get(f"{api}/targets", response_model=list[Target], tags=["targets"])
    async def list_targets(_: str = Depends(require_user)) -> list[Target]:
        return await app.state.store.list_targets()

    @app.post(f"{api}/targets", response_model=Target, status_code=201, tags=["targets"])
    async def create_target(target: Target, _: str = Depends(require_user)) -> Target:
        if await app.state.store.get_target(target.id):
            raise HTTPException(status.HTTP_409_CONFLICT, f"target '{target.id}' already exists")
        await app.state.store.upsert_target(target)
        return target

    @app.put(f"{api}/targets/{{target_id}}", response_model=Target, tags=["targets"])
    async def update_target(target_id: str, target: Target, _: str = Depends(require_user)) -> Target:
        if target.id != target_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "id in path and body differ")
        if not await app.state.store.get_target(target_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "target not found")
        await app.state.store.upsert_target(target)
        return target

    @app.delete(f"{api}/targets/{{target_id}}", status_code=204, tags=["targets"])
    async def delete_target(target_id: str, _: str = Depends(require_user)) -> Response:
        if not await app.state.store.delete_target(target_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "target not found")
        return Response(status_code=204)

    @app.post(f"{api}/scrape", response_model=ScrapeReport, tags=["scrape"])
    async def scrape_all(_: str = Depends(require_user)) -> ScrapeReport:
        return await app.state.runner.run_all()

    @app.post(f"{api}/targets/{{target_id}}/scrape", response_model=TargetResult, tags=["scrape"])
    async def scrape_one(target_id: str, _: str = Depends(require_user)) -> TargetResult:
        target = await app.state.store.get_target(target_id)
        if not target:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "target not found")
        return await app.state.runner.run_one(target)

    @app.get(f"{api}/scrape/last", response_model=ScrapeReport | None, tags=["scrape"])
    async def last_report(_: str = Depends(require_user)) -> ScrapeReport | None:
        return app.state.runner.last_report

    return app


app = create_app()
