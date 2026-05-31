from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

from app.core.config import settings
from app.models.workflow import WorkflowDefinition

logger = logging.getLogger(__name__)


def langfuse_host() -> str:
    return (settings.LANGFUSE_HOST or settings.LANGFUSE_BASE_URL or "").rstrip("/")


def is_langfuse_configured() -> bool:
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY and langfuse_host())


class LangfuseWorkflowTrace:
    def __init__(
        self,
        *,
        workflow: WorkflowDefinition,
        workflow_run_id: Any,
        user_message: str,
        channel: str,
        user_id: str,
    ) -> None:
        self.workflow = workflow
        self.workflow_run_id = workflow_run_id
        self.user_message = user_message
        self.channel = channel
        self.user_id = user_id
        self.enabled = False
        self.trace_id: str | None = None
        self.trace_url: str | None = None
        self._client: Any = None
        self._observation_cm: Any = None
        self._attributes_cm: Any = None
        self._span: Any = None

    def __enter__(self) -> "LangfuseWorkflowTrace":
        if not is_langfuse_configured():
            return self
        try:
            from langfuse import Langfuse, propagate_attributes
            from langfuse.types import TraceContext

            self._client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=langfuse_host(),
            )
            self.trace_id = self._client.create_trace_id(seed=str(self.workflow_run_id))
            self.trace_url = self._client.get_trace_url(trace_id=self.trace_id)
            self._observation_cm = self._client.start_as_current_observation(
                trace_context=TraceContext(trace_id=self.trace_id),
                name=self.workflow.name,
                as_type="chain",
                input={"message": self.user_message},
                metadata={
                    "workflow_id": str(self.workflow.id),
                    "workflow_run_id": str(self.workflow_run_id),
                    "channel": self.channel,
                    "user_id": self.user_id,
                },
            )
            self._span = self._observation_cm.__enter__()
            self._attributes_cm = propagate_attributes(
                user_id=self.user_id,
                session_id=str(self.workflow_run_id),
                trace_name=self.workflow.name,
                tags=[self.channel, "workflow"],
                metadata={"workflow_id": str(self.workflow.id)},
            )
            self._attributes_cm.__enter__()
            self.enabled = True
        except Exception:
            logger.exception("Failed to initialize Langfuse tracing")
            self.enabled = False
        return self

    def set_output(self, output: str, metadata: dict[str, Any] | None = None) -> None:
        if not self.enabled or self._span is None:
            return
        try:
            self._span.update(output={"response": output}, metadata=metadata)
        except Exception:
            logger.exception("Failed to update Langfuse trace output")

    def record_agent_step(
        self,
        *,
        agent_id: Any,
        agent_name: str,
        agent_model: str,
        input_message: str,
        output_message: str,
        token_count: int,
        cost_usd: float,
        step_index: int,
    ) -> None:
        if not self.enabled or self._span is None:
            return
        try:
            with self._span.start_as_current_observation(
                name=agent_name,
                as_type="agent",
                input={"message": input_message},
                output={"message": output_message},
                metadata={
                    "agent_id": str(agent_id),
                    "model": agent_model,
                    "step_index": step_index,
                    "token_count": token_count,
                    "cost_usd": cost_usd,
                },
            ):
                pass
        except Exception:
            logger.exception("Failed to record Langfuse agent step")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.enabled and exc is not None and self._span is not None:
            try:
                self._span.update(level="ERROR", status_message=str(exc))
            except Exception:
                logger.exception("Failed to mark Langfuse trace as errored")
        for manager in (self._attributes_cm, self._observation_cm):
            if manager is not None:
                try:
                    manager.__exit__(exc_type, exc, tb)
                except Exception:
                    logger.exception("Failed to close Langfuse context")
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:
                logger.exception("Failed to flush Langfuse trace")


def start_workflow_trace(
    *,
    workflow: WorkflowDefinition,
    workflow_run_id: Any,
    user_message: str,
    channel: str,
    user_id: str,
) -> LangfuseWorkflowTrace:
    return LangfuseWorkflowTrace(
        workflow=workflow,
        workflow_run_id=workflow_run_id,
        user_message=user_message,
        channel=channel,
        user_id=user_id,
    )
