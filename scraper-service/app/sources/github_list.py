"""Community-maintained internship lists on GitHub (Simplify format).

Repos such as SimplifyJobs/Summer2027-Internships and vanshb03/Summer2027-Internships
publish their tables from a machine-readable `.github/scripts/listings.json`. One list
covers thousands of companies, including startups that have no watchable ATS board.

The file is large (~13 MB), so requests use ETags: an unchanged list costs one 304.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.classify import RoleCategory, classify, degree_level
from app.models import DateSource, JobPosting, SourceType, Target

DEFAULT_PATH = ".github/scripts/listings.json"
DEFAULT_BRANCH = "dev"

# The list's own category labels, used when the title alone isn't conclusive.
_CATEGORY_MAP: dict[str, RoleCategory] = {
    "software": RoleCategory.SOFTWARE,
    "software engineering": RoleCategory.SOFTWARE,
    "ai/ml/data": RoleCategory.DATA_ML,
    "data science, ai & machine learning": RoleCategory.DATA_ML,
}

_TRACKING_PARAMS = re.compile(r"^(utm_.*|ref|referrer|source|src|gh_src)$", re.IGNORECASE)


def list_url(board: str) -> str:
    """'owner/repo' -> raw listings.json URL; full URLs pass through unchanged."""
    if board.startswith(("http://", "https://")):
        return board
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", board):
        raise ValueError(f"expected 'owner/repo' or a listings.json URL, got: {board}")
    return f"https://raw.githubusercontent.com/{board}/{DEFAULT_BRANCH}/{DEFAULT_PATH}"


def strip_tracking(url: str) -> str:
    parts = urlparse(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(k)]
    return urlunparse(parts._replace(query=urlencode(query)))


def _location(locations: list[str] | None) -> str | None:
    if not locations:
        return None
    shown = "; ".join(locations[:3])
    return shown if len(locations) <= 3 else f"{shown} +{len(locations) - 3} more"


def _term(job: dict[str, Any]) -> str | None:
    terms = [t for t in (job.get("terms") or []) if t and t != "N/A"]
    if terms:
        return ", ".join(terms[:2])
    season = job.get("season")
    return season if season and season != "N/A" else None


def parse(payload: list[dict[str, Any]], target: Target) -> list[JobPosting]:
    postings: list[JobPosting] = []
    for job in payload:
        if not job.get("active") or job.get("is_visible") is False:
            continue
        title = (job.get("title") or "").strip()
        url = job.get("url")
        if not title or not url or not job.get("company_name"):
            continue
        category = classify(title) or _CATEGORY_MAP.get((job.get("category") or "").lower())
        posted = job.get("date_posted")
        postings.append(
            JobPosting(
                source=SourceType.GITHUB_LIST,
                company=job["company_name"].strip(),
                external_id=str(job["id"]),
                title=title,
                location=_location(job.get("locations")),
                url=strip_tracking(url),
                posted_at=datetime.fromtimestamp(posted, tz=UTC) if posted else None,
                category=category,
                term=_term(job),
                internship=True,  # these lists only contain internships
                date_source=DateSource.LIST,
                degree_level=degree_level(
                    title, job.get("degrees")
                ),  # when the list added it, not when the employer posted
            )
        )
    return postings


class GithubListSource:
    def __init__(self) -> None:
        self._etags: dict[str, str] = {}

    async def fetch(self, client: httpx.AsyncClient, target: Target) -> list[JobPosting]:
        url = list_url(target.board)
        headers = {"If-None-Match": self._etags[url]} if url in self._etags else {}
        resp = await client.get(url, headers=headers)
        if resp.status_code == 304:
            return []  # list unchanged since last sweep, so nothing can be new
        resp.raise_for_status()
        postings = parse(resp.json(), target)
        if etag := resp.headers.get("ETag"):
            self._etags[url] = etag
        return postings
