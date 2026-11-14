"""Domain models shared across the scraper service."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.classify import DegreeLevel, RoleCategory


class SourceType(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    ASHBY = "ashby"
    GITHUB_LIST = "github_list"


class DateSource(str, Enum):
    EMPLOYER = "employer"  # the employer's ATS published this date
    APPROXIMATE = "approximate"  # employer-provided but coarse ("Posted 9 Days Ago")
    LIST = "list"  # when a third-party list added the role; may lag the real posting


class Target(BaseModel):
    """A company career page that the scraper watches."""

    id: str = Field(description="URL-safe slug, unique per target")
    company: str
    source: SourceType
    board: str = Field(
        description=(
            "Greenhouse/Lever: the board token (e.g. 'stripe'). "
            "Workday: the full career-site URL "
            "(e.g. https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite). "
            "Ashby: the job-board name (e.g. 'ramp'). "
            "GitHub list: 'owner/repo' of a Simplify-format internship list, or a raw listings.json URL."
        )
    )
    keywords: list[str] = Field(
        default_factory=list,
        description=(
            "Case-insensitive whole-word title filters (e.g. 'intern'). Empty list matches every posting. "
            "Postings the source itself marks as internships always match."
        ),
    )
    cs_only: bool = Field(
        default=True,
        description="Only keep computer-science roles (software, data/AI/ML, cloud/infra, security).",
    )
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", v):
            raise ValueError("id must be a lowercase slug (a-z, 0-9, '-')")
        return v

    def matches(self, title: str) -> bool:
        if not self.keywords:
            return True
        # Whole-word match (plural allowed) so "intern" hits "Interns" but not "Internal Tools".
        pattern = r"\b(?:" + "|".join(re.escape(k.strip()) for k in self.keywords) + r")s?\b"
        return re.search(pattern, title, re.IGNORECASE) is not None

    def accepts(self, posting: JobPosting) -> bool:
        """Keyword/internship filter, then (optionally) the CS-role filter."""
        if not (posting.internship or self.matches(posting.title)):
            return False
        return posting.category is not None or not self.cs_only


class JobPosting(BaseModel):
    """A normalized posting, independent of which ATS it came from."""

    source: SourceType
    company: str
    external_id: str
    title: str
    location: str | None = None
    url: str
    posted_at: datetime | None = None
    category: RoleCategory | None = None
    term: str | None = Field(default=None, description="e.g. 'Summer 2027', when the source provides it")
    internship: bool = Field(default=False, description="True when the source itself labels the role an internship")
    date_source: DateSource = DateSource.EMPLOYER
    degree_level: DegreeLevel | None = None

    @property
    def dedup_key(self) -> str:
        return f"{self.source.value}:{self.company.lower()}:{self.external_id}"


class JobDiscoveredEvent(BaseModel):
    """Message contract published to RabbitMQ (routing key: job.discovered).

    Field names are camelCase because the consumer is a Java service.
    """

    eventId: str = Field(default_factory=lambda: str(uuid4()))
    eventType: str = "job.discovered"
    source: str
    company: str
    externalId: str
    title: str
    location: str | None
    url: str
    postedAt: datetime | None
    postedAtSource: str = DateSource.EMPLOYER.value
    category: str | None = None
    term: str | None = None
    degreeLevel: str | None = None
    discoveredAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_posting(cls, p: JobPosting) -> JobDiscoveredEvent:
        return cls(
            source=p.source.value,
            company=p.company,
            externalId=p.external_id,
            title=p.title,
            location=p.location,
            url=p.url,
            postedAt=p.posted_at,
            postedAtSource=p.date_source.value,
            category=p.category.value if p.category else None,
            term=p.term,
            degreeLevel=p.degree_level.value if p.degree_level else None,
        )


class TargetResult(BaseModel):
    target_id: str
    fetched: int = 0
    matched: int = 0
    new: int = 0
    error: str | None = None
    duration_ms: int = 0


class ScrapeReport(BaseModel):
    started_at: datetime
    finished_at: datetime
    results: list[TargetResult]

    @property
    def total_new(self) -> int:
        return sum(r.new for r in self.results)
