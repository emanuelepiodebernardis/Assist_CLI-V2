"""Test per TsBoundaryTestAgent e TsPropertyTestAgent (test TS con LLM).

Copre le validazioni sull'output del modello (estrazione code-fence,
presenza/assenza di marker attesi, import dal modulo giusto, limiti di
conteggio) con un `MockLLMClient`, senza mai invocare `node`.

Include inoltre un unico test end-to-end REALE (l'unico che tocca
`node`) che dimostra come un property test fast-check scritto a mano
becchi un bug reale (`clamp` che ignora il limite superiore) tramite
`TsSandboxRunner`. Quel runner (`assist/verification/ts_runner.py`)
puo' non esistere ancora nel repo (e' costruito da un agente in
parallelo): il test viene quindi saltato se il modulo non e'
disponibile, invece di fallire la collection.
"""

import importlib.util

import pytest

from assist.llm.mock_client import MockLLMClient
from assist.verification.ts_test_agents import TsBoundaryTestAgent, TsPropertyTestAgent

# ---------------------------------------------------------------------
# TsBoundaryTestAgent
# ---------------------------------------------------------------------

BOUNDARY_VALID_RESPONSE = """Ecco i test:
```typescript
import { describe, it, expect } from "vitest";
import { add } from "./calc";

describe("add boundary", () => {
  it("handles zero", () => {
    expect(add(0, 0)).toBe(0);
  });

  it("handles negative numbers", () => {
    expect(add(-1, -1)).toBe(-2);
  });
});
```
"""

BOUNDARY_NO_VITEST_RESPONSE = """```typescript
import { describe, it, expect } from "mocha";
import { add } from "./calc";

it("adds", () => {
  expect(add(1, 2)).toBe(3);
});
```
"""

BOUNDARY_REQUIRE_RESPONSE = """```typescript
import { describe, it, expect } from "vitest";
import { add } from "./calc";
const helper = require("./helper");

it("adds", () => {
  expect(add(1, 2)).toBe(3);
});
```
"""

BOUNDARY_WRONG_MODULE_RESPONSE = """```typescript
import { describe, it, expect } from "vitest";
import { add } from "./other";

it("adds", () => {
  expect(add(1, 2)).toBe(3);
});
```
"""

BOUNDARY_TOO_MANY_TESTS_RESPONSE = """```typescript
import { describe, it, expect } from "vitest";
import { add } from "./calc";

it("case one", () => {
  expect(add(1, 2)).toBe(3);
});

it("case two", () => {
  expect(add(0, 0)).toBe(0);
});

it("case three", () => {
  expect(add(-1, -1)).toBe(-2);
});
```
"""


def test_boundary_extracts_fenced_code_with_expect():
    agent = TsBoundaryTestAgent(llm=MockLLMClient(fixture=BOUNDARY_VALID_RESPONSE))

    result = agent.generate(
        source="export function add(a: number, b: number): number {\n"
        "  return a + b;\n}\n",
        module_name="calc",
    )

    assert "expect(" in result
    assert "vitest" in result
    assert 'from "./calc"' in result


def test_boundary_response_without_vitest_returns_empty():
    agent = TsBoundaryTestAgent(llm=MockLLMClient(fixture=BOUNDARY_NO_VITEST_RESPONSE))

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_boundary_response_with_require_returns_empty():
    agent = TsBoundaryTestAgent(llm=MockLLMClient(fixture=BOUNDARY_REQUIRE_RESPONSE))

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_boundary_response_from_wrong_module_returns_empty():
    agent = TsBoundaryTestAgent(
        llm=MockLLMClient(fixture=BOUNDARY_WRONG_MODULE_RESPONSE)
    )

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_boundary_too_many_tests_returns_empty():
    agent = TsBoundaryTestAgent(
        llm=MockLLMClient(fixture=BOUNDARY_TOO_MANY_TESTS_RESPONSE),
        max_tests=2,
    )

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_boundary_invalid_output_returns_empty():
    agent = TsBoundaryTestAgent(llm=MockLLMClient(fixture="Non posso aiutarti."))

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


# ---------------------------------------------------------------------
# TsPropertyTestAgent
# ---------------------------------------------------------------------

PROPERTY_VALID_RESPONSE = """Ecco le proprieta':
```typescript
import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { add } from "./calc";

it("add is commutative", () => {
  fc.assert(
    fc.property(fc.integer(), fc.integer(), (a, b) => {
      expect(add(a, b)).toBe(add(b, a));
    }),
    { numRuns: 50 }
  );
});
```
"""

PROPERTY_NO_FAST_CHECK_RESPONSE = """```typescript
import { describe, it, expect } from "vitest";
import fc from "fc-lib";
import { add } from "./calc";

it("add is commutative", () => {
  fc.assert(
    fc.property(fc.integer(), fc.integer(), (a, b) => {
      expect(add(a, b)).toBe(add(b, a));
    })
  );
});
```
"""

PROPERTY_NO_FC_ASSERT_RESPONSE = """```typescript
import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { add } from "./calc";

it("add is commutative", () => {
  const arb = fc.property(fc.integer(), fc.integer(), (a, b) => {
    expect(add(a, b)).toBe(add(b, a));
  });
});
```
"""

PROPERTY_WRONG_MODULE_RESPONSE = """```typescript
import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { add } from "./other";

it("add is commutative", () => {
  fc.assert(
    fc.property(fc.integer(), fc.integer(), (a, b) => {
      expect(add(a, b)).toBe(add(b, a));
    })
  );
});
```
"""

PROPERTY_TOO_MANY_RESPONSE = """```typescript
import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { add } from "./calc";

it("property one", () => {
  fc.assert(
    fc.property(fc.integer(), (a) => {
      expect(add(a, 0)).toBe(a);
    })
  );
});

it("property two", () => {
  fc.assert(
    fc.property(fc.integer(), (a) => {
      expect(add(0, a)).toBe(a);
    })
  );
});
```
"""


def test_property_extracts_valid_test_with_fc_assert():
    agent = TsPropertyTestAgent(llm=MockLLMClient(fixture=PROPERTY_VALID_RESPONSE))

    result = agent.generate(
        source="export function add(a: number, b: number): number {\n"
        "  return a + b;\n}\n",
        module_name="calc",
    )

    assert "fc.assert" in result
    assert "fc.property" in result
    assert "fast-check" in result


def test_property_response_without_fast_check_returns_empty():
    agent = TsPropertyTestAgent(
        llm=MockLLMClient(fixture=PROPERTY_NO_FAST_CHECK_RESPONSE)
    )

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_property_response_without_fc_assert_returns_empty():
    agent = TsPropertyTestAgent(
        llm=MockLLMClient(fixture=PROPERTY_NO_FC_ASSERT_RESPONSE)
    )

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_property_response_from_wrong_module_returns_empty():
    agent = TsPropertyTestAgent(
        llm=MockLLMClient(fixture=PROPERTY_WRONG_MODULE_RESPONSE)
    )

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_property_too_many_properties_returns_empty():
    agent = TsPropertyTestAgent(
        llm=MockLLMClient(fixture=PROPERTY_TOO_MANY_RESPONSE),
        max_properties=1,
    )

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


def test_property_invalid_output_returns_empty():
    agent = TsPropertyTestAgent(llm=MockLLMClient(fixture="Non posso aiutarti."))

    result = agent.generate(source="export function add(a, b) {}", module_name="calc")

    assert result == ""


# ---------------------------------------------------------------------
# TsPropertyTestAgent.harden
# ---------------------------------------------------------------------


def test_harden_adds_configure_global_with_correct_num_runs():
    test_source = (
        'import fc from "fast-check";\n'
        'import { add } from "./calc";\n\n'
        'it("add is commutative", () => {\n'
        "  fc.assert(fc.property(fc.integer(), fc.integer(), (a, b) => {\n"
        "    add(a, b);\n"
        "  }));\n"
        "});\n"
    )

    hardened = TsPropertyTestAgent.harden(test_source, num_runs=77)

    assert "configureGlobal" in hardened
    assert "numRuns: 77" in hardened
    # Il sorgente originale resta intatto, solo prependuto.
    assert test_source in hardened


def test_harden_is_idempotent_when_num_runs_already_present():
    test_source = (
        'import fc from "fast-check";\n'
        'it("prop", () => {\n'
        "  fc.assert(fc.property(fc.integer(), (a) => {}), "
        "{ numRuns: 20 });\n"
        "});\n"
    )

    hardened = TsPropertyTestAgent.harden(test_source, num_runs=999)

    assert hardened == test_source
    assert "configureGlobal" not in hardened


# ---------------------------------------------------------------------
# Test end-to-end REALE: nessun LLM/mock coinvolto. Scriviamo a mano un
# modulo TS con una funzione bacata (`clamp` ignora il limite
# superiore) e il relativo property test fast-check, poi li eseguiamo
# con TsSandboxRunner reale (template /tmp/ts_template) per dimostrare
# che fast-check trova davvero il bug nella sandbox.
# ---------------------------------------------------------------------

_HAS_TS_RUNNER = (
    importlib.util.find_spec("assist.verification.ts_runner") is not None
)

BUGGY_TS_MODULE_SOURCE = """
export function clamp(v: number, lo: number, hi: number): number {
  // BACATA: non applica il limite superiore `hi`.
  if (v < lo) {
    return lo;
  }
  return v;
}
"""

TS_PROPERTY_TEST_SOURCE = """
import { it, expect } from "vitest";
import fc from "fast-check";
import { clamp } from "./clamp";

it("clamp stays within bounds", () => {
  fc.assert(
    fc.property(
      fc.integer({ min: -1000, max: 1000 }),
      fc.integer({ min: -1000, max: 1000 }),
      fc.integer({ min: -1000, max: 1000 }),
      (v, a, b) => {
        const lo = Math.min(a, b);
        const hi = Math.max(a, b);
        const result = clamp(v, lo, hi);
        expect(result).toBeGreaterThanOrEqual(lo);
        expect(result).toBeLessThanOrEqual(hi);
      }
    ),
    { numRuns: 50 }
  );
});
"""


@pytest.mark.skipif(
    not _HAS_TS_RUNNER,
    reason="assist.verification.ts_runner non ancora disponibile nel repo",
)
def test_end_to_end_fast_check_finds_real_bug_in_ts_sandbox():
    from assist.verification import ts_runner
    from assist.verification.ts_runner import (
        TsSandboxRunner,
        vitest_report_to_evidence,
    )

    # Il template di /tmp/ts_template e' il fallback usato da
    # `ts_template_dir` quando ne' la variabile d'ambiente
    # ASSIST_TS_TEMPLATE ne' ~/.assist/ts-template sono validi: si
    # azzera la cache di modulo per non dipendere dall'ordine di
    # esecuzione dei test.
    ts_runner.reset_ts_template_dir_cache()

    if not ts_runner.ts_available():
        pytest.skip("node/template TypeScript non disponibili in questo ambiente")

    runner = TsSandboxRunner(timeout_seconds=10)

    result, report = runner.run_vitest(
        files={
            "clamp.ts": BUGGY_TS_MODULE_SOURCE,
            "clamp.property.test.ts": TS_PROPERTY_TEST_SOURCE,
        }
    )

    evidence = vitest_report_to_evidence(report, result, label="clamp property")

    # La proprieta' su `clamp` deve fallire, perche' `clamp` non
    # rispetta il limite superiore `hi`.
    assert evidence.passed is False
