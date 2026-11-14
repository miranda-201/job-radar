from datetime import UTC, datetime, timedelta

import pytest

from app.models import SourceType, Target
from app.sources import greenhouse, lever, workday


def _target(source: SourceType, board: str = "acme") -> Target:
    return Target(id="acme", company="Acme", source=source, board=board, keywords=["intern"])


def test_greenhouse_parse_normalizes_fields():
    payload = {
        "jobs": [
            {
                "id": 8172508,
                "title": " Software Engineer Intern ",
                "absolute_url": "https://acme.com/jobs?gh_jid=8172508",
                "updated_at": "2026-10-29T10:42:09-04:00",
                "location": {"name": "Chicago, IL"},
            }
        ]
    }
    [job] = greenhouse.parse(payload, _target(SourceType.GREENHOUSE))
    assert job.external_id == "8172508"
    assert job.title == "Software Engineer Intern"
    assert job.location == "Chicago, IL"
    assert job.posted_at is not None and job.posted_at.year == 2026
    assert job.dedup_key == "greenhouse:acme:8172508"


def test_lever_parse_converts_epoch_millis():
    payload = [
        {
            "id": "6ed76ce8",
            "text": "Forward Deployed Engineer, Intern",
            "hostedUrl": "https://jobs.lever.co/acme/6ed76ce8",
            "createdAt": 1786469891368,
            "categories": {"location": "New York, NY"},
        }
    ]
    [job] = lever.parse(payload, _target(SourceType.LEVER))
    assert job.external_id == "6ed76ce8"
    assert job.posted_at.tzinfo is UTC
    assert job.location == "New York, NY"


@pytest.mark.parametrize(
    "url,expected_site",
    [
        ("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite", "NVIDIAExternalCareerSite"),
        ("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/", "NVIDIAExternalCareerSite"),
    ],
)
def test_workday_site_parsing(url, expected_site):
    site = workday.parse_site(url)
    assert site.tenant == "nvidia"
    assert site.site == expected_site
    assert site.api_url == f"https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/{expected_site}/jobs"


def test_workday_rejects_non_workday_url():
    with pytest.raises(ValueError):
        workday.parse_site("https://example.com/careers")


@pytest.mark.parametrize(
    "text,days",
    [("Posted Today", 0), ("Posted Yesterday", 1), ("Posted 3 Days Ago", 3), ("Posted 30+ Days Ago", 30)],
)
def test_workday_relative_dates(text, days):
    now = datetime(2026, 11, 14, 15, 30, tzinfo=UTC)
    midnight = datetime(2026, 11, 14, tzinfo=UTC)
    assert workday.parse_posted_on(text, now) == midnight - timedelta(days=days)


def test_workday_unknown_date_text_is_none():
    assert workday.parse_posted_on("Posted sometime") is None
    assert workday.parse_posted_on(None) is None


def test_workday_parse_builds_public_url_and_req_id():
    site = workday.parse_site("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")
    payload = {
        "jobPostings": [
            {
                "title": "Software Intern - 2027",
                "externalPath": "/job/US-CA-Santa-Clara/Software-Intern---2027_JR2027176",
                "locationsText": "US, CA, Santa Clara",
                "postedOn": "Posted Today",
            },
            {"title": "missing path is skipped"},
        ]
    }
    [job] = workday.parse(payload, _target(SourceType.WORKDAY, site.api_url), site)
    assert job.external_id == "JR2027176"
    assert job.url == (
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
        "/job/US-CA-Santa-Clara/Software-Intern---2027_JR2027176"
    )


def test_target_keyword_matching_is_case_insensitive():
    t = Target(id="x", company="X", source=SourceType.GREENHOUSE, board="x", keywords=["Intern", "new grad"])
    assert t.matches("Software Engineering INTERN, Summer 2027")
    assert t.matches("New Grad Backend Engineer")
    assert not t.matches("Staff Engineer")
    assert not t.matches("AI Engineer, Internal Tools")
    assert not t.matches("International Payments Engineer")
    assert t.matches("Software Engineering Interns (Summer)")
    assert Target(id="y", company="Y", source=SourceType.LEVER, board="y").matches("anything")


def test_target_rejects_bad_slug():
    with pytest.raises(ValueError):
        Target(id="Not A Slug", company="X", source=SourceType.LEVER, board="x")
