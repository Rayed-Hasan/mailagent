"""OpenRouter response normalization tests, including Gemini text parts."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mailagent.llm.base import LLMMessage
from mailagent.llm.openrouter_provider import OpenRouterProvider


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content, expected",
    [
        ('{"reply":"Hello there."}', '{"reply":"Hello there."}'),
        ([{"type": "text", "text": '{"reply":"Hello '} , {"type": "text", "text": 'there."}'}], '{"reply":"Hello there."}'),
    ],
)
async def test_openrouter_normalizes_string_and_gemini_text_parts(content, expected):
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
    }
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)

    with patch("mailagent.llm.openrouter_provider.httpx.AsyncClient", return_value=context):
        result = await OpenRouterProvider("test-key").complete(
            [LLMMessage(role="user", content="Write a reply")],
            model="google/gemini-3.8-flash",
            response_schema={"type": "object"},
            json_mode=True,
        )

    assert result.text == expected
    payload = client.post.await_args.kwargs["json"]
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["schema"] == {"type": "object"}


@pytest.mark.asyncio
async def test_openrouter_rejects_malformed_assistant_message():
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"choices": [{"message": None}]}
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)

    with patch("mailagent.llm.openrouter_provider.httpx.AsyncClient", return_value=context):
        with pytest.raises(ValueError, match="malformed assistant message"):
            await OpenRouterProvider("test-key").complete(
                [LLMMessage(role="user", content="Write a reply")],
                model="google/gemini-3.8-flash",
            )
