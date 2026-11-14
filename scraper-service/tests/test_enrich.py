from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.enrich import Enricher, needs_enrichment
from app.models import DateSource, JobPosting, SourceType, Target
from app.publisher import InMemoryPublisher
from app.scraper import ScrapeRunner
from app.store import InMemoryStore

TRINZIC = (
    "https://trinzic.wd115.myworkdayjobs.com/trinzic_careers/job/Chantilly-Virginia/"
    "Defense---Intel--D-I----Software-Engineering-Internship_R3001235"
)
TRINZIC_API = (
    "https://trinzic.wd115.myworkdayjobs.com/wday/cxs/trinzic/trinzic_careers/job/Chantilly-Virginia/"
    "Defense---Intel--D-I----Software-Engineering-Internship_R3001235"
)
LIST_DATE = datetime(2026, 11, 14, 3, 6, tzinfo=UTC)


def listed(url: str, posted: datetime | None = None) -> JobPosting:
    return JobPosting(
        source=SourceType.GITHUB_LIST,
        company="Trinzic",
        external_id="x",
        title="Software Engineering Internship",
        url=url,
        posted_at=posted or datetime.now(UTC) - timedelta(days=1),
        date_source=DateSource.LIST,
    )


@respx.mock
async def test_shortlink_is_resolved_and_workday_start_date_replaces_list_date():
    respx.head("https://go.vansh.nyc/1zz").mock(return_value=httpx.Response(302, headers={"Location": TRINZIC}))
    respx.head(TRINZIC).mock(return_value=httpx.Response(200))
    respx.get(TRINZIC_API).mock(
        return_value=httpx.Response(
            200, json={"jobPostingInfo": {"startDate": "2026-11-05", "postedOn": "Posted 9 Days Ago"}}
        )
    )
    p = listed("https://go.vansh.nyc/1zz")
    async with httpx.AsyncClient() as client:
        await Enricher(client).enrich(p)
    assert p.url == TRINZIC
    assert p.posted_at == datetime(2026, 11, 5, 12, tzinfo=UTC)  # noon UTC: same day in every US timezone
    assert p.date_source == DateSource.EMPLOYER


@respx.mock
@pytest.mark.parametrize(
    "url,api,body,expected",
    [
        (
            "https://job-boards.greenhouse.io/acme/jobs/123?utm_source=Simplify",
            "https://boards-api.greenhouse.io/v1/boards/acme/jobs/123",
            {"first_published": "2026-11-03T09:00:00-05:00"},
            datetime(2026, 11, 3, 14, tzinfo=UTC),
        ),
        (
            "https://boards.greenhouse.io/embed/job_app?for=acme&token=456",
            "https://boards-api.greenhouse.io/v1/boards/acme/jobs/456",
            {"first_published": "2026-11-02T00:00:00+00:00"},
            datetime(2026, 11, 2, tzinfo=UTC),
        ),
        (
            "https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd",
            "https://api.lever.co/v0/postings/acme/6ed76ce8-4156-4b60-b120-403538bd66cd",
            {"createdAt": 1793750400000},
            datetime(2026, 11, 4, tzinfo=UTC),
        ),
    ],
)
async def test_greenhouse_and_lever_dates(url, api, body, expected):
    respx.get(api).mock(return_value=httpx.Response(200, json=body))
    p = listed(url)
    async with httpx.AsyncClient() as client:
        await Enricher(client).enrich(p)
    assert p.posted_at == expected
    assert p.date_source == DateSource.EMPLOYER


@respx.mock
async def test_ashby_board_is_fetched_once_per_org_per_sweep():
    a, b = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
    route = respx.get("https://api.ashbyhq.com/posting-api/job-board/ramp").mock(
        return_value=httpx.Response(
            200,
            json={"jobs": [{"id": a, "publishedAt": "2026-11-01T00:00:00+00:00"}, {"id": b, "publishedAt": None}]},
        )
    )
    p1, p2 = listed(f"https://jobs.ashbyhq.com/ramp/{a}"), listed(f"https://jobs.ashbyhq.com/ramp/{b}")
    async with httpx.AsyncClient() as client:
        await Enricher(client).enrich_all([p1, p2])
    assert route.call_count == 1
    assert p1.date_source == DateSource.EMPLOYER and p1.posted_at.day == 1
    assert p2.date_source == DateSource.LIST  # no date published -> keeps list date


@respx.mock
async def test_failures_and_unknown_sites_keep_the_original_date():
    respx.get("https://boards-api.greenhouse.io/v1/boards/gone/jobs/1").mock(return_value=httpx.Response(404))
    gone, other = listed("https://boards.greenhouse.io/gone/jobs/1"), listed("https://careers.example.com/job/42")
    before = (gone.posted_at, other.posted_at)
    async with httpx.AsyncClient() as client:
        await Enricher(client).enrich_all([gone, other])
    assert (gone.posted_at, other.posted_at) == before
    assert gone.date_source == other.date_source == DateSource.LIST


def test_only_recent_list_dates_and_approximate_dates_are_checked():
    now = datetime(2026, 11, 14, tzinfo=UTC)
    assert needs_enrichment(listed("u", now - timedelta(days=3)), now)
    assert not needs_enrichment(listed("u", now - timedelta(days=90)), now)
    approx = listed("u", now - timedelta(days=90))
    approx.date_source = DateSource.APPROXIMATE
    assert needs_enrichment(approx, now)
    employer = listed("u")
    employer.date_source = DateSource.EMPLOYER
    assert not needs_enrichment(employer, now)


class FakeSource:
    def __init__(self, postings):
        self.postings = postings

    async def fetch(self, client, target):
        return self.postings


class NoopEnricher:
    def new_sweep(self):
        pass

    async def enrich_all(self, postings):
        pass


async def test_publish_failure_rolls_back_every_unpublished_posting():
    store, pub = InMemoryStore(), InMemoryPublisher()
    t = Target(id="acme", company="Acme", source=SourceType.GREENHOUSE, board="acme", keywords=["intern"])
    await store.upsert_target(t)
    postings = [
        JobPosting(source=SourceType.GREENHOUSE, company="Acme", external_id=str(i), title="SWE Intern", url=f"u{i}")
        for i in range(3)
    ]
    async with httpx.AsyncClient() as client:
        runner = ScrapeRunner(store, pub, client, source_lookup=lambda _: FakeSource(postings), enricher=NoopEnricher())
        pub.fail_next = True
        assert (await runner.run_all()).results[0].error
        assert (await runner.run_all()).results[0].new == 3  # nothing was lost
