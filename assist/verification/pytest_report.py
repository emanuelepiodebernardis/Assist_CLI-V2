"""Parser strutturato per l'output JUnit XML di pytest.

Sostituisce il parsing a regex dell'output testuale di pytest con la
lettura del report XML prodotto dall'opzione built-in `--junit-xml`
(nessuna dipendenza esterna: si usa solo `xml.etree.ElementTree`
della standard library).

Il formato JUnit XML generato da pytest ha una delle due forme:

    <testsuites>
        <testsuite tests="..." failures="..." errors="..." skipped="...">
            <testcase classname="..." name="..." time="...">
                <failure message="...">...</failure>  (oppure <error>, <skipped>)
            </testcase>
        </testsuite>
    </testsuites>

oppure, direttamente:

    <testsuite ...>
        <testcase ...>...</testcase>
    </testsuite>

In caso di errore di collection senza alcun `<testcase>` (ad es. un
`conftest.py` rotto), il conteggio viene recuperato dagli attributi
del nodo `<testsuite>` (tests/failures/errors/skipped), così da non
perdere l'informazione che qualcosa e' andato storto.
"""

import xml.etree.ElementTree as ET
from typing import Literal

from pydantic import BaseModel, Field

_MESSAGE_MAX_LEN = 1500

Outcome = Literal["passed", "failed", "error", "skipped"]


class PytestCaseResult(BaseModel):
    """Esito di un singolo test case estratto dal report JUnit XML."""

    name: str
    classname: str = ""
    outcome: Outcome
    message: str = ""
    time_seconds: float = 0.0


class PytestReport(BaseModel):
    """Sintesi aggregata di un'esecuzione pytest, ricavata dal JUnit XML."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    cases: list[PytestCaseResult] = Field(default_factory=list)
    parse_ok: bool = True
    parse_error: str = ""

    @property
    def all_passed(self) -> bool:
        """True solo se ci sono test eseguiti e nessuno e' fallito o in errore."""
        return self.total > 0 and self.failed == 0 and self.errors == 0


def _extract_message(node: ET.Element) -> str:
    """Combina attributo `message` e testo del nodo (failure/error/skipped)."""

    msg_attr = (node.get("message") or "").strip()
    text = (node.text or "").strip()

    if msg_attr and text:
        message = f"{msg_attr}\n{text}"
    else:
        message = msg_attr or text

    return message[:_MESSAGE_MAX_LEN]


def _parse_testcase(testcase: ET.Element) -> PytestCaseResult:
    """Determina l'outcome di un `<testcase>` dai suoi figli."""

    name = testcase.get("name", "")
    classname = testcase.get("classname", "")

    try:
        time_seconds = float(testcase.get("time") or 0.0)
    except ValueError:
        time_seconds = 0.0

    failure = testcase.find("failure")
    error = testcase.find("error")
    skipped = testcase.find("skipped")

    outcome: Outcome
    message = ""

    if failure is not None:
        outcome = "failed"
        message = _extract_message(failure)
    elif error is not None:
        outcome = "error"
        message = _extract_message(error)
    elif skipped is not None:
        outcome = "skipped"
        message = _extract_message(skipped)
    else:
        outcome = "passed"

    return PytestCaseResult(
        name=name,
        classname=classname,
        outcome=outcome,
        message=message,
        time_seconds=time_seconds,
    )


def _int_attr(element: ET.Element, attr: str) -> int:
    """Legge un attributo intero di un nodo `<testsuite>`, tollerante a errori."""

    try:
        return int(element.get(attr) or 0)
    except ValueError:
        return 0


def parse_junit_xml(xml_text: str) -> PytestReport:
    """Analizza il contenuto di un report JUnit XML generato da pytest.

    Ritorna un `PytestReport` con i conteggi aggregati e la lista dei
    singoli test case. Se `xml_text` e' vuoto o malformato, ritorna un
    report con `parse_ok=False` e `parse_error` valorizzato, senza
    sollevare eccezioni.
    """

    if not xml_text or not xml_text.strip():
        return PytestReport(parse_ok=False, parse_error="XML vuoto")

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return PytestReport(parse_ok=False, parse_error=str(exc))

    if root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    elif root.tag == "testsuite":
        suites = [root]
    else:
        suites = list(root.findall(".//testsuite"))

    if not suites:
        return PytestReport(
            parse_ok=False,
            parse_error=f"Nessun nodo <testsuite> trovato (root: <{root.tag}>)",
        )

    report = PytestReport()

    for suite in suites:
        testcases = list(suite.findall("testcase"))

        if not testcases:
            # Errore di collection: nessun <testcase>, i conteggi vanno
            # recuperati dagli attributi del <testsuite> stesso.
            suite_tests = _int_attr(suite, "tests")
            suite_failures = _int_attr(suite, "failures")
            suite_errors = _int_attr(suite, "errors")
            suite_skipped = _int_attr(suite, "skipped")
            suite_passed = max(
                suite_tests - suite_failures - suite_errors - suite_skipped, 0
            )

            report.total += suite_tests
            report.failed += suite_failures
            report.errors += suite_errors
            report.skipped += suite_skipped
            report.passed += suite_passed
            continue

        for testcase in testcases:
            case = _parse_testcase(testcase)
            report.cases.append(case)
            report.total += 1

            if case.outcome == "passed":
                report.passed += 1
            elif case.outcome == "failed":
                report.failed += 1
            elif case.outcome == "error":
                report.errors += 1
            elif case.outcome == "skipped":
                report.skipped += 1

    return report
