"""Greenhouse public Job Board API: GET boards-api.greenhouse.io/v1/boards/{token}/jobs"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.models import JobPosting, SourceType, Target

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def parse(payload: dict[str, Any], target: Target) -> list[JobPosting]:
    postings: list[JobPosting] = []
    for job in payload.get("jobs", []):
        posted = job.get("first_published") or job.get("updated_at")
        postings.append(
            JobPosting(
                source=SourceType.GREENHOUSE,
                company=target.company,
                external_id=str(job["id"]),
                title=job["title"].strip(),
                location=(job.get("location") or {}).get("name"),
                url=job["absolute_url"],
                posted_at=datetime.fromisoformat(posted) if posted else None,
            )
        )
    return postings


class GreenhouseSource:
    async def fetch(self, client: httpx.AsyncClient, target: Target) -> list[JobPosting]:
        resp = await client.get(BASE_URL.format(board=target.board))
        resp.raise_for_status()
        return parse(resp.json(), target)
