from assist.llm.mock_client import MockLLMClient


def test_mock_client_returns_fixture():
    client = MockLLMClient(
        fixture="hello world"
    )

    result = client.complete(
        prompt="Say hello"
    )

    assert result == "hello world"