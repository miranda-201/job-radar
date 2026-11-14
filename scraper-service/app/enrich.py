"""Replace second-hand posting dates with the employer's own date.

GitHub internship lists record when a maintainer *added* a role, often days after the
employer posted it, and Workday boards only say "Posted 9 Days Ago". For links that
point at a known ATS, this module asks that ATS for the real publish date:

  Workday     GET {host}/wday/cxs/{tenant}/{site}/job/{path}  -> jobPostingInfo.startDate
  Greenhouse  GET boards-api.greenhouse.io/v1/boards/{token}/jobs/{id} -> first_published
  Lever       GET api.lever.co/v0/postings/{company}/{id}     -> createdAt
  Ashby       GET api.ashbyhq.com/posting-api/job-board/{org} -> jobs[].publishedAt

Shortlinks (e.g. go.vansh.nyc) are resolved first. Any failure leaves the original date
in place: enrichment can only improve a posting, never block or drop it.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
from prometheus_client import Counter

from app.models import DateSource, JobPosting
from app.sources.github_list import strip_tracking

log = logging.getLogger(__name__)

ENRICHED = Counter("scraper_dates_verified_total", "Postings whose employer posting date was verified", ["ats"])
UNVERIFIED = Counter("scraper_dates_unverified_total", "Postings left with a list/approximate date")

# Only re-check list dates this recent; for older postings a few days' error matters little.
MAX_AGE = timedelta(days=30)
SHORTLINK_HOSTS = {"go.vansh.nyc", "bit.ly", "tinyurl.com", "simplify.jobs"}

_WORKDAY = re.compile(
    r"^https?://(?P<host>(?P<tenant>[\w-]+)\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?"
    r"(?P<site>[^/?#]+)/job/(?P<path>[^?#]+)"
)
_GREENHOUSE = re.compile(r"^https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?P<token>[\w-]+)/jobs/(?P<id>\d+)")
_GREENHOUSE_EMBED = re.compile(r"^https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/embed/job_app")
_LEVER = re.compile(r"^https?://jobs\.(?P<eu>eu\.)?lever\.co/(?P<company>[^/?#]+)/(?P<id>[0-9a-f-]{36})")
_ASHBY = re.compile(r"^https?://jobs\.ashbyhq\.com/(?P<org>[^/?#]+)/(?P<id>[0-9a-f-]{36})")


def needs_enrichment(p: JobPosting, now: datetime | None = None) -> bool:
    if p.date_source == DateSource.APPROXIMATE:
        return True
    if p.date_source == DateSource.LIST:
        now = now or datetime.now(UTC)
        return p.posted_at is None or now - p.posted_at <= MAX_AGE
    return False


class Enricher:
    def __init__(self, client: httpx.AsyncClient, concurrency: int = 16):
        self._client = client
        self._sem = asyncio.Semaphore(concurrency)
        self._ashby_boards: dict[str, asyncio.Task[dict[str, str]]] = {}

    def new_sweep(self) -> None:
        self._ashby_boards.clear()

    async def enrich_all(self, postings: list[JobPosting]) -> None:
        await asyncio.gather(*(self.enrich(p) for p in postings if needs_enrichment(p)))

    async def enrich(self, p: JobPosting) -> None:
        async with self._sem:
            try:
                url = await self._resolve(p.url)
                if url != p.url:
                    p.url = strip_tracking(url)
                found = await self._employer_date(p.url)
            except Exception as exc:  # network errors, removed postings, unexpected JSON
                log.debug("date enrichment failed for %s: %s", p.url, exc)
                found = None
        if found:
            ats, posted = found
            p.posted_at, p.date_source = posted, DateSource.EMPLOYER
            ENRICHED.labels(ats).inc()
        else:
            UNVERIFIED.inc()

    async def _resolve(self, url: str) -> str:
        if urlparse(url).netloc.lower() not in SHORTLINK_HOSTS:
            return url
        resp = await self._client.head(url, follow_redirects=True)
        if resp.status_code >= 400:
            resp = await self._client.get(url, follow_redirects=True)
        return str(resp.url)

    async def _employer_date(self, url: str) -> tuple[str, datetime] | None:
        if m := _WORKDAY.match(url):
            api = f"https://{m['host']}/wday/cxs/{m['tenant']}/{m['site']}/job/{m['path']}"
            info = (await self._get_json(api)).get("jobPostingInfo") or {}
            start = info.get("startDate")
            # Date-only: store at noon UTC so it shows as the same calendar day in every US/EU timezone
            # (midnight UTC is the *previous* evening in the Americas).
            return ("workday", datetime.fromisoformat(start).replace(hour=12, tzinfo=UTC)) if start else None

        token = job_id = None
        if m := _GREENHOUSE.match(url):
            token, job_id = m["token"], m["id"]
        elif _GREENHOUSE_EMBED.match(url):
            q = parse_qs(urlparse(url).query)
            token, job_id = (q.get("for") or [None])[0], (q.get("token") or [None])[0]
        if token and job_id:
            job = await self._get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}")
            published = job.get("first_published") or job.get("updated_at")
            return ("greenhouse", datetime.fromisoformat(published)) if published else None

        if m := _LEVER.match(url):
            host = "api.eu.lever.co" if m["eu"] else "api.lever.co"
            job = await self._get_json(f"https://{host}/v0/postings/{m['company']}/{m['id']}")
            created = job.get("createdAt")
            return ("lever", datetime.fromtimestamp(created / 1000, tz=UTC)) if created else None

        if m := _ASHBY.match(url):
            published = (await self._ashby_board(m["org"])).get(m["id"])
            return ("ashby", datetime.fromisoformat(published)) if published else None
        return None

    async def _ashby_board(self, org: str) -> dict[str, str]:
        # One board request per org per sweep, shared by every posting from that org.
        if org not in self._ashby_boards:

            async def load() -> dict[str, str]:
                data = await self._get_json(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
                return {j["id"]: j.get("publishedAt") for j in data.get("jobs", [])}

            self._ashby_boards[org] = asyncio.ensure_future(load())
        try:
            return await self._ashby_boards[org]
        except Exception:
            return {}

    async def _get_json(self, url: str) -> dict:
        resp = await self._client.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
