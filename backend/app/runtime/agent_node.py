import uuid
from typing import Any, Callable

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from sqlmodel import select

from app.core.config import settings
from app.core.database import async_session
from app.models.agent import Agent


@tool
def search_kb(query: str) -> str:
    """Search a tiny demo knowledge base."""
    return f"Knowledge base result for: {query}"


@tool
def create_ticket(title: str, description: str) -> str:
    """Create a demo support ticket."""
    return f"Created support ticket '{title}': {description}"


TOOLS = {
    "search_kb": search_kb,
    "create_ticket": create_ticket,
}


class MockLLM:
    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        last = ""
        for message in reversed(messages):
            content = getattr(message, "content", "")
            if content:
                last = str(content)
                break
        return AIMessage(content=f"Mock response: {last}")


class OllamaChat:
    def __init__(self, model: str, base_url: str):
        self.model = model.replace("ollama:", "", 1)
        self.base_url = base_url.rstrip("/")

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "assistant" if isinstance(message, AIMessage) else "system"
                    if isinstance(message, SystemMessage)
                    else "user",
                    "content": str(getattr(message, "content", "")),
                }
                for message in messages
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Ollama v1 endpoint not available, return explicit failure to fall back
                raise RuntimeError("Ollama v1 chat completions endpoint not found") from exc
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        data = response.json()
        content = ""
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content", "")
            if not content:
                content = message.get("reasoning_content") or message.get("thinking") or ""
        if not content:
            content = data.get("output") or data.get("response") or ""
        usage = data.get("usage") or {}
        usage_metadata = None
        if usage:
            usage_metadata = {
                "input_tokens": int(usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            }
        if usage_metadata:
            return AIMessage(content=content, usage_metadata=usage_metadata)
        return AIMessage(content=content)


class GoogleChat:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model.replace("google:", "", 1)

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        contents = []
        system_parts = []
        for message in messages:
            content = str(getattr(message, "content", ""))
            if not content:
                continue
            if isinstance(message, SystemMessage):
                system_parts.append({"text": content})
            elif isinstance(message, AIMessage):
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        if not contents:
            contents.append({"role": "user", "parts": [{"text": ""}]})

        payload: dict[str, Any] = {"contents": contents}
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
                response = await client.post(url, json=payload, headers={"x-goog-api-key": self.api_key})
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise RuntimeError(
                f"Google Gemini request failed with HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Google Gemini request failed: {exc}") from exc

        data = response.json()
        candidates = data.get("candidates") or []
        content = ""
        if candidates:
            candidate = candidates[0]
            candidate_content = candidate.get("content") or {}
            if isinstance(candidate_content, dict):
                parts = candidate_content.get("parts") or []
                content = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
            elif isinstance(candidate_content, str):
                content = candidate_content
            if not content:
                content = candidate.get("output") or ""
        if not content:
            content = data.get("output") or data.get("content") or ""
        usage = data.get("usageMetadata") or {}
        usage_metadata = None
        if usage:
            usage_metadata = {
                "input_tokens": int(usage.get("promptTokenCount") or 0),
                "output_tokens": int(usage.get("candidatesTokenCount") or 0),
                "total_tokens": int(usage.get("totalTokenCount") or 0),
            }
        if usage_metadata:
            return AIMessage(content=content, usage_metadata=usage_metadata)
        return AIMessage(content=content)


class GoogleWithFallback:
    def __init__(self, google: GoogleChat, fallback_llm: Any):
        self.google = google
        self.fallback_llm = fallback_llm

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        try:
            return await self.google.ainvoke(messages)
        except Exception:
            if hasattr(self.fallback_llm, "ainvoke"):
                return await self.fallback_llm.ainvoke(messages)
            return await self.fallback_llm.invoke(messages)


def _to_langchain_messages(raw_messages: list[dict], system_prompt: str) -> list[Any]:
    messages: list[Any] = [SystemMessage(content=system_prompt)]
    for message in raw_messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "assistant" or role == "agent":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages


class OllamaWithFallback:
    """Try Ollama first, fall back to API key if Ollama fails."""
    def __init__(self, ollama: OllamaChat, fallback_llm: Any):
        self.ollama = ollama
        self.fallback_llm = fallback_llm

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        try:
            # Try Ollama first
            result = await self.ollama.ainvoke(messages)
            # Check if it's a fallback response
            if "Ollama unavailable" not in result.content:
                return result
        except Exception:
            pass
        
        # Fall back to API key provider
        if hasattr(self.fallback_llm, "ainvoke"):
            return await self.fallback_llm.ainvoke(messages)
        else:
            return await self.fallback_llm.invoke(messages)


def _build_llm(agent: Agent) -> Any:
    model_name = agent.model.lower()
    
    # Build Ollama if available
    ollama_llm = None
    if settings.OLLAMA_BASE_URL:
        if model_name.startswith("ollama:") or model_name.startswith("llama"):
            ollama_llm = OllamaChat(agent.model, settings.OLLAMA_BASE_URL)
        elif model_name == "mock":
            ollama_llm = OllamaChat("ollama:gemma4:latest", settings.OLLAMA_BASE_URL)
    
    # Build fallback LLM (API key provider)
    fallback_llm = None
    google_api_key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
    if not google_api_key and settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("sk-"):
        google_api_key = settings.OPENAI_API_KEY

    if model_name.startswith("claude") and settings.ANTHROPIC_API_KEY:
        from langchain_anthropic import ChatAnthropic
        fallback_llm = ChatAnthropic(model=agent.model, api_key=settings.ANTHROPIC_API_KEY)
    elif google_api_key:
        model = agent.model if model_name.startswith(("gemini", "google:")) else "gemini-2.5-flash"
        fallback_llm = GoogleChat(api_key=google_api_key, model=model)
    elif settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        model = agent.model if model_name.startswith("gpt") else "gpt-3.5-turbo"
        fallback_llm = ChatOpenAI(model=model, api_key=settings.OPENAI_API_KEY)
    if ollama_llm and fallback_llm:
        return OllamaWithFallback(ollama_llm, fallback_llm)
    elif ollama_llm:
        return ollama_llm
    elif fallback_llm:
        selected_tools = [TOOLS[name] for name in agent.tools if name in TOOLS]
        if selected_tools and hasattr(fallback_llm, "bind_tools"):
            return fallback_llm.bind_tools(selected_tools)
        return fallback_llm
    else:
        return MockLLM()


async def _run_configured_tools(agent: Agent, user_message: str, context: dict[str, Any]) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    selected = [name for name in agent.tools if name in TOOLS]
    if "search_kb" in selected:
        result = await TOOLS["search_kb"].ainvoke({"query": user_message})
        outputs.append({"tool": "search_kb", "result": str(result)})
    intent = context.get("intent") or _infer_context(user_message).get("intent")
    lowered = user_message.lower()
    should_ticket = intent == "support" or any(word in lowered for word in ["ticket", "support", "broken", "failed"])
    if "create_ticket" in selected and should_ticket:
        result = await TOOLS["create_ticket"].ainvoke(
            {
                "title": f"Request from {agent.name}",
                "description": user_message,
            }
        )
        outputs.append({"tool": "create_ticket", "result": str(result)})
    return outputs


def _infer_context(content: str) -> dict[str, str]:
    lowered = content.lower()
    intent = "general"
    if "bill" in lowered or "invoice" in lowered or "payment" in lowered:
        intent = "billing"
    elif "ticket" in lowered or "support" in lowered:
        intent = "support"
    sentiment = "negative" if any(word in lowered for word in ["angry", "bad", "broken"]) else "neutral"
    return {"intent": intent, "sentiment": sentiment}


def create_agent_node(
    agent_id: uuid.UUID | str,
    session_factory: Callable = async_session,
) -> Callable[[dict], dict]:
    async def run_agent(state: dict) -> dict:
        async with session_factory() as db:
            result = await db.exec(select(Agent).where(Agent.id == uuid.UUID(str(agent_id))))
            agent = result.first()

        if agent is None:
            content = f"Agent {agent_id} was not found."
            tool_outputs: list[dict[str, str]] = []
            token_count = 0
        else:
            context = dict(state.get("context", {}))
            user_message = next(
                (
                    str(message.get("content", ""))
                    for message in reversed(state.get("messages", []))
                    if message.get("role") == "user"
                ),
                "",
            )
            tool_outputs = await _run_configured_tools(agent, user_message, context)
            tool_prompt = ""
            if tool_outputs:
                rendered = "\n".join(f"- {item['tool']}: {item['result']}" for item in tool_outputs)
                tool_prompt = f"\n\nTool results available to you:\n{rendered}"
            llm = _build_llm(agent)
            rules = "\n".join(
                item
                for item in [
                    agent.system_prompt,
                    f"Role: {agent.role}",
                    f"Skills: {', '.join(agent.skills)}" if agent.skills else "",
                    f"Interaction rules: {agent.interaction_rules}" if agent.interaction_rules else "",
                    f"Guardrails: {agent.guardrails}" if agent.guardrails else "",
                    tool_prompt,
                ]
                if item
            )
            messages = _to_langchain_messages(state.get("messages", []), rules)
            response = await llm.ainvoke(messages)
            content = str(getattr(response, "content", response)).strip()
            usage_metadata = getattr(response, "usage_metadata", None) or {}
            token_count = int(usage_metadata.get("total_tokens") or 0)

        messages = list(state.get("messages", []))
        agent_message = {"role": "agent", "agent_id": str(agent_id), "content": content}
        if token_count:
            agent_message["token_count"] = token_count
        messages.append(agent_message)
        context = dict(state.get("context", {}))
        context.update(_infer_context(content))
        if tool_outputs:
            context["tool_results"] = tool_outputs
        return {**state, "messages": messages, "context": context, "next_agent": None}

    return run_agent
