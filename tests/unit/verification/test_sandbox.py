from assist.verification.sandbox import SandboxRunner


def test_run_pytest_passing():
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


def test_run_pytest_failing():
    runner = SandboxRunner(timeout_seconds=30)

    result = runner.run_pytest(
        files={
            "calc.py": "def add(a, b):\n    return a - b\n",
            "test_calc.py": (
                "from calc import add\n\n"
                "def test_add():\n    assert add(1, 2) == 3\n"
            ),
        }
    )

    assert not result.ok
    assert result.exit_code != 0


def test_timeout_is_detected():
    runner = SandboxRunner(timeout_seconds=2)

    result = runner.run_script(
        files={"loop.py": "while True:\n    pass\n"},
        entry="loop.py",
    )

    assert result.timed_out
    assert not result.ok
