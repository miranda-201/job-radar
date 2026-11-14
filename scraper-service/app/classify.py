"""Title-based classification of computer-science roles.

Aggregated sources (GitHub lists, startup boards) post every kind of role, so each
posting is tagged with a CS category, or rejected when it isn't a CS role.
Rules run in order; the first matching category wins.
"""

from __future__ import annotations

import re
from enum import Enum


class RoleCategory(str, Enum):
    SOFTWARE = "software"
    DATA_ML = "data_ml"
    CLOUD_INFRA = "cloud_infra"
    SECURITY = "security"


def _rx(*terms: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b", re.IGNORECASE)


# Roles that mention tech words but are not engineering/science roles.
_EXCLUDE = _rx(
    r"sales",
    r"marketing",
    r"recruit(?:ing|er|ment)",
    r"talent",
    r"account(?:ing|ant)",
    r"account executive",
    r"legal",
    r"paralegal",
    r"human resources",
    r"hr",
    r"business development",
    r"customer (?:success|support|service)",
    r"mechanical",
    r"civil",
    r"chemical",
    r"manufacturing",
    r"structural",
    r"supply chain",
    r"procurement",
    r"graphic design(?:er)?",
    r"content",
    r"communications",
    r"public relations",
)

_RULES: list[tuple[RoleCategory, re.Pattern[str]]] = [
    (
        RoleCategory.SECURITY,
        _rx(
            r"security",
            r"cyber ?security",
            r"cyber",
            r"infosec",
            r"appsec",
            r"penetration",
            r"red team",
            r"soc analyst",
        ),
    ),
    (
        RoleCategory.CLOUD_INFRA,
        _rx(
            r"cloud",
            r"dev ?ops",
            r"devsecops",
            r"sre",
            r"site reliability",
            r"infrastructure",
            r"platform engineer(?:ing)?",
            r"distributed systems",
            r"kubernetes",
            r"network engineer(?:ing)?",
            r"systems administrat(?:or|ion)",
            r"production engineer(?:ing)?",
        ),
    ),
    (
        RoleCategory.DATA_ML,
        _rx(
            r"data scien(?:ce|tist)",
            r"data engineer(?:ing)?",
            r"data analy(?:st|tics)",
            r"analytics engineer(?:ing)?",
            r"machine learning",
            r"ml",
            r"ai",
            r"artificial intelligence",
            r"deep learning",
            r"llms?",
            r"nlp",
            r"computer vision",
            r"(?:applied|research) scientist",
            r"business intelligence",
            r"data",
        ),
    ),
    (
        RoleCategory.SOFTWARE,
        _rx(
            r"software",
            r"swe",
            r"sde",
            r"developer",
            r"programmer",
            r"programming",
            r"full[- ]?stack",
            r"back[- ]?end",
            r"front[- ]?end",
            r"web",
            r"mobile",
            r"ios",
            r"android",
            r"embedded",
            r"firmware",
            r"game (?:engineer|programmer|developer)",
            r"quant(?:itative)? (?:developer|engineer)",
            r"computer science",
            r"computer engineering",
            r"engineering intern(?:ship)?",
            r"technology intern(?:ship)?",
            r"it intern(?:ship)?",
            r"information technology",
            r"qa",
            r"test automation",
            r"automation engineer",
        ),
    ),
]


def classify(title: str) -> RoleCategory | None:
    if _EXCLUDE.search(title):
        return None
    for category, pattern in _RULES:
        if pattern.search(title):
            return category
    return None


_INTERN = _rx(r"interns?", r"internships?", r"co-?ops?", r"apprentice(?:ship)?", r"summer analyst")


def looks_like_internship(title: str) -> bool:
    return _INTERN.search(title) is not None


class DegreeLevel(str, Enum):
    UNDERGRAD = "undergrad"  # open to bachelor's/associate's students
    GRADUATE = "graduate"  # Master's / PhD / MBA students only


_UNDERGRAD = _rx(r"undergrad(?:uate)?s?", r"bachelor'?s?", r"b\.?s\.?/m\.?s\.?", r"associate'?s degree")
_GRAD = re.compile(
    r"\b(?:ph\.?\s?d\.?s?|doctoral|doctorate|postdoc(?:toral)?|master'?s|masters|mba"
    r"|graduate (?:student|research|intern(?:ship)?|co-?op|level|program))\b",
    re.IGNORECASE,
)
_GRAD_ABBREV = re.compile(r"(?<![\w.])(?:MS|M\.S\.)(?![\w])")  # case-sensitive: "MS/PhD", "Intern (MS)"
_NEW_GRAD = _rx(r"new grad(?:uate)?s?", r"recent grad(?:uate)?s?")

_DEGREE_LABELS_UNDERGRAD = {"bachelor's", "associate's", "bachelors", "associates", "undergraduate"}
_DEGREE_LABELS_GRAD = {"master's", "masters", "phd", "mba", "doctorate"}


def degree_level(title: str, degrees: list[str] | None = None) -> DegreeLevel | None:
    """Who a posting is for. None means unknown (treated as open to undergrads).

    The title is written by the employer, so a degree named there wins ("PhD Intern",
    "Research Intern - BS/MS/PhD"). A list's degree tags are a fallback only: list
    maintainers tag generously, e.g. marking a "PhD Studentship" as open to Bachelor's.
    """
    if _UNDERGRAD.search(title):
        return DegreeLevel.UNDERGRAD
    cleaned = _NEW_GRAD.sub(" ", title)
    if _GRAD.search(cleaned) or _GRAD_ABBREV.search(cleaned):
        return DegreeLevel.GRADUATE
    labels = {d.strip().lower() for d in degrees or [] if d}
    if labels & _DEGREE_LABELS_UNDERGRAD:
        return DegreeLevel.UNDERGRAD
    if labels & _DEGREE_LABELS_GRAD:
        return DegreeLevel.GRADUATE
    return None
