from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.classify import RoleCategory
from app.models import JobPosting, SourceType, Target
from app.publisher import InMemoryPublisher
from app.scraper import ScrapeRunner
from app.sources import ashby, github_list
from app.store import InMemoryStore, seed_targets

LIST_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"


def gh_target(**kw) -> Target:
    return Target(
        id="simplify",
        company="Simplify list",
        source=SourceType.GITHUB_LIST,
        board="SimplifyJobs/Summer2027-Internships",
        **kw,
    )


def listing(i: int, title: str, **kw) -> dict:
    return {
        "id": f"id-{i}",
        "company_name": "Tiny Startup",
        "title": title,
        "locations": ["Des Moines, IA", "Remote in USA", "Chicago, IL", "Austin, TX"],
        "url": f"https://jobs.example.com/{i}?utm_source=Simplify&ref=Simplify&gh_jid=42",
        "date_posted": 1794614400,  # 2026-11-14T00:00:00Z
        "active": True,
        "is_visible": True,
        "terms": ["Summer 2027"],
        "category": "Software",
    } | kw


# ---- GitHub list adapter ------------------------------------------------------------


def test_github_list_url_shorthand_and_validation():
    assert github_list.list_url("SimplifyJobs/Summer2027-Internships") == LIST_URL
    assert github_list.list_url("https://example.com/listings.json") == "https://example.com/listings.json"
    with pytest.raises(ValueError):
        github_list.list_url("not a repo")


def test_github_list_parse_normalizes_and_filters():
    payload = [
        listing(1, "Software Engineer Intern"),
        listing(2, "Quant Research Intern", category="AI/ML/Data"),  # title inconclusive -> list category
        listing(3, "Closed role", active=False),
        listing(4, "Hidden role", is_visible=False),
        listing(5, "Hardware Intern", category="Hardware"),
    ]
    jobs = github_list.parse(payload, gh_target())
    assert [j.external_id for j in jobs] == ["id-1", "id-2", "id-5"]

    swe = jobs[0]
    assert swe.company == "Tiny Startup"  # per-listing company, not the target label
    assert swe.category == RoleCategory.SOFTWARE
    assert swe.internship is True
    assert swe.term == "Summer 2027"
    assert swe.posted_at == datetime(2026, 11, 14, tzinfo=UTC)
    assert swe.location == "Des Moines, IA; Remote in USA; Chicago, IL +1 more"
    assert swe.url == "https://jobs.example.com/1?gh_jid=42"  # tracking params stripped, real ones kept
    assert jobs[1].category == RoleCategory.DATA_ML
    assert jobs[2].category is None  # hardware is not a CS role


@respx.mock
async def test_github_list_uses_etag_to_skip_unchanged_lists():
    route = respx.get(LIST_URL)
    route.side_effect = [
        httpx.Response(200, json=[listing(1, "Software Engineer Intern")], headers={"ETag": '"v1"'}),
        httpx.Response(304),
    ]
    source = github_list.GithubListSource()
    async with httpx.AsyncClient() as client:
        assert len(await source.fetch(client, gh_target())) == 1
        assert await source.fetch(client, gh_target()) == []
    assert route.calls[1].request.headers["If-None-Match"] == '"v1"'


# ---- Ashby adapter ------------------------------------------------------------------


def test_ashby_parse_uses_employment_type_and_published_date():
    payload = {
        "jobs": [
            {
                "id": "a1",
                "title": "Software Engineer",
                "employmentType": "Intern",
                "location": "New York, NY",
                "publishedAt": "2026-11-10T17:12:35.753+00:00",
                "jobUrl": "https://jobs.ashbyhq.com/ramp/a1",
                "isListed": True,
            },
            {"id": "a2", "title": "Unlisted", "isListed": False, "jobUrl": "x"},
        ]
    }
    t = Target(id="ramp", company="Ramp", source=SourceType.ASHBY, board="ramp", keywords=["intern"])
    [job] = ashby.parse(payload, t)
    assert job.internship is True
    assert job.posted_at.date().isoformat() == "2026-11-10"
    # The title has no "intern", but Ashby marks it as one, so the target still accepts it.
    job.category = RoleCategory.SOFTWARE
    assert t.accepts(job)


# ---- CS-only filtering in the scrape loop ---------------------------------------------


class FakeSource:
    def __init__(self, postings):
        self.postings = postings

    async def fetch(self, client, target):
        return self.postings


def _posting(i: int, title: str) -> JobPosting:
    return JobPosting(
        source=SourceType.GREENHOUSE, company="Acme", external_id=str(i), title=title, url=f"https://x/{i}"
    )


async def test_scrape_keeps_only_cs_roles_and_tags_category():
    store, pub = InMemoryStore(), InMemoryPublisher()
    t = Target(id="acme", company="Acme", source=SourceType.GREENHOUSE, board="acme", keywords=["intern"])
    await store.upsert_target(t)
    source = FakeSource(
        [
            _posting(1, "Backend Engineer Intern"),
            _posting(2, "Marketing Intern"),
            _posting(3, "Data Science Intern"),
            _posting(4, "Senior Backend Engineer"),
        ]
    )
    async with httpx.AsyncClient() as client:
        report = await ScrapeRunner(store, pub, client, source_lookup=lambda _: source).run_all()
    assert report.results[0].matched == 2
    assert {(e.title, e.category) for e in pub.events} == {
        ("Backend Engineer Intern", "software"),
        ("Data Science Intern", "data_ml"),
    }


async def test_cs_only_can_be_disabled():
    t = Target(
        id="acme", company="Acme", source=SourceType.GREENHOUSE, board="acme", keywords=["intern"], cs_only=False
    )
    assert t.accepts(_posting(2, "Marketing Intern"))


# ---- seeding --------------------------------------------------------------------------


async def test_new_defaults_reach_existing_installs_but_deleted_ones_stay_deleted(tmp_path):
    store = InMemoryStore()
    v1 = tmp_path / "v1.json"
    v1.write_text('[{"id": "a", "company": "A", "source": "lever", "board": "a"}]')
    assert await seed_targets(store, str(v1)) == 1

    await store.delete_target("a")  # the user removes a default
    v2 = tmp_path / "v2.json"
    v2.write_text(
        '[{"id": "a", "company": "A", "source": "lever", "board": "a"},'
        ' {"id": "b", "company": "B", "source": "ashby", "board": "b"}]'
    )
    assert await seed_targets(store, str(v2)) == 1  # only the new default "b"
    assert [t.id for t in await store.list_targets()] == ["b"]
