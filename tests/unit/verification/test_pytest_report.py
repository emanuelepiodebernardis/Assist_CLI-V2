"""Test del parser JUnit XML in `assist.verification.pytest_report`."""

from assist.verification.pytest_report import parse_junit_xml
from assist.verification.sandbox import SandboxRunner

_XML_MIXED = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="3">
    <testcase classname="test_demo" name="test_ok_one" time="0.001" />
    <testcase classname="test_demo" name="test_ok_two" time="0.002" />
    <testcase classname="test_demo" name="test_broken" time="0.003">
      <failure message="assert 1 == 2">
        def test_broken():
        &gt;       assert 1 == 2
        E       assert 1 == 2
      </failure>
    </testcase>
  </testsuite>
</testsuites>
"""

_XML_MALFORMED = "<testsuites><testsuite><testcase></testsuite>"

_XML_WITH_SKIPPED = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="0" failures="0" skipped="1" tests="2">
    <testcase classname="test_demo" name="test_ok" time="0.001" />
    <testcase classname="test_demo" name="test_skipped" time="0.001">
      <skipped type="pytest.skip" message="non serve" />
    </testcase>
  </testsuite>
</testsuites>
"""

_XML_EMPTY_SUITE = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="0" failures="0" skipped="0" tests="0" />
</testsuites>
"""

_XML_COLLECTION_ERROR = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="1" failures="0" skipped="0" tests="0" />
</testsuites>
"""


def test_parse_mixed_outcomes_counts_and_message():
    report = parse_junit_xml(_XML_MIXED)

    assert report.parse_ok
    assert report.total == 3
    assert report.passed == 2
    assert report.failed == 1
    assert report.errors == 0
    assert len(report.cases) == 3

    passed_names = {c.name for c in report.cases if c.outcome == "passed"}
    assert passed_names == {"test_ok_one", "test_ok_two"}

    failed_case = next(c for c in report.cases if c.outcome == "failed")
    assert failed_case.name == "test_broken"
    assert failed_case.classname == "test_demo"
    assert "assert 1 == 2" in failed_case.message

    assert not report.all_passed


def test_parse_malformed_xml_sets_parse_ok_false():
    report = parse_junit_xml(_XML_MALFORMED)

    assert report.parse_ok is False
    assert report.parse_error != ""
    assert report.total == 0
    assert not report.all_passed


def test_parse_with_skipped_all_passed_true():
    report = parse_junit_xml(_XML_WITH_SKIPPED)

    assert report.parse_ok
    assert report.total == 2
    assert report.passed == 1
    assert report.skipped == 1
    assert report.failed == 0
    assert report.errors == 0
    assert report.all_passed


def test_empty_report_all_passed_false():
    report = parse_junit_xml(_XML_EMPTY_SUITE)

    assert report.parse_ok
    assert report.total == 0
    assert not report.all_passed


def test_collection_error_zero_testcases_counted_as_error():
    report = parse_junit_xml(_XML_COLLECTION_ERROR)

    assert report.parse_ok
    assert report.errors == 1
    assert not report.all_passed


def test_run_pytest_with_collect_report_real_sandbox():
    runner = SandboxRunner(timeout_seconds=30)
    junit_xml_out: list[str] = []

    result = runner.run_pytest(
        files={
            "calc.py": "def add(a, b):\n    return a + b\n",
            "test_calc.py": (
                "from calc import add\n\n"
                "def test_add_ok():\n"
                "    assert add(1, 2) == 3\n\n"
                "def test_add_wrong():\n"
                "    assert add(1, 2) == 999\n"
            ),
        },
        collect_report=True,
        junit_xml_out=junit_xml_out,
    )

    assert not result.ok
    assert len(junit_xml_out) == 1
    assert junit_xml_out[0] != ""

    report = parse_junit_xml(junit_xml_out[0])

    assert report.parse_ok
    assert report.total == 2
    assert report.passed == 1
    assert report.failed == 1

    failed_case = next(c for c in report.cases if c.outcome == "failed")
    assert failed_case.name == "test_add_wrong"
    assert failed_case.message != ""


def test_run_pytest_without_new_params_is_backward_compatible():
    runner = SandboxRunner(timeout_seconds=30)

    result = runner.run_pytest(
        files={
            "calc.py": "def add(a, b):\n    return a + b\n",
            "test_calc.py": (
                "from calc import add\n\n"
                "def test_add():\n    assert add(1, 2) == 3\n"
            ),
        }
    )

    assert result.ok
    assert result.exit_code == 0
