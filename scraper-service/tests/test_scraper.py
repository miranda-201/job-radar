import httpx
import pytest

from app.models import JobPosting, SourceType, Target
from app.publisher import InMemoryPublisher
from app.scraper import ScrapeRunner
from app.store import InMemoryStore


class FakeSource:
    def __init__(self, postings=None, error: Exception | None = None):
        self.postings = postings or []
        self.error = error

    async def fetch(self, client, target):
        if self.error:
            raise self.error
        return self.postings


def posting(i: int, title: str = "Software Engineer Intern") -> JobPosting:
    return JobPosting(
        source=SourceType.GREENHOUSE, company="Acme", external_id=str(i), title=title, url=f"https://x/{i}"
    )


def target(tid: str = "acme") -> Target:
    return Target(id=tid, company="Acme", source=SourceType.GREENHOUSE, board=tid, keywords=["intern"])


@pytest.fixture
async def env():
    store, pub = InMemoryStore(), InMemoryPublisher()
    async with httpx.AsyncClient() as client:
        yield store, pub, client


async def test_publishes_only_new_matching_postings(env):
    store, pub, client = env
    await store.upsert_target(target())
    source = FakeSource([posting(1), posting(2), posting(3, "Senior Staff Engineer")])
    runner = ScrapeRunner(store, pub, client, source_lookup=lambda t: source)

    first = await runner.run_all()
    assert [r.new for r in first.results] == [2]
    assert first.results[0].matched == 2 and first.results[0].fetched == 3
    assert {e.externalId for e in pub.events} == {"1", "2"}

    # Second sweep: same postings plus one stealth drop -> only the drop is published.
    source.postings.append(posting(4))
    second = await runner.run_all()
    assert second.total_new == 1
    assert pub.events[-1].externalId == "4"
    assert pub.events[-1].eventType == "job.discovered"


async def test_one_failing_target_does_not_block_others(env):
    store, pub, client = env
    await store.upsert_target(target("broken"))
    await store.upsert_target(target("healthy"))
    sources = {"broken": FakeSource(error=httpx.ConnectTimeout("timeout")), "healthy": FakeSource([posting(1)])}
    runner = ScrapeRunner(store, pub, client, source_lookup=lambda t: sources[t.id])

    report = await runner.run_all()
    by_id = {r.target_id: r for r in report.results}
    assert "ConnectTimeout" in by_id["broken"].error
    assert by_id["healthy"].new == 1 and by_id["healthy"].error is None


async def test_publish_failure_rolls_back_dedup_so_job_is_retried(env):
    store, pub, client = env
    await store.upsert_target(target())
    runner = ScrapeRunner(store, pub, client, source_lookup=lambda t: FakeSource([posting(1)]))

    pub.fail_next = True
    failed = await runner.run_all()
    assert failed.results[0].error and failed.results[0].new == 0
    assert pub.events == []

    retried = await runner.run_all()
    assert retried.results[0].new == 1
    assert [e.externalId for e in pub.events] == ["1"]


async def test_disabled_targets_are_skipped(env):
    store, pub, client = env
    t = target()
    t.enabled = False
    await store.upsert_target(t)
    runner = ScrapeRunner(store, pub, client, source_lookup=lambda t: FakeSource([posting(1)]))
    report = await runner.run_all()
    assert report.results == []
