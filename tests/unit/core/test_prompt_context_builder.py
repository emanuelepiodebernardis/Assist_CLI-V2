from assist.core.prompt_context_builder import (
    PromptContextBuilder,
)


def test_build_prompt_context():

    options = {
        "repository_context": {
            "related_files": [
                "auth.py",
            ],
        },
        "architecture_context": {
            "health_score": 0.8,
            "cyclic_dependencies": [],
        },
        "semantic_context": {
            "functions": [
                "login",
            ],
            "classes": [
                "AuthService",
            ],
            "imports": [
                "jwt",
            ],
            "calls": [
                "print",
            ],
        },
        "cross_file_context": {
            "imports": [
                {
                    "source": "a.py",
                    "target": "b.py",
                    "symbol": "os",
                },
            ],
            "function_calls": [
                {
                    "source": "a.py",
                    "target": "a.py",
                    "symbol": "print",
                },
            ],
        },
        "risk_context": {
            "risks": [
                {
                    "type": "high_coupling",
                    "severity": "high",
                    "file": "core.py",
                    "description": "Too many dependencies",
                },
            ],
        },
    }

    result = (
        PromptContextBuilder()
        .build(options)
    )

    assert "auth.py" in result

    assert "0.8" in result

    assert "login" in result

    assert "AuthService" in result

    assert "jwt" in result

    assert "print" in result

    assert "a.py" in result

    assert "b.py" in result

    assert "print" in result

    assert "high_coupling" in result

    assert "Too many dependencies" in result