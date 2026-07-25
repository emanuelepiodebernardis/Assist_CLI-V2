"""Test per il modulo del certificato di verifica."""

import json
from datetime import datetime

import pytest

from assist.verification.certificate import (
    ASSIST_PREDICATE_TYPE,
    INTOTO_STATEMENT_TYPE,
    build_certificate,
    certificate_to_intoto_json,
    certificate_to_json,
    default_signing_key,
    load_certificate,
    load_intoto_statement,
    to_intoto_statement,
    verify_certificate,
)
from assist.verification.evidence import (
    EvidenceBundle,
    Mutant,
    MutantResult,
    MutationReport,
    SandboxResult,
    TestRunEvidence,
    Verdict,
    VerificationOutput,
)

SOURCE = """def is_adult(age):
    return age >= 18
"""


def _make_output() -> VerificationOutput:
    """Costruisce un VerificationOutput finto ma realistico."""
    sandbox = SandboxResult(exit_code=0, stdout="3 passed", duration_seconds=0.1)
    baseline = TestRunEvidence(
        label="baseline",
        passed=True,
        tests_collected=3,
        tests_failed=0,
        sandbox=sandbox,
    )

    mutants = [
        MutantResult(
            mutant=Mutant(
                mutant_id=1, lineno=2, description="cambia >= in >"
            ),
            killed=True,
        ),
        MutantResult(
            mutant=Mutant(
                mutant_id=2, lineno=2, description="off-by-one su 18"
            ),
            killed=True,
        ),
        MutantResult(
            mutant=Mutant(
                mutant_id=3, lineno=2, description="cambia True in False"
            ),
            killed=False,
        ),
        MutantResult(
            mutant=Mutant(
                mutant_id=4, lineno=2, description="rimuove il return"
            ),
            killed=False,
        ),
    ]
    mutation = MutationReport(
        total_mutants=4,
        killed=2,
        survived=2,
        mutation_score=0.5,
        surviving_mutants=[m for m in mutants if not m.killed],
    )

    evidence = EvidenceBundle(
        target_file="src/target.py",
        module_name="target",
        syntax_ok=True,
        baseline_tests=baseline,
        boundary_tests=None,
        mutation=mutation,
        dependencies=["typing"],
        notes=["mutation score sotto la soglia consigliata"],
    )

    verdict = Verdict(
        status="warn",
        reasons=["mutation score 0.50 sotto la soglia 0.80"],
        explanation="I test coprono il caso base ma non i limiti.",
        fix_validated=False,
        mutation_score=0.5,
    )

    return VerificationOutput(verdict=verdict, evidence=evidence)


def test_build_certificate_populates_payload() -> None:
    output = _make_output()

    cert = build_certificate(output, SOURCE)

    payload = cert.payload
    assert payload.target_file == "src/target.py"
    assert len(payload.source_sha256) == 64
    assert all(c in "0123456789abcdef" for c in payload.source_sha256)
    assert payload.verdict_status == "warn"
    assert payload.verdict_reasons == [
        "mutation score 0.50 sotto la soglia 0.80"
    ]
    assert payload.mutation_score == 0.5
    assert payload.mutants_total == 4
    assert payload.mutants_killed == 2
    assert payload.tests_baseline_collected == 3
    assert payload.tests_baseline_failed == 0
    assert payload.tests_boundary_collected == 0
    assert payload.tests_boundary_failed == 0
    assert payload.fix_validated is False
    assert payload.dependencies == ["typing"]
    assert payload.notes == ["mutation score sotto la soglia consigliata"]

    # generated_at deve essere un ISO 8601 parsabile.
    datetime.fromisoformat(payload.generated_at)


def test_build_certificate_without_signing_key_has_empty_signature() -> None:
    output = _make_output()

    cert = build_certificate(output, SOURCE)

    assert cert.signature == ""


def test_build_certificate_with_signing_key_produces_valid_signature() -> None:
    output = _make_output()

    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")

    assert cert.signature != ""
    assert verify_certificate(cert, "s3gr3t0") is True


def test_verify_certificate_fails_on_tampered_payload() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")

    cert.payload.verdict_status = "fail"

    assert verify_certificate(cert, "s3gr3t0") is False


def test_verify_certificate_fails_with_wrong_key() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")

    assert verify_certificate(cert, "chiave-sbagliata") is False


def test_verify_certificate_fails_without_signature() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE)

    assert verify_certificate(cert, "qualsiasi-chiave") is False


def test_roundtrip_json_serialization() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")

    json_text = certificate_to_json(cert)
    loaded = load_certificate(json_text)

    assert loaded == cert
    assert verify_certificate(loaded, "s3gr3t0") is True


def test_load_certificate_raises_on_invalid_json() -> None:
    with pytest.raises(ValueError):
        load_certificate("{questo non e' json valido")


def test_load_certificate_raises_on_invalid_schema() -> None:
    with pytest.raises(ValueError):
        load_certificate("{}")


def test_default_signing_key_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASSIST_SIGNING_KEY", raising=False)
    assert default_signing_key() is None

    monkeypatch.setenv("ASSIST_SIGNING_KEY", "chiave-env")
    assert default_signing_key() == "chiave-env"


def test_to_intoto_statement_has_correct_shape() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")

    statement = to_intoto_statement(cert)

    assert statement["_type"] == INTOTO_STATEMENT_TYPE
    assert statement["predicateType"] == ASSIST_PREDICATE_TYPE
    assert statement["subject"] == [
        {
            "name": cert.payload.target_file,
            "digest": {"sha256": cert.payload.source_sha256},
        }
    ]
    predicate = statement["predicate"]
    assert "target_file" not in predicate
    assert "source_sha256" not in predicate
    assert predicate["verdict_status"] == "warn"
    assert predicate["signature"] == cert.signature
    assert predicate["signature_algorithm"] == cert.signature_algorithm


def test_to_intoto_statement_without_signature_omits_signature_keys() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE)

    statement = to_intoto_statement(cert)

    predicate = statement["predicate"]
    assert "signature" not in predicate
    assert "signature_algorithm" not in predicate


def test_intoto_roundtrip_verifies_signature() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")

    json_text = certificate_to_intoto_json(cert)
    loaded = load_intoto_statement(json_text)

    assert loaded.payload == cert.payload
    assert loaded.signature == cert.signature
    assert verify_certificate(loaded, "s3gr3t0") is True


def test_intoto_roundtrip_without_signature_fails_verification() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE)

    json_text = certificate_to_intoto_json(cert)
    loaded = load_intoto_statement(json_text)

    assert loaded.signature == ""
    assert verify_certificate(loaded, "qualsiasi-chiave") is False


def test_load_intoto_statement_detects_tampered_digest() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")

    statement = to_intoto_statement(cert)
    statement["subject"][0]["digest"]["sha256"] = "0" * 64

    loaded = load_intoto_statement(json.dumps(statement))

    assert verify_certificate(loaded, "s3gr3t0") is False


def test_load_intoto_statement_raises_on_wrong_type() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")
    statement = to_intoto_statement(cert)
    statement["_type"] = "https://example.com/Statement/v0"

    with pytest.raises(ValueError):
        load_intoto_statement(json.dumps(statement))


def test_load_intoto_statement_raises_on_wrong_predicate_type() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")
    statement = to_intoto_statement(cert)
    statement["predicateType"] = "https://example.com/other/v1"

    with pytest.raises(ValueError):
        load_intoto_statement(json.dumps(statement))


def test_load_intoto_statement_raises_on_missing_subject() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")
    statement = to_intoto_statement(cert)
    statement["subject"] = []

    with pytest.raises(ValueError):
        load_intoto_statement(json.dumps(statement))


def test_load_intoto_statement_raises_on_malformed_subject() -> None:
    output = _make_output()
    cert = build_certificate(output, SOURCE, signing_key="s3gr3t0")
    statement = to_intoto_statement(cert)
    statement["subject"] = [{"name": "src/target.py"}]

    with pytest.raises(ValueError):
        load_intoto_statement(json.dumps(statement))


def test_load_intoto_statement_raises_on_invalid_json() -> None:
    with pytest.raises(ValueError):
        load_intoto_statement("{questo non e' json valido")
