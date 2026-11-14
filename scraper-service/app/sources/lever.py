"""Lever public Postings API: GET api.lever.co/v0/postings/{company}?mode=json"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.models import JobPosting, SourceType, Target

BASE_URL = "https://api.lever.co/v0/postings/{board}"


def parse(payload: list[dict[str, Any]], target: Target) -> list[JobPosting]:
    postings: list[JobPosting] = []
    for job in payload:
        created_ms = job.get("createdAt")
        postings.append(
            JobPosting(
                source=SourceType.LEVER,
                company=target.company,
                external_id=job["id"],
                title=job["text"].strip(),
                location=(job.get("categories") or {}).get("location"),
                url=job["hostedUrl"],
                posted_at=(datetime.fromtimestamp(created_ms / 1000, tz=UTC) if created_ms else None),
            )
        )
    return postings


class LeverSource:
    async def fetch(self, client: httpx.AsyncClient, target: Target) -> list[JobPosting]:
        resp = await client.get(BASE_URL.format(board=target.board), params={"mode": "json"})
        resp.raise_for_status()
        return parse(resp.json(), target)
