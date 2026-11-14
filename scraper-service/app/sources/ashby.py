"""Ashby public Job Board API (used by many startups: Ramp, Notion, Linear, ...).

GET https://api.ashbyhq.com/posting-api/job-board/{board}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.models import JobPosting, SourceType, Target

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{board}"


def parse(payload: dict[str, Any], target: Target) -> list[JobPosting]:
    postings: list[JobPosting] = []
    for job in payload.get("jobs", []):
        if job.get("isListed") is False:
            continue
        published = job.get("publishedAt")
        postings.append(
            JobPosting(
                source=SourceType.ASHBY,
                company=target.company,
                external_id=job["id"],
                title=job["title"].strip(),
                location=job.get("location"),
                url=job.get("jobUrl") or job.get("applyUrl"),
                posted_at=datetime.fromisoformat(published) if published else None,
                internship=job.get("employmentType") == "Intern",
            )
        )
    return postings


class AshbySource:
    async def fetch(self, client: httpx.AsyncClient, target: Target) -> list[JobPosting]:
        resp = await client.get(BASE_URL.format(board=target.board))
        resp.raise_for_status()
        return parse(resp.json(), target)
