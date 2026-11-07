"""Where a job is, how you would work it, and whether it fits a search you described.

Pure functions.

A job post says "Bangalore", "Bengaluru, Karnataka, India", "Remote - US", "Dubai (Hybrid)", or
"Munich or Remote (EU)". This reads those texts into a place (region, city) and a way of working
(remote, hybrid, onsite), and answers whether a post fits a *search profile*: the regions, cities
and ways of working you want. A listing whose place cannot be understood is not a match (better a
missed job than a wrong city), and `matches` says why, so a miss can be explained.

Regions are the app's own: India, Europe, USA, UAE / Middle East, and "Remote (Global)" (accept
remote jobs from anywhere).
"""

import re
from dataclasses import dataclass

INDIA, EUROPE, USA, GULF, GLOBAL = "India", "Europe", "USA", "UAE / Middle East", "Remote (Global)"
REMOTE, HYBRID, ONSITE = "Remote", "Hybrid", "Onsite"
WORLDWIDE = "*"

# canonical city -> other spellings. Typing any spelling in a search finds the others.
_INDIA_CITIES: dict[str, tuple[str, ...]] = {
    "bengaluru": ("bangalore", "bengalooru", "bengaluru urban"),
    "hyderabad": ("secunderabad", "cyberabad"),
    "pune": ("pimpri-chinchwad", "pimpri chinchwad"),
    "mumbai": ("bombay", "navi mumbai", "thane"),
    "delhi": ("new delhi",),
    "gurugram": ("gurgaon",),
    "noida": ("greater noida",),
    "ghaziabad": (),
    "faridabad": (),
    "chennai": ("madras",),
    "kolkata": ("calcutta",),
    "ahmedabad": (),
    "gandhinagar": (),
    "jaipur": (),
    "kochi": ("cochin", "ernakulam"),
    "thiruvananthapuram": ("trivandrum",),
    "coimbatore": (),
    "indore": (),
    "chandigarh": ("mohali", "panchkula"),
    "nagpur": (),
    "lucknow": (),
    "bhubaneswar": (),
    "mysuru": ("mysore",),
    "vadodara": ("baroda",),
    "surat": (),
    "visakhapatnam": ("vizag",),
    "mangaluru": ("mangalore",),
    "nashik": (),
    "bhopal": (),
    "patna": (),
}
# A group a person might type that stands for several cities.
CITY_GROUPS: dict[str, tuple[str, ...]] = {
    "delhi ncr": ("delhi", "gurugram", "noida", "ghaziabad", "faridabad"),
    "ncr": ("delhi", "gurugram", "noida", "ghaziabad", "faridabad"),
}
_GULF_CITIES: dict[str, tuple[str, ...]] = {
    "dubai": (),
    "abu dhabi": (),
    "sharjah": (),
    "riyadh": (),
    "jeddah": (),
    "doha": (),
    "manama": (),
    "muscat": (),
    "kuwait city": (),
}
_EUROPE_CITIES: dict[str, tuple[str, ...]] = dict.fromkeys(
    (
        "london",
        "berlin",
        "munich",
        "hamburg",
        "frankfurt",
        "cologne",
        "amsterdam",
        "rotterdam",
        "dublin",
        "paris",
        "lyon",
        "madrid",
        "barcelona",
        "lisbon",
        "porto",
        "stockholm",
        "gothenburg",
        "copenhagen",
        "oslo",
        "helsinki",
        "warsaw",
        "krakow",
        "prague",
        "vienna",
        "zurich",
        "geneva",
        "brussels",
        "tallinn",
        "riga",
        "vilnius",
        "budapest",
        "bucharest",
        "sofia",
        "athens",
        "milan",
        "rome",
        "edinburgh",
        "manchester",
        "luxembourg",
    ),
    (),
)
_USA_CITIES: dict[str, tuple[str, ...]] = {
    "new york": ("nyc", "brooklyn"),
    "san francisco": ("sf bay area", "bay area"),
    "seattle": (),
    "austin": (),
    "boston": (),
    "chicago": (),
    "los angeles": (),
    "san jose": (),
    "mountain view": (),
    "bellevue": (),
    "denver": (),
    "atlanta": (),
    "dallas": (),
    "houston": (),
    "washington": ("washington, d.c.", "washington dc"),
}

_GULF_WORDS = (
    "united arab emirates",
    "uae",
    "saudi arabia",
    "qatar",
    "bahrain",
    "oman",
    "kuwait",
    "middle east",
    "mena",
    "gcc",
)
_EUROPE_WORDS = (
    "europe",
    "emea",
    "eu",
    "united kingdom",
    "uk",
    "england",
    "scotland",
    "wales",
    "ireland",
    "germany",
    "france",
    "netherlands",
    "spain",
    "portugal",
    "italy",
    "sweden",
    "norway",
    "denmark",
    "finland",
    "poland",
    "czechia",
    "czech republic",
    "austria",
    "switzerland",
    "belgium",
    "estonia",
    "latvia",
    "lithuania",
    "romania",
    "bulgaria",
    "greece",
    "hungary",
    "croatia",
    "slovenia",
    "slovakia",
    "luxembourg",
)
_USA_WORDS = (
    "united states",
    "usa",
    "u.s.",
    "u.s.a.",
    "america",
    "americas",
    "north america",
)
_US_STATES = frozenset(
    (
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    )
)
_US_STATE_NAMES = (
    "california",
    "texas",
    "new york",
    "washington",
    "massachusetts",
    "virginia",
    "maryland",
    "colorado",
    "georgia",
    "illinois",
    "florida",
    "oregon",
    "north carolina",
    "arizona",
    "utah",
)

_WORLD = ("worldwide", "anywhere", "global", "any location", "all locations", "work from anywhere")
_APAC = ("apac", "asia", "asia pacific")


def _flat(*tables: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """spelling -> canonical city, for every table given."""
    out: dict[str, str] = {}
    for table in tables:
        for canonical, others in table.items():
            for spelling in (canonical, *others):
                out[spelling] = canonical
    return out


_CITY_REGION: dict[str, str] = {
    **dict.fromkeys(_INDIA_CITIES, INDIA),
    **dict.fromkeys(_GULF_CITIES, GULF),
    **dict.fromkeys(_EUROPE_CITIES, EUROPE),
    **dict.fromkeys(_USA_CITIES, USA),
}
_SPELLINGS = _flat(_INDIA_CITIES, _GULF_CITIES, _EUROPE_CITIES, _USA_CITIES)


def _word(text: str, word: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text) is not None


def canonical_city(text: str) -> str | None:
    """ "Bangalore" -> "bengaluru"; None when the text names no city we know."""
    folded = text.casefold().strip()
    if folded in _SPELLINGS:
        return _SPELLINGS[folded]
    for spelling in sorted(_SPELLINGS, key=len, reverse=True):  # longest first: "navi mumbai"
        if _word(folded, spelling):
            return _SPELLINGS[spelling]
    return None


def expand_cities(names: list[str]) -> set[str]:
    """The canonical cities a list of typed names stands for ("Delhi NCR" is five cities)."""
    wanted: set[str] = set()
    for name in names:
        folded = name.casefold().strip()
        if folded in CITY_GROUPS:
            wanted.update(CITY_GROUPS[folded])
        elif (city := canonical_city(folded)) is not None:
            wanted.add(city)
        elif folded:
            wanted.add(folded)  # a city we do not know: matched as written
    return wanted


@dataclass(frozen=True)
class Place:
    region: str | None
    city: str | None


def _region_of_text(folded: str) -> str | None:
    if _word(folded, "india"):
        return INDIA
    if any(_word(folded, w) for w in _GULF_WORDS):
        return GULF
    if any(_word(folded, w) for w in _USA_WORDS) or _word(folded, "us"):
        return USA
    if any(_word(folded, w) for w in _US_STATE_NAMES):
        return USA
    if any(_word(folded, w) for w in _EUROPE_WORDS):
        return EUROPE
    if re.search(
        r",\s*(" + "|".join(sorted(_US_STATES)) + r")\b", folded.upper().replace("·", ",")
    ):
        return USA
    return None


def places_of(location: str | None) -> list[Place]:
    """Every place a location text names ("Maryland; Virginia" is two, "Pune or Remote" is one)."""
    if not location or not location.strip():
        return []
    places: list[Place] = []
    for part in re.split(r"[;|/]| or | and ", location, flags=re.IGNORECASE):
        folded = part.casefold().strip(" -()")
        if not folded or folded in ("remote", "hybrid", "onsite", "on-site"):
            continue
        city = canonical_city(folded)
        region = _CITY_REGION.get(city) if city else None
        region = _region_of_text(folded) or region
        if region is None and city is None:
            continue
        places.append(Place(region, city))
    return places


def work_mode_of(location: str | None, remote: bool, title: str = "") -> str:
    """Hybrid if the post says so; remote if flagged or the text says so; else onsite."""
    text = f"{location or ''} {title}".casefold()
    if "hybrid" in text:
        return HYBRID
    if remote or _word(text, "remote") or "work from home" in text or "wfh" in text.split():
        return REMOTE
    return ONSITE


def remote_regions(location: str | None) -> set[str] | None:
    """Where a remote job may be worked from: {WORLDWIDE}, a set of regions, or None when the post
    does not say (a bare "Remote")."""
    folded = (location or "").casefold().strip(" -()")
    if folded in ("", "remote"):
        return None
    if any(w in folded for w in _WORLD):
        return {WORLDWIDE}
    regions = {p.region for p in places_of(location) if p.region}
    if any(_word(folded, w) for w in _APAC):
        regions.add(INDIA)
    if _word(folded, "emea"):
        regions.update({EUROPE, GULF})
    folded_region = _region_of_text(folded)
    if folded_region:
        regions.add(folded_region)
    return regions


@dataclass(frozen=True)
class SearchSpec:
    """One way of searching: all of it must hold. Several specs are alternatives."""

    regions: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    work_modes: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class Fit:
    ok: bool
    why: str


def matches(spec: SearchSpec, *, title: str, location: str | None, remote: bool) -> Fit:
    folded_title = title.casefold()
    if spec.keywords and not any(k.casefold() in folded_title for k in spec.keywords):
        return Fit(False, "the title has none of the words you asked for")
    if any(k.casefold() in folded_title for k in spec.exclude):
        return Fit(False, "the title has a word you excluded")
    mode = work_mode_of(location, remote, title)
    if spec.work_modes and mode not in spec.work_modes:
        return Fit(
            False, f"it is {mode.lower()}, not {' or '.join(m.lower() for m in spec.work_modes)}"
        )
    wanted = {r for r in spec.regions if r != GLOBAL}
    if mode == REMOTE:
        scope = remote_regions(location)
        if scope is None:
            return Fit(True, "remote; the post does not say where from")
        if WORLDWIDE in scope:
            return Fit(True, "remote from anywhere")
        if scope & wanted:
            return Fit(True, "remote within your regions")
        if not spec.regions:
            return Fit(True, "remote")
        return Fit(False, "remote, but only for " + (", ".join(sorted(scope)) or "another country"))
    places = places_of(location)
    if not places:
        return Fit(False, "the location is missing or not understood")
    in_region = [p for p in places if not spec.regions or p.region in wanted]
    if not in_region:
        return Fit(False, "it is not in the regions you chose")
    if spec.cities:
        cities = expand_cities(list(spec.cities))
        if not any(p.city in cities for p in in_region if p.city):
            return Fit(False, "it is not in the cities you chose")
    return Fit(True, "place and way of working fit")


def matches_any(specs: list[SearchSpec], *, title: str, location: str | None, remote: bool) -> bool:
    """True when there are no searches (nothing is filtered) or any one of them fits."""
    return not specs or any(
        matches(s, title=title, location=location, remote=remote).ok for s in specs
    )
