"""Workday career sites.

Workday pages are client-rendered, but the SPA reads from a JSON endpoint:
    POST https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
with body {"appliedFacets": {}, "limit": 20, "offset": N, "searchText": "..."}.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models import DateSource, JobPosting, SourceType, Target

PAGE_SIZE = 20  # Workday rejects larger pages
MAX_PAGES = 10


@dataclass(frozen=True)
class WorkdaySite:
    host: str
    tenant: str
    site: str

    @property
    def api_url(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}/{self.site}/jobs"

    def job_url(self, external_path: str) -> str:
        return f"https://{self.host}/{self.site}{external_path}"


def parse_site(url: str) -> WorkdaySite:
    parsed = urlparse(url)
    host = parsed.netloc
    if not host.endswith("myworkdayjobs.com"):
        raise ValueError(f"not a Workday career site: {url}")
    # path may include a locale prefix, e.g. /en-US/NVIDIAExternalCareerSite
    parts = [p for p in parsed.path.split("/") if p and not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", p)]
    if not parts:
        raise ValueError(f"Workday URL is missing the site name: {url}")
    return WorkdaySite(host=host, tenant=host.split(".")[0], site=parts[0])


_POSTED_RE = re.compile(r"Posted (Today|Yesterday|(\d+)\+? Days? Ago)", re.IGNORECASE)


def parse_posted_on(text: str | None, now: datetime | None = None) -> datetime | None:
    """Workday only exposes relative dates ('Posted 3 Days Ago')."""
    if not text:
        return None
    now = now or datetime.now(UTC)
    m = _POSTED_RE.search(text)
    if not m:
        return None
    word = m.group(1).lower()
    if word == "today":
        days = 0
    elif word == "yesterday":
        days = 1
    else:
        days = int(m.group(2))
    # Noon UTC keeps the calendar day stable across US/EU timezones (see enrich.py).
    return (now - timedelta(days=days)).replace(hour=12, minute=0, second=0, microsecond=0)


def parse(payload: dict[str, Any], target: Target, site: WorkdaySite) -> list[JobPosting]:
    postings: list[JobPosting] = []
    for job in payload.get("jobPostings", []):
        path = job.get("externalPath")
        if not path:
            continue
        postings.append(
            JobPosting(
                source=SourceType.WORKDAY,
                company=target.company,
                external_id=path.rsplit("_", 1)[-1] if "_" in path else path,
                title=job["title"].strip(),
                location=job.get("locationsText"),
                url=site.job_url(path),
                posted_at=parse_posted_on(job.get("postedOn")),
                date_source=DateSource.APPROXIMATE,
            )
        )
    return postings


class WorkdaySource:
    async def fetch(self, client: httpx.AsyncClient, target: Target) -> list[JobPosting]:
        site = parse_site(target.board)
        # Push the first keyword to Workday's server-side search to keep pagination short.
        search = target.keywords[0] if len(target.keywords) == 1 else ""
        postings: list[JobPosting] = []
        for page in range(MAX_PAGES):
            resp = await client.post(
                site.api_url,
                json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": page * PAGE_SIZE, "searchText": search},
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            batch = parse(resp.json(), target, site)
            postings.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
        return postings
