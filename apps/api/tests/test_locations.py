"""Reading job locations and matching them against searches you describe.
# covers: the search conditions: work mode, cities with their other spellings, India only, abroad
"""

import pytest

from careerpilot.modules.discovery import locations as loc
from careerpilot.modules.discovery.locations import (
    EUROPE,
    GLOBAL,
    GULF,
    INDIA,
    USA,
    SearchSpec,
    matches,
    matches_any,
)


@pytest.mark.parametrize(
    ("text", "city", "region"),
    [
        ("Bangalore", "bengaluru", INDIA),
        ("Bengaluru, Karnataka, India", "bengaluru", INDIA),
        ("Gurgaon, Haryana", "gurugram", INDIA),
        ("Navi Mumbai", "mumbai", INDIA),
        ("Hyderabad / Secunderabad", "hyderabad", INDIA),
        ("Dubai, United Arab Emirates", "dubai", GULF),
        ("Munich, Germany", "munich", EUROPE),
        ("London, United Kingdom", "london", EUROPE),
        ("San Francisco, CA", "san francisco", USA),
        ("Austin, TX", "austin", USA),
        ("Amsterdam", "amsterdam", EUROPE),
    ],
)
def test_places_are_read_from_post_text(text: str, city: str, region: str) -> None:
    (place, *_) = loc.places_of(text)
    assert (place.city, place.region) == (city, region)


def test_a_state_code_and_a_country_without_a_city() -> None:
    assert loc.places_of("Boston, MA")[0].region == USA
    assert loc.places_of("India")[0] == loc.Place(INDIA, None)
    assert loc.places_of("Romania")[0].region == EUROPE  # "oman" inside "romania" is not Oman
    assert loc.places_of("Springfield") == []  # unknown: no guess
    assert loc.places_of(None) == [] and loc.places_of("  ") == []


def test_several_places_in_one_text_are_all_read() -> None:
    places = loc.places_of("Maryland; Virginia; Washington, D.C.")
    assert {p.region for p in places} == {USA}
    mixed = loc.places_of("Pune or Dubai")
    assert [p.city for p in mixed] == ["pune", "dubai"]


@pytest.mark.parametrize(
    ("location", "remote", "title", "mode"),
    [
        ("Bengaluru", False, "Engineer", loc.ONSITE),
        ("Bengaluru (Hybrid)", False, "Engineer", loc.HYBRID),
        ("Remote - US", False, "Engineer", loc.REMOTE),
        (None, True, "Engineer", loc.REMOTE),
        ("Pune", False, "Remote Backend Engineer", loc.REMOTE),
        ("Berlin", False, "Engineer (hybrid)", loc.HYBRID),
    ],
)
def test_the_way_of_working(location: str | None, remote: bool, title: str, mode: str) -> None:
    assert loc.work_mode_of(location, remote, title) == mode


def test_where_a_remote_job_can_be_done_from() -> None:
    assert loc.remote_regions("Anywhere in the World") == {loc.WORLDWIDE}
    assert loc.remote_regions("Worldwide") == {loc.WORLDWIDE}
    assert loc.remote_regions("Remote") is None
    assert loc.remote_regions("") is None
    assert loc.remote_regions("USA") == {USA}
    assert loc.remote_regions("APAC") == {INDIA}
    assert loc.remote_regions("EMEA") == {EUROPE, GULF}
    assert loc.remote_regions("Canada") == set()  # a place we know nothing of: not India


def test_typed_city_names_expand_to_every_spelling_and_groups() -> None:
    assert loc.expand_cities(["Bangalore", "Bombay"]) == {"bengaluru", "mumbai"}
    assert loc.expand_cities(["Delhi NCR"]) == {
        "delhi",
        "gurugram",
        "noida",
        "ghaziabad",
        "faridabad",
    }
    assert loc.expand_cities(["Springfield"]) == {"springfield"}


# --- searches ---------------------------------------------------------------------------------

INDIA_ONSITE = SearchSpec(
    regions=(INDIA,), cities=("Bangalore", "Hyderabad"), work_modes=("Hybrid", "Onsite")
)
INDIA_REMOTE = SearchSpec(regions=(INDIA,), work_modes=("Remote",))
GULF_ANY = SearchSpec(regions=(GULF,), cities=("Dubai",), work_modes=("Onsite", "Remote"))
ABROAD_REMOTE = SearchSpec(regions=(EUROPE, USA), work_modes=("Remote",))


def fit(spec: SearchSpec, title: str, location: str | None, remote: bool = False) -> bool:
    return matches(spec, title=title, location=location, remote=remote).ok


def test_bangalore_in_a_search_finds_bengaluru_posts_but_not_other_cities_or_countries() -> None:
    assert fit(INDIA_ONSITE, "Backend Engineer", "Bengaluru, Karnataka, India")
    assert fit(INDIA_ONSITE, "Backend Engineer", "Hyderabad (Hybrid)")
    assert not fit(INDIA_ONSITE, "Backend Engineer", "Pune, India")  # a city you did not choose
    assert not fit(INDIA_ONSITE, "Backend Engineer", "Berlin, Germany")  # not India
    assert not fit(
        INDIA_ONSITE, "Backend Engineer", "Bangalore", remote=True
    )  # you asked hybrid/onsite


def test_a_search_inside_india_for_remote_rejects_other_countries() -> None:
    assert fit(INDIA_REMOTE, "Data Engineer", "Anywhere in the World", remote=True)
    assert fit(INDIA_REMOTE, "Data Engineer", "India", remote=True)
    assert fit(INDIA_REMOTE, "Data Engineer", "APAC", remote=True)
    assert fit(
        INDIA_REMOTE, "Data Engineer", "Remote", remote=True
    )  # does not say: kept, but noted
    assert not fit(INDIA_REMOTE, "Data Engineer", "USA", remote=True)
    assert not fit(INDIA_REMOTE, "Data Engineer", "Remote - US", remote=True)
    assert not fit(INDIA_REMOTE, "Data Engineer", "Germany", remote=True)
    assert "only for" in matches(INDIA_REMOTE, title="x", location="USA", remote=True).why


def test_gulf_search_takes_dubai_onsite_or_remote_but_not_riyadh() -> None:
    assert fit(GULF_ANY, "Engineer", "Dubai, UAE")
    assert fit(GULF_ANY, "Engineer", "UAE", remote=True)
    assert not fit(GULF_ANY, "Engineer", "Riyadh, Saudi Arabia")  # in the region, not a chosen city


def test_abroad_remote_search_wants_remote_in_europe_or_the_usa() -> None:
    assert fit(ABROAD_REMOTE, "Engineer", "Germany", remote=True)
    assert fit(ABROAD_REMOTE, "Engineer", "USA", remote=True)
    assert fit(ABROAD_REMOTE, "Engineer", "Anywhere", remote=True)
    assert not fit(ABROAD_REMOTE, "Engineer", "Berlin")  # onsite
    assert not fit(ABROAD_REMOTE, "Engineer", "India", remote=True)


def test_keywords_and_exclusions_apply_to_the_title() -> None:
    spec = SearchSpec(regions=(INDIA,), keywords=("python", "backend"), exclude=("intern",))
    assert fit(spec, "Senior Backend Engineer", "Pune")
    assert not fit(spec, "Frontend Engineer", "Pune")
    assert not fit(spec, "Backend Intern", "Pune")


def test_an_unknown_location_is_not_matched_and_says_why() -> None:
    result = matches(INDIA_ONSITE, title="Engineer", location="Springfield", remote=False)
    assert not result.ok
    assert "not understood" in result.why
    assert not matches(INDIA_ONSITE, title="Engineer", location=None, remote=False).ok


def test_several_searches_are_alternatives_and_none_means_no_filter() -> None:
    specs = [INDIA_ONSITE, INDIA_REMOTE, GULF_ANY, ABROAD_REMOTE]
    assert matches_any(specs, title="Engineer", location="Munich", remote=True)
    assert matches_any(specs, title="Engineer", location="Dubai", remote=False)
    assert not matches_any(specs, title="Engineer", location="Sydney, Australia", remote=False)
    assert matches_any([], title="Engineer", location="Sydney", remote=False)


def test_global_remote_choice_is_accepted_as_a_region_name() -> None:
    spec = SearchSpec(regions=(GLOBAL,), work_modes=("Remote",))
    assert fit(spec, "Engineer", "Worldwide", remote=True)
    assert not fit(spec, "Engineer", "USA", remote=True)  # global means "from anywhere"
