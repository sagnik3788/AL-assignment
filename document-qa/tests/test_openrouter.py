import json

import httpx
import pytest

from app.config import Settings
from app.openrouter import OpenRouter, ProviderError


def provider_with(response_json=None, status=200):
    def handler(request):
        return httpx.Response(status, json=response_json or {}, request=request)

    provider = OpenRouter(Settings(openrouter_api_key="test-key", embedding_dimensions=2))
    provider.client.close()
    provider.client = httpx.Client(base_url="https://router.test/api/v1", transport=httpx.MockTransport(handler))
    return provider


def test_embedding_response_is_sorted_by_index():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [0, 1]},
            {"index": 0, "embedding": [1, 0]},
        ]}, request=request)

    provider = OpenRouter(Settings(openrouter_api_key="test-key", embedding_dimensions=2))
    provider.client.close()
    provider.client = httpx.Client(base_url="https://router.test/api/v1", transport=httpx.MockTransport(handler))
    try:
        assert provider.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]
        assert paths == ["/api/v1/embeddings"]
    finally:
        provider.close()


def test_answer_uses_chat_completions_path():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"answer": "Evidence.", "abstain": False, "citation_ids": ["chunk-1"]})}}]}, request=request)

    provider = OpenRouter(Settings(openrouter_api_key="test-key", embedding_dimensions=2))
    provider.client.close()
    provider.client = httpx.Client(base_url="https://router.test/api/v1", transport=httpx.MockTransport(handler))
    try:
        provider.answer("Question", [], [{"source_id": "chunk-1", "text": "Evidence"}])
        assert paths == ["/api/v1/chat/completions"]
    finally:
        provider.close()


def test_invalid_embedding_shape_is_sanitized():
    provider = provider_with({"data": [{"index": 0, "embedding": [1]}]})
    try:
        with pytest.raises(ProviderError, match="invalid embedding"):
            provider.embed(["text"])
    finally:
        provider.close()


def test_http_failure_does_not_surface_provider_body():
    provider = provider_with({"detail": "private provider payload"}, 500)
    try:
        with pytest.raises(ProviderError, match="temporarily unavailable") as error:
            provider.embed(["text"])
        assert "private provider payload" not in str(error.value)
    finally:
        provider.close()


def test_structured_answer_is_parsed():
    body = {"choices": [{"message": {"content": json.dumps({"answer": "From the source.", "abstain": False, "citation_ids": ["chunk-1"]})}}]}
    provider = provider_with(body)
    try:
        result = provider.answer("Question?", [], [{"source_id": "chunk-1", "text": "Evidence"}])
        assert result["citation_ids"] == ["chunk-1"]
    finally:
        provider.close()


def test_malformed_answer_is_rejected():
    provider = provider_with({"choices": [{"message": {"content": "not json"}}]})
    try:
        with pytest.raises(ProviderError, match="invalid answer"):
            provider.answer("Question?", [], [])
    finally:
        provider.close()
