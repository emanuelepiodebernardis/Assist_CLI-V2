"""Certificato di verifica: audit trail esportabile per compliance.

Il certificato serializza le evidenze deterministiche prodotte dalla
pipeline di verifica (Proof Engine) in un payload firmabile con
HMAC-SHA256, cosi' da poter dimostrare, anche fuori dal repository,
che un file e' stato verificato e con quale esito.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError

from assist.verification.evidence import VerificationOutput

TOOL_NAME = "assist-cli"
TOOL_VERSION = "4.5"
SCHEMA_VERSION = "1.0"
SIGNING_KEY_ENV_VAR = "ASSIST_SIGNING_KEY"


class CertificatePayload(BaseModel):
    """Contenuto verificabile del certificato di verifica.

    Riassume in forma stabile e serializzabile le evidenze prodotte
    dalla pipeline, cosi' da poter essere firmato e distribuito come
    prova di conformita'.
    """

    schema_version: str = SCHEMA_VERSION
    generated_at: str
    tool: str = TOOL_NAME
    tool_version: str = TOOL_VERSION
    target_file: str
    source_sha256: str
    verdict_status: str
    verdict_reasons: list[str] = Field(default_factory=list)
    mutation_score: float | None = None
    mutants_total: int = 0
    mutants_killed: int = 0
    tests_baseline_collected: int = 0
    tests_baseline_failed: int = 0
    tests_boundary_collected: int = 0
    tests_boundary_failed: int = 0
    fix_validated: bool = False
    dependencies: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VerificationCertificate(BaseModel):
    """Certificato di verifica, eventualmente firmato."""

    payload: CertificatePayload
    signature: str = ""
    signature_algorithm: str = "HMAC-SHA256"


def default_signing_key() -> str | None:
    """Legge la chiave di firma di default dalla variabile d'ambiente.

    Restituisce ``None`` se la variabile ``ASSIST_SIGNING_KEY`` non e'
    impostata.
    """
    return os.environ.get(SIGNING_KEY_ENV_VAR) or None


def _canonical_payload_json(payload: CertificatePayload) -> bytes:
    """Serializza il payload in JSON canonico per firma/verifica."""
    data = payload.model_dump()
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _sign_payload(payload: CertificatePayload, signing_key: str) -> str:
    """Calcola la firma HMAC-SHA256 esadecimale del payload canonico."""
    digest = hmac.new(
        signing_key.encode("utf-8"),
        _canonical_payload_json(payload),
        hashlib.sha256,
    )
    return digest.hexdigest()


def build_certificate(
    output: VerificationOutput,
    source: str,
    signing_key: str | None = None,
) -> VerificationCertificate:
    """Costruisce un certificato di verifica dalle evidenze raccolte.

    Il payload viene popolato a partire da ``output`` (verdetto ed
    evidenze) e dal ``source`` originale, di cui viene calcolato lo
    hash SHA-256. Se e' fornita una ``signing_key`` il certificato
    viene firmato con HMAC-SHA256; altrimenti la firma resta vuota.
    """
    evidence = output.evidence
    verdict = output.verdict

    baseline = evidence.baseline_tests
    boundary = evidence.boundary_tests
    mutation = evidence.mutation

    payload = CertificatePayload(
        generated_at=datetime.now(timezone.utc).isoformat(),
        target_file=evidence.target_file,
        source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        verdict_status=verdict.status,
        verdict_reasons=list(verdict.reasons),
        mutation_score=verdict.mutation_score,
        mutants_total=mutation.total_mutants if mutation else 0,
        mutants_killed=mutation.killed if mutation else 0,
        tests_baseline_collected=(
            baseline.tests_collected if baseline else 0
        ),
        tests_baseline_failed=baseline.tests_failed if baseline else 0,
        tests_boundary_collected=(
            boundary.tests_collected if boundary else 0
        ),
        tests_boundary_failed=boundary.tests_failed if boundary else 0,
        fix_validated=verdict.fix_validated,
        dependencies=list(evidence.dependencies),
        notes=list(evidence.notes),
    )

    signature = _sign_payload(payload, signing_key) if signing_key else ""

    return VerificationCertificate(payload=payload, signature=signature)


def verify_certificate(
    cert: VerificationCertificate, signing_key: str
) -> bool:
    """Verifica l'autenticita' del certificato con la chiave fornita.

    Ricalcola la firma HMAC-SHA256 sul payload del certificato e la
    confronta, con confronto a tempo costante, con quella presente.
    Un certificato privo di firma non e' mai considerato valido.
    """
    if not cert.signature:
        return False

    expected = _sign_payload(cert.payload, signing_key)
    return hmac.compare_digest(expected, cert.signature)


def certificate_to_json(cert: VerificationCertificate) -> str:
    """Serializza il certificato in JSON indentato pronto per il file."""
    return json.dumps(cert.model_dump(), indent=2, ensure_ascii=False)


def load_certificate(json_text: str) -> VerificationCertificate:
    """Carica e valida un certificato a partire dal testo JSON.

    Solleva ``ValueError`` con un messaggio chiaro se il testo non e'
    JSON valido o non rispetta lo schema del certificato.
    """
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON del certificato non valido: {exc}") from exc

    try:
        return VerificationCertificate.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"Schema del certificato non valido: {exc}"
        ) from exc
