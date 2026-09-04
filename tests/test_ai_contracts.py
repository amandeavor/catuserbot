# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from userbot.core.ai.interface import AIRequestOptions
from userbot.core.ai.providers import (
    ClaudeProvider,
    GeminiProvider,
    OpenAIProvider,
    OllamaProvider,
)


@pytest.mark.asyncio
async def test_openai_contract_schema_and_response_parsing():
    """Verify OpenAI REST contract (request headers, payload, and response choices)."""
    provider = OpenAIProvider(api_key="sk-test-mock-key-12345")
    options = AIRequestOptions(
        prompt="Hello OpenAI",
        system_prompt="Be helpful",
        model_name="gpt-4o-mini",
        temperature=0.3,
    )

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "Hello from mock OpenAI"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        resp = await provider.complete(options)

        # Verify contract request format
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.openai.com/v1/chat/completions"
        assert call_args[1]["headers"]["Authorization"] == "Bearer sk-test-mock-key-12345"
        payload = call_args[1]["json"]
        assert payload["model"] == "gpt-4o-mini"
        assert payload["messages"][0] == {"role": "system", "content": "Be helpful"}
        assert payload["messages"][1] == {"role": "user", "content": "Hello OpenAI"}

        # Verify parsed response
        assert resp.text == "Hello from mock OpenAI"
        assert resp.usage["prompt_tokens"] == 12


@pytest.mark.asyncio
async def test_claude_contract_schema_and_response_parsing():
    """Verify Anthropic Claude REST contract (headers, payload, and content blocks)."""
    provider = ClaudeProvider(api_key="ant-mock-key-54321")
    options = AIRequestOptions(
        prompt="Hello Claude",
        system_prompt="You are an expert",
        model_name="claude-3-5-sonnet-20241022",
    )

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "content": [{"type": "text", "text": "Hello from mock Claude"}],
        "usage": {"input_tokens": 15, "output_tokens": 6},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        resp = await provider.complete(options)

        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.anthropic.com/v1/messages"
        assert call_args[1]["headers"]["x-api-key"] == "ant-mock-key-54321"
        assert call_args[1]["headers"]["anthropic-version"] == "2023-06-01"
        payload = call_args[1]["json"]
        assert payload["system"] == "You are an expert"
        assert payload["messages"][0]["content"] == "Hello Claude"

        assert resp.text == "Hello from mock Claude"
        assert resp.usage["prompt_tokens"] == 15


@pytest.mark.asyncio
async def test_gemini_contract_schema_and_response_parsing():
    """Verify Google Gemini v1beta REST contract."""
    provider = GeminiProvider(api_key="ai-mock-gemini-key")
    options = AIRequestOptions(
        prompt="Hello Gemini",
        system_prompt="Be concise",
        model_name="gemini-1.5-flash",
    )

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": "Hello from mock Gemini"}]
            }
        }],
        "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 4},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        resp = await provider.complete(options)

        call_args = mock_post.call_args
        assert "key=ai-mock-gemini-key" in call_args[0][0]
        assert "gemini-1.5-flash:generateContent" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["systemInstruction"]["parts"][0]["text"] == "Be concise"
        assert payload["contents"][0]["parts"][0]["text"] == "Hello Gemini"

        assert resp.text == "Hello from mock Gemini"
        assert resp.usage["prompt_tokens"] == 8


@pytest.mark.asyncio
async def test_ollama_contract_schema_and_response_parsing():
    """Verify local Ollama REST contract."""
    provider = OllamaProvider(base_url="http://127.0.0.1:11434")
    options = AIRequestOptions(
        prompt="Hello Ollama",
        model_name="llama3:latest",
    )

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "message": {"content": "Hello from local Ollama"},
        "prompt_eval_count": 20,
        "eval_count": 10,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        resp = await provider.complete(options)

        call_args = mock_post.call_args
        assert call_args[0][0] == "http://127.0.0.1:11434/api/chat"
        payload = call_args[1]["json"]
        assert payload["model"] == "llama3:latest"
        assert payload["messages"][0]["content"] == "Hello Ollama"

        assert resp.text == "Hello from local Ollama"
        assert resp.usage["prompt_tokens"] == 20
