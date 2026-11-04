"""Test harness for the practice editor.

This one file is used in two places, so its behaviour is tested natively:
  - the browser loads it into Pyodide (see python-worker.js);
  - the API test suite imports it to check every problem's tests against a reference solution.
Standard library only.
"""

import contextlib
import io
import json
import math
import traceback

MAX_TEXT = 2000  # cap on any text sent back (actual value, messages, printed output)


def _clip(text):
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "... (truncated)"


def _normalise(value):
    """Round-trip through JSON so tuples become lists; raises TypeError for sets and the like."""
    return json.loads(json.dumps(value))


def _sort_key(value):
    return json.dumps(value, sort_keys=True)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def same(actual, expected, tolerance=0.0):
    """Strict deep equality: True is not 1, but 1 equals 1.0. `tolerance` allows float error."""
    if _is_number(actual) and _is_number(expected):
        if tolerance:
            return math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance)
        return actual == expected
    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual == expected
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            same(a, b, tolerance) for a, b in zip(actual, expected, strict=True)
        )
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            same(actual[k], expected[k], tolerance) for k in actual
        )
    return actual == expected


def _unordered(items):
    return sorted(items, key=_sort_key)


def _nested_unordered(groups):
    return _unordered([_unordered(group) for group in groups])


def equal(actual, expected, mode="exact"):
    if mode == "float":
        return same(actual, expected, tolerance=1e-6)
    if mode == "unordered":
        return isinstance(actual, list) and same(_unordered(actual), _unordered(expected))
    if mode == "unordered_nested":
        return (
            isinstance(actual, list)
            and all(isinstance(group, list) for group in actual)
            and same(_nested_unordered(actual), _nested_unordered(expected))
        )
    return same(actual, expected)


def run_test(source, entry, args_json, expected_json, mode="exact"):
    """Run one test in a fresh namespace. Returns a JSON string:
    {"status": "pass"|"fail"|"error", "actual": str, "message": str, "stdout": str}
    """
    out = io.StringIO()
    result = {"status": "error", "actual": "", "message": "", "stdout": ""}
    try:
        code = compile(source, "<solution>", "exec")
    except SyntaxError as exc:
        result["message"] = _clip(f"SyntaxError: {exc.msg} (line {exc.lineno})")
        return json.dumps(result)

    try:
        namespace = {"__name__": "__solution__"}
        with contextlib.redirect_stdout(out):
            exec(code, namespace)  # noqa: S102 - running the learner's own code is the point
            function = namespace.get(entry)
            if not callable(function):
                raise NameError(f"Define a function named {entry}")
            returned = function(*json.loads(args_json))
        actual = _normalise(returned)
    except Exception as exc:  # noqa: BLE001 - any failure in learner code is reported, not raised
        tail = traceback.format_exception_only(type(exc), exc)[-1].strip()
        result["message"] = _clip(tail)
        result["stdout"] = _clip(out.getvalue())
        return json.dumps(result)

    result["stdout"] = _clip(out.getvalue())
    result["actual"] = _clip(json.dumps(actual))
    result["status"] = "pass" if equal(actual, json.loads(expected_json), mode) else "fail"
    return json.dumps(result)
