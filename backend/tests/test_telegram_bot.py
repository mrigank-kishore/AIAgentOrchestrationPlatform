from types import SimpleNamespace
import uuid

import pytest

from app.messaging import telegram_bot
from app.services.workflow_service import WorkflowRunResult


class FakeMessage:
    def __init__(self):
        self.text = "hello"
        self.chat_id = 123
        self.chat = SimpleNamespace(type="private")
        self.replies = []

    async def reply_text(self, text):
        self.replies.append(text)


@pytest.mark.asyncio
async def test_telegram_message_handler(monkeypatch):
    message = FakeMessage()
    update = SimpleNamespace(message=message)

    class FakeSession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(telegram_bot, "async_session", lambda: FakeSession())

    async def fake_execute_workflow_run(user_message, channel, user_id, db):
        assert user_message == "hello"
        assert channel == "telegram"
        assert user_id == "123"
        return WorkflowRunResult(response="reply", workflow_run_id=uuid.uuid4())

    monkeypatch.setattr(telegram_bot, "execute_workflow_run", fake_execute_workflow_run)
    await telegram_bot.handle_message(update, SimpleNamespace())
    assert message.replies == ["reply"]


def test_clean_telegram_reply_removes_noisy_markdown():
    reply = telegram_bot.clean_telegram_reply(
        "## Title\n\n**Focus:** Something\n\n*   Item one\n\n\n\nIndented"
    )

    assert reply == "Title\n\nFocus: Something\n- Item one\n\nIndented"
