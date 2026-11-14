"""ATS adapters. Each adapter turns one career page into normalized JobPostings."""

from __future__ import annotations

from typing import Protocol

import httpx

from app.models import JobPosting, SourceType, Target
from app.sources.ashby import AshbySource
from app.sources.github_list import GithubListSource
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource
from app.sources.workday import WorkdaySource


class JobSource(Protocol):
    async def fetch(self, client: httpx.AsyncClient, target: Target) -> list[JobPosting]: ...


REGISTRY: dict[SourceType, JobSource] = {
    SourceType.GREENHOUSE: GreenhouseSource(),
    SourceType.LEVER: LeverSource(),
    SourceType.WORKDAY: WorkdaySource(),
    SourceType.ASHBY: AshbySource(),
    SourceType.GITHUB_LIST: GithubListSource(),
}


def source_for(target: Target) -> JobSource:
    return REGISTRY[target.source]
