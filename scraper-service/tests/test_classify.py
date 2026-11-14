import pytest

from app.classify import RoleCategory, classify, looks_like_internship


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Software Engineer Intern", RoleCategory.SOFTWARE),
        ("SWE Intern - Summer 2027", RoleCategory.SOFTWARE),
        ("Full-Stack Developer Co-op", RoleCategory.SOFTWARE),
        ("iOS Engineering Intern", RoleCategory.SOFTWARE),
        ("Embedded Firmware Intern", RoleCategory.SOFTWARE),
        ("Machine Learning Engineer Intern", RoleCategory.DATA_ML),
        ("Data Science Intern", RoleCategory.DATA_ML),
        ("AI Research Scientist Intern", RoleCategory.DATA_ML),
        ("Data Engineering Intern", RoleCategory.DATA_ML),
        ("Cloud Infrastructure Intern", RoleCategory.CLOUD_INFRA),
        ("Site Reliability Engineer Intern", RoleCategory.CLOUD_INFRA),
        ("DevOps Intern", RoleCategory.CLOUD_INFRA),
        ("Cybersecurity Analyst Intern", RoleCategory.SECURITY),
        ("Software Engineer, Security", RoleCategory.SECURITY),
        # Not CS roles
        ("Sales Development Intern - AI Products", None),
        ("Mechanical Engineering Intern", None),
        ("Marketing Intern", None),
        ("Product Manager Intern", None),
        ("Electrical Engineer Intern - High Speed Hardware Design", None),
        ("Recruiting Coordinator Intern", None),
        # Word boundaries: "ai" must not match "maintenance", "ml" must not match "html"
        ("Facilities Maintenance Intern", None),
    ],
)
def test_classify(title, expected):
    assert classify(title) == expected


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Software Engineer Intern", True),
        ("Summer 2027 Internship - Data", True),
        ("Software Co-op", True),
        ("Engineering Coop (Fall)", True),
        ("Internal Tools Engineer", False),
        ("International Payments Engineer", False),
    ],
)
def test_looks_like_internship(title, expected):
    assert looks_like_internship(title) is expected


@pytest.mark.parametrize(
    "title,degrees,expected",
    [
        ("Software PhD Intern", None, "graduate"),
        ("Software Engineering Masters Intern", None, "graduate"),
        ("Applied Research Intern - MS/PhD", None, "graduate"),
        ("Ph.D. Research Intern, Generative AI", None, "graduate"),
        ("Graduate Research Intern", None, "graduate"),
        ("MBA Product Intern", None, "graduate"),
        ("Undergraduate Software Engineering Intern", None, "undergrad"),
        ("Software Engineer Intern (BS/MS)", None, "undergrad"),
        ("Software Engineer Intern", None, None),
        ("New Grad Software Engineer", None, None),  # "grad" here is not a degree requirement
        ("Microsoft Teams Platform Intern", None, None),  # "MS" only as a standalone token
        ("ML Intern", ["Master's", "PhD"], "graduate"),
        ("PhD Intern", ["Bachelor's", "Master's", "PhD"], "graduate"),  # the employer's title beats list tags
        ("PhD Studentship: Causal Reinforcement Learning", ["Bachelor's"], "graduate"),
        ("Research Intern - BS/MS/PhD", ["PhD"], "undergrad"),
        ("Data Intern", ["Bachelor's"], "undergrad"),
    ],
)
def test_degree_level(title, degrees, expected):
    from app.classify import degree_level

    result = degree_level(title, degrees)
    assert (result.value if result else None) == expected
