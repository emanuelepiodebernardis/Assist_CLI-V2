from assist.llm.anthropic_client import AnthropicClient


client = AnthropicClient(
    model="claude-sonnet-4-6",
)

response = client.complete(
    prompt="Say hello in one short sentence."
)

print(response)