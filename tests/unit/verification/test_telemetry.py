import time

from assist.llm.mock_client import MockLLMClient
from assist.verification.telemetry import CountingLLM, Telemetry


def test_phases_measured_in_order() -> None:
    telemetry = Telemetry()

    with telemetry.phase("sintassi"):
        time.sleep(0.01)

    with telemetry.phase("semantica"):
        time.sleep(0.01)

    names = [phase.name for phase in telemetry.stats.phases]
    assert names == ["sintassi", "semantica"]
    assert all(
        phase.duration_seconds > 0 for phase in telemetry.stats.phases
    )


def test_counters_increment() -> None:
    telemetry = Telemetry()

    telemetry.count_sandbox_run()
    telemetry.count_sandbox_run()
    telemetry.count_llm_fast()
    telemetry.count_llm_strong()
    telemetry.count_llm_strong()
    telemetry.count_mutation_cache_hit()

    assert telemetry.stats.sandbox_runs == 2
    assert telemetry.stats.llm_calls_fast == 1
    assert telemetry.stats.llm_calls_strong == 2
    assert telemetry.stats.mutation_cache_hits == 1


def test_finish_computes_total_seconds() -> None:
    telemetry = Telemetry()

    with telemetry.phase("fase_1"):
        time.sleep(0.01)
    with telemetry.phase("fase_2"):
        time.sleep(0.01)

    stats = telemetry.finish()

    expected_total = sum(p.duration_seconds for p in stats.phases)
    assert stats.total_seconds == expected_total
    assert stats.total_seconds > 0


def test_summary_line_contains_numbers() -> None:
    telemetry = Telemetry()
    telemetry.count_sandbox_run()
    telemetry.count_sandbox_run()
    telemetry.count_llm_fast()
    telemetry.count_llm_strong()
    telemetry.count_llm_strong()
    telemetry.count_mutation_cache_hit()
    telemetry.stats.total_seconds = 12.3

    line = telemetry.stats.summary_line()

    assert "12.3s" in line
    assert "2 run" in line
    assert "1 fast" in line
    assert "2 strong" in line
    assert "1 hit" in line


def test_counting_llm_forwards_result_and_calls_callback() -> None:
    inner = MockLLMClient(fixture="risposta mock")
    calls: list[None] = []

    counting = CountingLLM(inner=inner, on_call=lambda: calls.append(None))

    result = counting.complete("prompt", system="system")

    assert result == "risposta mock"
    assert len(calls) == 1


def test_counting_llm_counts_multiple_calls() -> None:
    inner = MockLLMClient(fixture="ok")
    calls: list[None] = []

    counting = CountingLLM(inner=inner, on_call=lambda: calls.append(None))

    counting.complete("uno")
    counting.complete("due")
    counting.complete("tre")

    assert len(calls) == 3
