"""Provider integration contract tests. These check the exact HTTP requests BrandGuard sends and how it parses
responses, using a fake transport. They do NOT call a live model (no API key was available)."""
import json

import httpx
import pytest

from app.config import settings
from app.services import llm


@pytest.fixture()
def cfg():
    saved = {k: getattr(settings, k) for k in ("llm_provider", "llm_api_key", "llm_model", "llm_base_url")}

    def set_(**kw):
        for k, v in kw.items():
            object.__setattr__(settings, k, v)
    yield set_
    for k, v in saved.items():
        object.__setattr__(settings, k, v)


class FakePost:
    def __init__(self, response_json, status=200):
        self.calls = []
        self.response_json, self.status = response_json, status

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(self.status, json=self.response_json, request=httpx.Request("POST", url))


AI_JSON = {"findings": [{"category": "tone", "severity": "low", "passage": "Plan calmly",
                         "title": "Fine", "explanation": "Calm voice matches brand voice.", "evidence_ids": [],
                         "suggestion": None, "confidence": "low"}]}


def test_anthropic_request_shape_and_parsing(cfg, monkeypatch):
    cfg(llm_provider="anthropic", llm_api_key="test-key", llm_model="", llm_base_url="")
    fake = FakePost({"content": [{"type": "text", "text": json.dumps(AI_JSON)}]})
    monkeypatch.setattr(llm.httpx, "post", fake)
    out = llm.get_provider().complete("SYS", "USER")
    call = fake.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "test-key" and call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["json"]["model"] == "claude-haiku-5-5" and call["json"]["system"] == "SYS"
    assert call["json"]["messages"] == [{"role": "user", "content": "USER"}] and call["json"]["temperature"] == 0
    assert json.loads(out) == AI_JSON


def test_openai_compatible_request_shape(cfg, monkeypatch):
    cfg(llm_provider="openai", llm_api_key="k", llm_model="my-model", llm_base_url="https://llm.example/v1")
    fake = FakePost({"choices": [{"message": {"content": json.dumps(AI_JSON)}}]})
    monkeypatch.setattr(llm.httpx, "post", fake)
    llm.get_provider().complete("SYS", "USER")
    call = fake.calls[0]
    assert call["url"] == "https://llm.example/v1/chat/completions"
    assert call["headers"]["authorization"] == "Bearer k"
    assert call["json"]["model"] == "my-model" and call["json"]["response_format"] == {"type": "json_object"}
    assert call["json"]["messages"][0] == {"role": "system", "content": "SYS"}


def test_openai_requires_explicit_model(cfg):
    cfg(llm_provider="openai", llm_api_key="k", llm_model="")
    assert llm.get_provider() is None
    assert "BRANDGUARD_LLM_MODEL is required" in llm.ai_status()["message"]


def test_provider_without_key_is_reported_clearly(cfg):
    cfg(llm_provider="anthropic", llm_api_key="")
    st = llm.ai_status()
    assert st["enabled"] is False and "BRANDGUARD_LLM_API_KEY is not set" in st["message"]


def test_unknown_provider_reported(cfg):
    cfg(llm_provider="gemini", llm_api_key="k")
    assert "Unknown BRANDGUARD_LLM_PROVIDER" in llm.ai_status()["message"]


@pytest.mark.parametrize("status,body", [(401, {"error": "invalid key"}), (500, {"error": "boom"}), (200, {"choices": []})])
def test_provider_http_errors_fall_back_to_deterministic(cfg, monkeypatch, ws, status, body):
    cfg(llm_provider="openai", llm_api_key="k", llm_model="m")
    monkeypatch.setattr(llm.httpx, "post", FakePost(body, status))
    d = ws.audit_text("Get cheap plans today.")
    assert "failed" in d["latest_audit"]["ai_status"] and "deterministic results shown" in d["latest_audit"]["ai_status"]
    assert any(f["passage"] == "cheap" for f in d["findings"])
    assert "k" not in d["latest_audit"]["ai_status"].split("(")[0].split()  # key never echoed


def test_timeouts_fall_back(cfg, monkeypatch, ws):
    cfg(llm_provider="anthropic", llm_api_key="k")

    def boom(*a, **k):
        raise httpx.ReadTimeout("timed out")
    monkeypatch.setattr(llm.httpx, "post", boom)
    d = ws.audit_text("Get cheap plans today.")
    assert "ReadTimeout" in d["latest_audit"]["ai_status"]


def test_end_to_end_ai_finding_through_real_provider_path(cfg, monkeypatch, ws):
    cfg(llm_provider="anthropic", llm_api_key="k")
    monkeypatch.setattr(llm.httpx, "post", FakePost({"content": [{"type": "text", "text": json.dumps(AI_JSON)}]}))
    d = ws.audit_text("Plan calmly with Pulse.")
    ai = [f for f in d["findings"] if f["origin"] == "ai"]
    assert len(ai) == 1 and ai[0]["passage"] == "Plan calmly"
    assert d["latest_audit"]["ai_mode"] == "anthropic"
