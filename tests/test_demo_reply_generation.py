"""Safe end-to-end demo reply tests using fictional mail and mocked AI."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

with patch("mailagent.core.database.Database.__init__", return_value=None):
    from mailagent.dashboard import app as dashboard
    from mailagent.core.config import settings
    from mailagent.llm.base import LLMResponse


def _response(reply_text):
    return LLMResponse(
        text=reply_text,
        provider="openrouter",
        model="google/gemini-3.8-flash",
        raw={},
    )


@pytest.mark.asyncio
async def test_fictional_message_saves_and_returns_complete_ai_reply():
    email = {
        "id": "fictional-email-1",
        "account_id": dashboard.get_demo_account_id(),
        "thread_id": None,
        "message_id": "fictional-message-1",
        "sender": "Casey Example <casey@example.invalid>",
        "sender_email": "casey@example.invalid",
        "subject": "Choose a meeting time",
        "body": "Would Tuesday or Thursday work better for you?",
    }
    reply = "Hi Casey,\n\nCould you share which day works best on your end?\n\nBest regards"
    mock_db = MagicMock()
    mock_db.get_email = AsyncMock(return_value=email)
    mock_db.get_classification = AsyncMock(return_value={"id": "classification-1"})
    mock_db.get_pending_drafts = AsyncMock(return_value=[])
    mock_db.save_draft = AsyncMock(return_value="draft-1")
    fake_request = MagicMock()
    fake_response = _response(json.dumps({"reply": reply}))

    with patch.object(settings, "public_demo_mode", True), \
         patch.object(dashboard, "db", mock_db), \
         patch.object(dashboard, "demo_gmail_provider", None), \
         patch.object(dashboard, "get_client_ip", AsyncMock(return_value="127.0.0.1")), \
         patch.object(dashboard.demo_rate_limiter, "release_request", AsyncMock()), \
         patch("mailagent.demo.demo_provider.complete_demo", AsyncMock(return_value=(fake_response, False))) as complete:
        result = await dashboard.generate_demo_draft(
            http_request=fake_request,
            draft_request=dashboard.DemoDraftRequest(email_id=email["id"]),
            user_id="demo-user-judge",
        )

    assert result["content"] == reply
    assert result["fallback"] is False
    assert result["draft_id"] == "draft-1"
    saved_draft = mock_db.save_draft.await_args.args[0]
    assert saved_draft.content == reply
    sent_prompt = complete.await_args.args[0][0].content
    assert email["body"] in sent_prompt
    assert "do not invent the owner's preference" in sent_prompt.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("model_text", ["", "not-json", '{"reply":"  "}', "{}"])
async def test_empty_or_malformed_model_reply_is_not_saved(model_text):
    email = {
        "id": "fictional-email-2",
        "account_id": dashboard.get_demo_account_id(),
        "thread_id": None,
        "subject": "Test",
        "body": "A fictional request?",
    }
    mock_db = MagicMock()
    mock_db.get_email = AsyncMock(return_value=email)
    mock_db.get_classification = AsyncMock(return_value={"id": "classification-2"})
    mock_db.save_draft = AsyncMock()

    with patch.object(settings, "public_demo_mode", True), \
         patch.object(dashboard, "db", mock_db), \
         patch.object(dashboard, "demo_gmail_provider", None), \
         patch.object(dashboard, "get_client_ip", AsyncMock(return_value="127.0.0.1")), \
         patch.object(dashboard.demo_rate_limiter, "release_request", AsyncMock()), \
         patch("mailagent.demo.demo_provider.complete_demo", AsyncMock(return_value=(_response(model_text), False))):
        with pytest.raises(HTTPException) as exc:
            await dashboard.generate_demo_draft(
                http_request=MagicMock(),
                draft_request=dashboard.DemoDraftRequest(email_id=email["id"]),
                user_id="demo-user-judge",
            )

    assert exc.value.status_code == 502
    mock_db.save_draft.assert_not_awaited()
