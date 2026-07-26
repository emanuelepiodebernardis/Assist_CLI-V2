"""Judge basato su evidenze.

Regola architetturale: lo STATUS del verdetto e' deciso in modo
deterministico dalle evidenze (test, mutanti, sandbox). Il modello
forte scrive solo spiegazione e fix proposto — non puo' ribaltare
un fallimento oggettivo. Questo elimina i falsi "pass" da
LLM-che-giudica-LLM.
"""

from assist.llm.base import LLMClient
from assist.verification.evidence import (
    EvidenceBundle,
    Verdict,
)

_SYSTEM = (
    "Sei un senior engineer che spiega i risultati di una verifica "
    "automatica del codice. Ricevi EVIDENZE oggettive (test eseguiti, "
    "mutation testing, errori). Non inventare problemi non presenti "
    "nelle evidenze. Sii conciso e concreto. Se e' richiesto un fix, "
    "fornisci il codice corretto in un blocco ```python```."
)

_PROMPT_TEMPLATE = """File verificato: {target_file}
Status deciso dalle evidenze: {status}

EVIDENZE:
{evidence_text}

Compiti:
1. Spiega in 3-6 frasi cosa dicono le evidenze e perche' contano,
   in linguaggio comprensibile anche a chi non e' developer.
2. {fix_instruction}
"""

_SYSTEM_NON_DEV = (
    "Spieghi il risultato di un controllo automatico a una persona che "
    "NON sa programmare (un \"vibe coder\" che chiede a un'AI di scrivere "
    "codice ma non sa leggerlo). Non usare gergo da programmatori e non "
    "citare termini tecnici interni della verifica automatica: parla "
    "solo in linguaggio quotidiano. Usa analogie di tutti i giorni — per "
    "esempio, il controllo di qualita' dei test e' come verificare che "
    "l'allarme antincendio suoni davvero quando c'e' un problema, non "
    "solo che sia attaccato al muro. Scrivi frasi brevi e dirette. Dai "
    "indicazioni pratiche su cosa chiedere all'AI di sistemare, senza "
    "dettagli implementativi. Se e' richiesto un fix, fornisci comunque "
    "il codice corretto in un blocco ```python``` (verra' applicato "
    "automaticamente da uno strumento, non serve che la persona lo "
    "legga)."
)

_PROMPT_TEMPLATE_NON_DEV = """File verificato: {target_file}
Status deciso dalle evidenze: {status}

EVIDENZE:
{evidence_text}

Compiti:
1. Spiega in 4-8 frasi semplici cosa e' stato controllato e cosa e'
   emerso, come lo spiegheresti a un cliente non tecnico.
2. Elenca in 1-3 punti "cosa rischi se pubblichi cosi'".
3. {fix_instruction}
"""


class EvidenceJudge:
    def __init__(
        self,
        llm: LLMClient,
        mutation_threshold: float = 0.60,
        audience: str = "dev",
        max_input_chars: int = 24000,
    ) -> None:
        """Inizializza il judge.

        ``max_input_chars`` limita la dimensione totale (sorgente incluso)
        del testo di evidenze inserito nel prompt inviato all'LLM forte.
        Il default 24000 e' coerente con un budget di ~4 caratteri per
        token (regola empirica per l'inglese/codice): un
        ``max_input_tokens`` di 6000 token corrisponde grosso modo a
        24000 caratteri. Chi chiama puo' passare un valore derivato
        direttamente da ``settings.max_input_tokens * 4`` per tenere i
        due limiti coerenti tra loro.
        """
        if audience not in ("dev", "non-dev"):
            raise ValueError(
                f"audience non valida: {audience!r} (attesi 'dev' o "
                "'non-dev')"
            )

        self.llm = llm
        self.mutation_threshold = mutation_threshold
        self.audience = audience
        self.max_input_chars = max_input_chars

    def judge(
        self,
        evidence: EvidenceBundle,
        source: str = "",
    ) -> Verdict:
        status, reasons = self._deterministic_status(evidence)

        mutation_score = (
            evidence.mutation.mutation_score
            if evidence.mutation and not evidence.mutation.skipped_reason
            else None
        )

        explanation, proposed_fix = self._explain(
            evidence, status, source
        )

        return Verdict(
            status=status,
            reasons=reasons,
            explanation=explanation,
            proposed_fix=proposed_fix,
            mutation_score=mutation_score,
        )

    def _deterministic_status(
        self,
        evidence: EvidenceBundle,
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []

        if not evidence.syntax_ok:
            reasons.append(
                f"Errore di sintassi: {evidence.syntax_error}"
            )
            return "fail", reasons

        if evidence.baseline_tests and not evidence.baseline_tests.passed:
            reasons.append(
                "I test esistenti falliscono in sandbox "
                f"({evidence.baseline_tests.tests_failed} falliti)."
            )
            return "fail", reasons

        if evidence.boundary_tests and not evidence.boundary_tests.passed:
            reasons.append(
                "I test sui boundary generati falliscono: il codice non "
                "gestisce correttamente i casi limite "
                f"({evidence.boundary_tests.tests_failed} falliti)."
            )
            return "fail", reasons

        if evidence.property_tests and not evidence.property_tests.passed:
            reasons.append(
                "Le proprieta' del codice sono violate: Hypothesis ha "
                "trovato controesempi concreti "
                f"({evidence.property_tests.tests_failed} proprieta' "
                "falsificate)."
            )
            return "fail", reasons

        mutation = evidence.mutation

        if mutation and not mutation.skipped_reason:
            if mutation.mutation_score < self.mutation_threshold:
                reasons.append(
                    f"Mutation score {mutation.mutation_score:.0%} sotto la "
                    f"soglia {self.mutation_threshold:.0%}: "
                    f"{mutation.survived} mutanti sopravvissuti — i test "
                    "non provano il comportamento reale."
                )
                return "warn", reasons

            reasons.append(
                f"Mutation score {mutation.mutation_score:.0%} "
                f"({mutation.killed}/{mutation.total_mutants} mutanti uccisi)."
            )

        no_tests = (
            evidence.baseline_tests is None
            and evidence.boundary_tests is None
            and evidence.property_tests is None
        )

        if no_tests:
            reasons.append(
                "Nessun test eseguito: verifica limitata alla sintassi."
            )
            return "warn", reasons

        reasons.append("Tutti i test eseguiti passano in sandbox.")
        return "pass", reasons

    def _explain(
        self,
        evidence: EvidenceBundle,
        status: str,
        source: str,
    ) -> tuple[str, str]:
        is_non_dev = self.audience == "non-dev"

        if status == "fail" and source:
            fix_instruction = (
                "Proponi il fix completo del file in un blocco ```python``` "
                "che faccia passare i test falliti."
            )
        else:
            fix_instruction = (
                "Non serve un fix: suggerisci al massimo un miglioramento."
            )

        system = _SYSTEM_NON_DEV if is_non_dev else _SYSTEM
        template = _PROMPT_TEMPLATE_NON_DEV if is_non_dev else _PROMPT_TEMPLATE

        # Per audience non-dev il sorgente serve nel prompt solo se
        # necessario per generare il fix (status fail e source presente):
        # un non-dev non lo legge e consuma token inutilmente.
        evidence_source = source if (not is_non_dev or status == "fail") else ""

        prompt = template.format(
            target_file=evidence.target_file,
            status=status.upper(),
            evidence_text=self._render_evidence(
                evidence,
                evidence_source,
                audience=self.audience,
                max_input_chars=self.max_input_chars,
            ),
            fix_instruction=fix_instruction,
        )

        raw = self.llm.complete(prompt=prompt, system=system)

        proposed_fix = ""

        if status == "fail" and "```" in raw:
            import re

            match = re.search(
                r"```(?:python|py)?\s*\n(.*?)```", raw, re.DOTALL
            )
            if match:
                proposed_fix = match.group(1).strip()

        return raw.strip(), proposed_fix

    @staticmethod
    def _render_evidence(
        evidence: EvidenceBundle,
        source: str,
        audience: str = "dev",
        max_input_chars: int = 24000,
    ) -> str:
        is_non_dev = audience == "non-dev"
        parts: list[str] = []

        if not evidence.syntax_ok:
            parts.append(f"- SINTASSI: ERRORE — {evidence.syntax_error}")

        for label, run in (
            ("Test esistenti", evidence.baseline_tests),
            ("Test boundary generati", evidence.boundary_tests),
            ("Proprieta' (Hypothesis)", evidence.property_tests),
        ):
            if run is None:
                continue

            outcome = "PASSATI" if run.passed else "FALLITI"
            parts.append(
                f"- {label}: {outcome} "
                f"({run.tests_collected} raccolti, {run.tests_failed} falliti)"
            )

            if not run.passed and run.failure_summary:
                parts.append(f"  Dettaglio: {run.failure_summary[:1500]}")

        mutation = evidence.mutation

        if mutation:
            if mutation.skipped_reason:
                label = (
                    "Controllo qualita' dei test"
                    if is_non_dev
                    else "Mutation testing"
                )
                parts.append(f"- {label}: saltato ({mutation.skipped_reason})")
            else:
                if is_non_dev:
                    parts.append(
                        "- Controllo qualita' dei test: "
                        f"{mutation.mutation_score:.0%} (quota di problemi "
                        "simulati che i test hanno saputo rilevare)"
                    )
                else:
                    parts.append(
                        f"- Mutation testing: score {mutation.mutation_score:.0%} "
                        f"({mutation.killed}/{mutation.total_mutants} uccisi)"
                    )

                for mr in mutation.surviving_mutants[:8]:
                    tag = "NON RILEVATO" if is_non_dev else "SOPRAVVISSUTO"
                    parts.append(
                        f"  * {tag} riga {mr.mutant.lineno}: "
                        f"{mr.mutant.description} — `{mr.mutant.original_snippet}`"
                    )

        for note in evidence.notes:
            parts.append(f"- Nota: {note}")

        if source:
            truncated_source = source[: min(max_input_chars, len(source))]
            parts.append(
                f"\nSorgente del file:\n```python\n{truncated_source}\n```"
            )

        rendered = "\n".join(parts)

        if len(rendered) > max_input_chars:
            truncation_note = "\n...(evidenze troncate)"
            cutoff = max(max_input_chars - len(truncation_note), 0)
            rendered = rendered[:cutoff] + truncation_note

        return rendered
