"""Integrazione del flusso TypeScript: vitest + fast-check in sandbox."""

import pytest

from assist.llm.base import LLMClient
from assist.verification.pipeline import VerificationPipeline
from assist.verification.ts_runner import ts_available

pytestmark = pytest.mark.skipif(
    not ts_available(),
    reason="runtime TS non disponibile",
)

BUGGY_TS = """export function applyDiscount(
  price: number,
  percent: number
): number {
  if (percent > 100) percent = 100;
  return price + (price * percent) / 100;
}
"""

WEAK_TESTS_TS = """import { it, expect } from "vitest";
import { applyDiscount } from "./pricing";

it("zero percent", () => {
  expect(applyDiscount(100, 0)).toBe(100);
});
"""

PROPERTY_TS = """```typescript
import { it } from "vitest";
import fc from "fast-check";
import { applyDiscount } from "./pricing";

it("uno sconto non aumenta mai il prezzo", () => {
  fc.assert(
    fc.property(
      fc.integer({ min: 1, max: 10000 }),
      fc.integer({ min: 0, max: 100 }),
      (price, percent) => applyDiscount(price, percent) <= price
    )
  );
});
```"""


class _ScriptedLLM(LLMClient):
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, prompt: str, system: str = "") -> str:
        return self.responses.pop(0) if self.responses else "niente"


def test_ts_property_catches_bug_missed_by_unit_test(tmp_path):
    (tmp_path / "pricing.ts").write_text(BUGGY_TS, encoding="utf-8")
    (tmp_path / "pricing.test.ts").write_text(
        WEAK_TESTS_TS, encoding="utf-8"
    )

    pipeline = VerificationPipeline(
        # 1a risposta: boundary (non valida), 2a: property valida
        fast_llm=_ScriptedLLM(["niente codice", PROPERTY_TS]),
        strong_llm=_ScriptedLLM(["Spiegazione."]),
    )

    result = pipeline.run(file_path=str(tmp_path / "pricing.ts"))

    evidence = result.evidence

    # discovery automatica del test TS
    assert evidence.discovered_tests_path.endswith("pricing.test.ts")

    # il test-bugia passa, la proprieta' falsifica il bug
    assert evidence.baseline_tests is not None
    assert evidence.baseline_tests.passed
    assert evidence.property_tests is not None
    assert not evidence.property_tests.passed
    assert result.verdict.status == "fail"


def test_ts_evidence_only_pass(tmp_path):
    from assist.llm.null_client import NullLLMClient

    (tmp_path / "pricing.ts").write_text(BUGGY_TS, encoding="utf-8")
    (tmp_path / "pricing.test.ts").write_text(
        WEAK_TESTS_TS, encoding="utf-8"
    )

    pipeline = VerificationPipeline(
        fast_llm=NullLLMClient(),
        strong_llm=NullLLMClient(),
    )

    result = pipeline.run(file_path=str(tmp_path / "pricing.ts"))

    assert result.evidence.baseline_tests is not None
    assert result.evidence.mutation is not None
    assert result.evidence.mutation.skipped_reason
    assert result.verdict.status == "pass"


FIXED_TS = """```typescript
export function applyDiscount(
  price: number,
  percent: number
): number {
  if (percent > 100) percent = 100;
  return price - (price * percent) / 100;
}
```"""

STRICT_TESTS_TS = """import { it, expect } from "vitest";
import { applyDiscount } from "./pricing";

it("half discount", () => {
  expect(applyDiscount(100, 50)).toBe(50);
});
"""


def test_ts_validated_fix_loop(tmp_path):
    """Il fix TS e' accettato solo dopo il pass di vitest in sandbox."""
    (tmp_path / "pricing.ts").write_text(BUGGY_TS, encoding="utf-8")
    (tmp_path / "pricing.test.ts").write_text(
        STRICT_TESTS_TS, encoding="utf-8"
    )

    pipeline = VerificationPipeline(
        fast_llm=_ScriptedLLM(["niente", "niente"]),
        strong_llm=_ScriptedLLM(
            # 1) spiegazione judge, 2) fix corretto per il loop
            ["Spiegazione.", FIXED_TS]
        ),
        max_fix_iterations=2,
    )

    result = pipeline.run(file_path=str(tmp_path / "pricing.ts"))

    assert result.verdict.status == "fail"
    assert result.verdict.fix_validated is True
    assert "price - (price * percent)" in result.verdict.proposed_fix


def test_ts_multifile_dependencies(tmp_path):
    """Gli import relativi TS vengono inclusi nella sandbox."""
    (tmp_path / "tax.ts").write_text(
        "export const RATE = 0.2;\n", encoding="utf-8"
    )
    (tmp_path / "net.ts").write_text(
        'import { RATE } from "./tax";\n'
        "export function net(x: number): number {\n"
        "  return x * (1 - RATE);\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "net.test.ts").write_text(
        'import { it, expect } from "vitest";\n'
        'import { net } from "./net";\n'
        'it("net", () => { expect(net(100)).toBe(80); });\n',
        encoding="utf-8",
    )

    from assist.llm.null_client import NullLLMClient

    pipeline = VerificationPipeline(
        fast_llm=NullLLMClient(),
        strong_llm=NullLLMClient(),
    )

    result = pipeline.run(file_path=str(tmp_path / "net.ts"))

    assert result.evidence.dependencies == ["tax.ts"]
    assert result.evidence.baseline_tests is not None
    assert result.evidence.baseline_tests.passed
    assert result.verdict.status == "pass"
