import pytest

from app.runtime.agent_node import GoogleChat
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


class FakeResponse:
    text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Gemini response"},
                        ]
                    }
                }
            ]
        }


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        FakeAsyncClient.last_url = url
        FakeAsyncClient.last_kwargs = kwargs
        return FakeResponse()


@pytest.mark.asyncio
async def test_google_chat_uses_gemini_generate_content(monkeypatch):
    monkeypatch.setattr("app.runtime.agent_node.httpx.AsyncClient", FakeAsyncClient)

    chat = GoogleChat(api_key="google-key", model="gemini-2.5-flash")
    response = await chat.ainvoke(
        [
            SystemMessage(content="Be concise."),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
    )

    assert response.content == "Gemini response"
    assert FakeAsyncClient.last_url == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )
    assert FakeAsyncClient.last_kwargs["headers"] == {"x-goog-api-key": "google-key"}
    assert FakeAsyncClient.last_kwargs["json"] == {
        "contents": [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"text": "Hi"}]},
        ],
        "systemInstruction": {"parts": [{"text": "Be concise."}]},
    }
