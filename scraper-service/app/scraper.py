"""Core scrape loop: fetch -> filter -> dedupe -> publish, isolated per target."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from prometheus_client import Counter, Histogram

from app.classify import classify
from app.models import JobDiscoveredEvent, ScrapeReport, Target, TargetResult
from app.publisher import Publisher
from app.sources import JobSource, source_for
from app.store import Store

log = logging.getLogger(__name__)

JOBS_FETCHED = Counter("scraper_jobs_fetched_total", "Postings fetched", ["target"])
JOBS_PUBLISHED = Counter("scraper_jobs_published_total", "New postings published", ["target"])
SCRAPE_ERRORS = Counter("scraper_errors_total", "Failed target scrapes", ["target"])
SCRAPE_SECONDS = Histogram("scraper_target_seconds", "Time to scrape one target", ["target"])


class ScrapeRunner:
    def __init__(
        self,
        store: Store,
        publisher: Publisher,
        client: httpx.AsyncClient,
        concurrency: int = 4,
        source_lookup: Callable[[Target], JobSource] = source_for,
    ):
        self._store = store
        self._publisher = publisher
        self._client = client
        self._sem = asyncio.Semaphore(concurrency)
        self._source_lookup = source_lookup
        self._lock = asyncio.Lock()
        self.last_report: ScrapeReport | None = None

    async def run_all(self) -> ScrapeReport:
        # One sweep at a time; a manual trigger during a scheduled run just waits.
        async with self._lock:
            started = datetime.now(UTC)
            targets = [t for t in await self._store.list_targets() if t.enabled]
            results = await asyncio.gather(*(self._run_guarded(t) for t in targets))
            report = ScrapeReport(started_at=started, finished_at=datetime.now(UTC), results=list(results))
            self.last_report = report
            log.info("sweep complete: %d targets, %d new postings", len(results), report.total_new)
            return report

    async def run_one(self, target: Target) -> TargetResult:
        async with self._lock:
            return await self._run_guarded(target)

    async def _run_guarded(self, target: Target) -> TargetResult:
        async with self._sem:
            start = time.perf_counter()
            result = TargetResult(target_id=target.id)
            try:
                with SCRAPE_SECONDS.labels(target.id).time():
                    await self._scrape(target, result)
            except Exception as exc:  # one broken career page must not stop the sweep
                SCRAPE_ERRORS.labels(target.id).inc()
                result.error = f"{type(exc).__name__}: {exc}"
                log.warning("scrape failed for %s: %s", target.id, result.error)
            result.duration_ms = int((time.perf_counter() - start) * 1000)
            return result

    async def _scrape(self, target: Target, result: TargetResult) -> None:
        postings = await self._source_lookup(target).fetch(self._client, target)
        result.fetched = len(postings)
        JOBS_FETCHED.labels(target.id).inc(len(postings))

        for posting in postings:
            if posting.category is None:
                posting.category = classify(posting.title)
            if not target.accepts(posting):
                continue
            result.matched += 1
            if not await self._store.mark_seen(target.id, posting.dedup_key):
                continue
            try:
                await self._publisher.publish(JobDiscoveredEvent.from_posting(posting))
            except Exception:
                # Roll back the dedup mark so the posting is retried on the next sweep
                # instead of being silently lost.
                await self._store.forget_seen(target.id, posting.dedup_key)
                raise
            result.new += 1
            JOBS_PUBLISHED.labels(target.id).inc()
