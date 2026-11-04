from careerpilot.modules.tracker.identity import canonical_url, job_fingerprint, normalize_company


def test_company_names_match_across_legal_suffixes_and_case() -> None:
    assert normalize_company("Mareana Software India Pvt. Ltd.") == "mareana software india"
    assert normalize_company("  MAREANA  software india ") == "mareana software india"
    assert normalize_company("Acme Inc") == normalize_company("acme")
    # a name made only of suffix words keeps its last word instead of becoming empty
    assert normalize_company("Limited") == "limited"


def test_url_tracking_parameters_do_not_change_identity() -> None:
    plain = "https://boards.greenhouse.io/acme/jobs/123"
    tracked = "http://Boards.Greenhouse.io/acme/jobs/123/?utm_source=x&gclid=1#apply"
    assert canonical_url(plain) == canonical_url(tracked)


def test_url_parameters_that_identify_a_job_are_kept() -> None:
    assert canonical_url("https://x.com/jobs?gh_jid=1") != canonical_url(
        "https://x.com/jobs?gh_jid=2"
    )


def test_fingerprint_ignores_case_spacing_and_company_suffix() -> None:
    a = job_fingerprint("Acme Pvt Ltd", "Backend  Engineer", "Bengaluru", None)
    b = job_fingerprint("acme", "backend engineer", " bengaluru ", None)
    assert a == b
    assert a != job_fingerprint("acme", "frontend engineer", "bengaluru", None)
