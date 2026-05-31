# AIAgentOrchestrationPlatform

## Tech Stack

| Tech stack | What it does | Why | Tradeoff |
| --- | --- | --- | --- |
| LangChain | Provides message abstractions, model integrations, tools, and LLM invocation patterns used by each agent. | It gives a standard way to connect agents to different LLM providers and tools without hard-coding one model vendor. | It is not used as the workflow orchestrator because LangGraph gives clearer graph execution, node routing, and state transitions. |
| LangGraph | Dynamically builds and runs the multi-agent workflow graph from the saved workflow JSON. | The product needs agent-to-agent workflows with ordered steps, conditional edges, and feedback loops, which are naturally represented as a graph. | Chosen over CrewAI and AutoGen because this app needs user-authored visual graphs, not mostly conversation/team abstractions; chosen over a custom runtime to avoid rebuilding graph execution, routing, and state handling. |
| FastAPI | Exposes REST APIs for agents, workflows, integrations, execution, and monitoring. | It is async-friendly, lightweight, and works well with WebSockets, Telegram polling, and Python AI libraries. | Django would add more built-in structure than needed; Flask would require more manual async/WebSocket setup. |
| SQLModel | Defines typed database models for agents, workflows, and message history. | It combines Pydantic validation with SQLAlchemy persistence, keeping API schemas and database models easy to maintain. | Raw SQLAlchemy is more flexible but more verbose; using separate Pydantic and ORM models would duplicate schema logic for this prototype. |
| SQLite | Stores local data such as agent configuration, workflow definitions, and message history. | It keeps the project fully local and simple to run without requiring an external database service. | PostgreSQL would be better for production concurrency, but SQLite is simpler for a local single-container challenge demo. |
| Next.js | Provides the frontend application for managing agents, building workflows, and viewing monitor logs. | It gives a structured React app with build/export support, making the UI easy to run locally or serve from the backend. | Vite would be lighter, but Next.js gives a familiar app structure and static export path for deployment. |
| React | Powers the interactive UI components and state management on the frontend. | The platform needs a dynamic visual interface for CRUD forms, workflow editing, and live monitoring. | Server-rendered templates would be simpler, but they would make the visual workflow builder and live monitor less ergonomic. |
| React Flow / @xyflow/react | Renders the visual workflow builder with draggable nodes and edges. | It is purpose-built for graph editors, so users can visually connect agents instead of editing JSON manually. | Building a graph canvas manually would take longer and be less reliable for node/edge interactions. |
| WebSocket | Streams workflow and agent events to the monitor page in real time. | Monitoring should update live while a workflow runs, instead of waiting for the user to refresh history. | Polling would be simpler but less responsive and would create unnecessary repeated API requests. |
| asyncio broker | Publishes runtime events from the backend to WebSocket subscribers. | It keeps live event delivery lightweight and local without adding Redis, Kafka, or another message broker. | Redis pub/sub would scale better across multiple processes, but the requirement targets a local single-container app. |
| python-telegram-bot | Connects Telegram messages to the default workflow. | It satisfies the external messaging channel requirement and allows a human to interact with agents conversationally. | Slack or WhatsApp could also work, but Telegram long polling is simpler to run locally without public webhooks. |
| Langfuse | Records workflow traces and per-agent observations. | It makes execution visible outside the app, showing each agent step separately for debugging and observability. | Custom trace tables would be simpler locally, but Langfuse provides purpose-built LLM observability and trace visualization. |
| Ollama | Runs local models through an OpenAI-compatible HTTP API. | It lets the project work locally without depending on paid cloud model APIs. | Hosted models may be stronger, but Ollama keeps the demo private, local, and usable without API credits. |
| OpenAI / Anthropic / Gemini adapters | Provide optional hosted LLM backends when API keys are configured. | They make the runtime flexible so agents can use stronger hosted models when available. | Supporting multiple providers adds configuration complexity, but avoids locking the platform to one model vendor. |
| Uvicorn | Runs the FastAPI ASGI application during development and deployment. | It supports async APIs and WebSockets, which are core to workflow execution and live monitoring. | Gunicorn alone is not enough for ASGI/WebSockets; Uvicorn is the direct fit for this async app. |
| Docker | Packages backend, frontend build output, and runtime dependencies into one container. | It gives a repeatable single-container run path for demos and review. | Local scripts are faster while developing, but Docker is more predictable for evaluators. |
| TypeScript | Adds type checking to frontend components, hooks, and API data handling. | It reduces UI regressions when workflow, agent, and monitor payload shapes change. | Plain JavaScript would be quicker initially, but TypeScript catches payload and component mistakes earlier. |

For the required AI framework choice, this project uses **LangGraph**. The requirement allowed one of openclaw.ai, LangGraph, CrewAI, AutoGen, or a custom runtime; LangGraph was selected because the core product is a visual workflow builder where users connect agents as nodes and edges, then the backend dynamically executes that graph. CrewAI and AutoGen are strong for agent collaboration patterns, but they are less directly aligned with user-authored graph definitions. openclaw.ai is oriented toward always-on agents with SOUL.md/MEMORY, while this project focuses on run-based workflow execution. A custom runtime would satisfy the requirement, but it would add avoidable risk by reimplementing graph routing, state passing, and async node execution that LangGraph already provides.

## Architecture Flow

![AAOP prototype architecture](AAOP-Prototype.drawio.png)

## Workflow JSON Flow

The frontend creates workflows visually with React Flow, then sends the workflow as JSON to the backend. The backend stores this JSON definition in SQLite and uses it later to dynamically build and execute a LangGraph workflow.

### 1. Save Workflow

`POST /api/workflows/`

```json
{
  "name": "Research and Summary Workflow",
  "description": "Researches a topic first, then summarizes the research output.",
  "is_template": false,
  "definition": {
    "triggers": [
      {
        "channel": "api",
        "reply": true
      },
      {
        "channel": "telegram",
        "reply": true
      }
    ],
    "entry_node": "research",
    "end_nodes": ["summary"],
    "nodes": [
      {
        "id": "research",
        "agent_id": "RESEARCH_AGENT_UUID"
      },
      {
        "id": "summary",
        "agent_id": "SUMMARY_AGENT_UUID"
      }
    ],
    "edges": [
      {
        "source": "research",
        "target": "summary",
        "condition": null,
        "condition_map": null
      }
    ]
  }
}
```

The workflow is saved in the `workflowdefinition` table. The `definition` field stores the dynamic graph structure: triggers, entry node, end nodes, agent nodes, and edges.

### 2. Execute Workflow

`POST /api/workflows/{workflow_id}/execute`

```json
{
  "user_message": "Compare Kubernetes and Azure Container Apps for hosting a small FastAPI service. Research first, then summarize for a startup CTO."
}
```

### 3. Runtime Execution

When the workflow runs, the backend performs these steps:

- Loads the workflow definition from SQLite.
- Loads each referenced agent configuration from SQLite.
- Builds a LangGraph dynamically from `entry_node`, `nodes`, `edges`, and `end_nodes`.
- Starts with the user message as the first message in workflow state.
- Runs the first agent node.
- Passes the updated message state to the next agent node.
- Stores the user prompt and each agent output in message history.
- Publishes live monitor events over WebSocket.
- Sends workflow and per-agent telemetry to Langfuse.
- Returns the final agent output to the frontend or Telegram.

### 4. Backend Response

```json
{
  "response": "For a small FastAPI service, Azure Container Apps is usually the faster choice...",
  "workflow_run_id": "82e04532-35e1-49a8-914e-8a2561fe3342",
  "token_count": 642,
  "cost_usd": 0
}
```

In short, the JSON flow is:

```text
Frontend visual workflow
  -> workflow JSON
  -> FastAPI
  -> SQLite workflowdefinition table
  -> dynamic LangGraph build
  -> agent execution
  -> message history in SQLite
  -> telemetry in Langfuse
  -> final response
```
