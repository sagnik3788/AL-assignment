import json

import httpx

from app.config import Settings
from app.llm import OpenRouter


def test_openrouter_sends_structured_output_request():
    seen = {}

    def handler(request):
        seen["request"] = request
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"action":"quiz"}'}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = OpenRouter(Settings(openrouter_api_key="test-secret"), client)
    result = llm.complete_json(system="route", user="quiz me", schema_name="intent", schema={"type": "object"})
    assert result == {"action": "quiz"}
    request = seen["request"]
    assert request.url.path == "/api/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-secret"
    body = json.loads(request.content)
    assert body["temperature"] == 0
    assert body["response_format"]["json_schema"]["strict"] is True
    client.close()


def test_openrouter_retries_malformed_json_once():
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        body = "not json" if calls == 1 else '{"ok":true}'
        return httpx.Response(200, json={"choices": [{"message": {"content": body}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = OpenRouter(Settings(openrouter_api_key="test"), client).complete_json(system="s", user="u", schema_name="s", schema={})
    assert result == {"ok": True}
    assert calls == 2
    client.close()
