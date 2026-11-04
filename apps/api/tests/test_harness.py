"""The Python test harness that runs in the browser (apps/web/public/runner/harness.py)."""

import json
from typing import Any

import pytest

from careerpilot.core.config import REPO_ROOT
from tests.test_problem_content import harness

CASES = json.loads(
    (REPO_ROOT / "apps" / "web" / "public" / "runner" / "compare-cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_comparison_modes_agree_with_the_shared_cases(case: dict[str, Any]) -> None:
    assert harness.equal(case["actual"], case["expected"], case["mode"]) is case["equal"]


def run(
    source: str, args: list[Any], expected: Any, entry: str = "f", mode: str = "exact"
) -> dict[str, Any]:
    return json.loads(harness.run_test(source, entry, json.dumps(args), json.dumps(expected), mode))


def test_pass_and_fail_report_the_actual_value() -> None:
    ok = run("def f(a, b):\n    return a + b\n", [2, 3], 5)
    assert ok["status"] == "pass" and ok["actual"] == "5"
    bad = run("def f(a, b):\n    return a + b\n", [2, 2], 5)
    assert bad["status"] == "fail" and bad["actual"] == "4"


def test_printed_output_is_captured_even_when_the_test_fails() -> None:
    result = run("def f():\n    print('debug line')\n    return 1\n", [], 2)
    assert result["status"] == "fail" and result["stdout"] == "debug line\n"


def test_tuples_come_back_as_lists() -> None:
    assert run("def f():\n    return (1, 2)\n", [], [1, 2])["status"] == "pass"


def test_syntax_error_names_the_line() -> None:
    result = run("def f(:\n    pass\n", [], 1)
    assert (
        result["status"] == "error"
        and "SyntaxError" in result["message"]
        and "line 1" in result["message"]
    )


def test_missing_function() -> None:
    result = run("def other():\n    pass\n", [], 1)
    assert (
        result["status"] == "error" and result["message"] == "NameError: Define a function named f"
    )


def test_exceptions_are_reported_not_raised() -> None:
    result = run("def f():\n    return 1 / 0\n", [], 1)
    assert (
        result["status"] == "error" and result["message"] == "ZeroDivisionError: division by zero"
    )


def test_results_that_are_not_json_are_an_error() -> None:
    result = run("def f():\n    return {1, 2}\n", [], 1)
    assert result["status"] == "error" and "not JSON serializable" in result["message"]


def test_module_level_code_runs_fresh_for_each_test() -> None:
    source = "counter = []\ndef f():\n    counter.append(1)\n    return len(counter)\n"
    assert run(source, [], 1)["status"] == "pass"
    assert run(source, [], 1)["status"] == "pass"  # not 2: no state is shared between tests


def test_long_output_is_truncated() -> None:
    result = run("def f():\n    print('x' * 10000)\n    return 1\n", [], 1)
    assert len(result["stdout"]) < 2100 and result["stdout"].endswith("(truncated)")
