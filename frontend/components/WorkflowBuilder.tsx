import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';
import { GitBranch, Play, Plus, Save } from 'lucide-react';

import { getApiUrl } from '../config/api';
import { Agent } from '../hooks/useAgents';

type BuilderEdge = Edge & {
  data?: {
    condition?: string;
    condition_map?: Record<string, string>;
  };
};

export function WorkflowBuilder({
  agents,
  onSaved,
}: {
  agents: Agent[];
  onSaved?: () => Promise<void> | void;
}) {
  const [name, setName] = useState('Support Workflow');
  const [description, setDescription] = useState('Built in the visual editor');
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<BuilderEdge>([]);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [sourceNode, setSourceNode] = useState('');
  const [targetNode, setTargetNode] = useState('');
  const [condition, setCondition] = useState('');
  const [apiTrigger, setApiTrigger] = useState(true);
  const [telegramTrigger, setTelegramTrigger] = useState(false);
  const [telegramReply, setTelegramReply] = useState(true);
  const [testMessage, setTestMessage] = useState('My payment failed and I need support');
  const [lastRun, setLastRun] = useState('');

  useEffect(() => {
    if (!selectedAgent && agents[0]) setSelectedAgent(agents[0].id);
  }, [agents, selectedAgent]);

  const agentById = useMemo(() => Object.fromEntries(agents.map((agent) => [agent.id, agent])), [agents]);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, label: 'default', data: {} }, current));
  }, [setEdges]);

  function addNode() {
    const agent = agentById[selectedAgent];
    if (!agent) return;
    const id = `node_${nodes.length + 1}`;
    setNodes((current) => [
      ...current,
      {
        id,
        position: { x: 120 + current.length * 140, y: 120 + current.length * 60 },
        data: { label: agent.name, agent_id: agent.id },
      },
    ]);
    if (!sourceNode) setSourceNode(id);
    setTargetNode(id);
  }

  function addConfiguredEdge(feedbackLoop = false) {
    if (!sourceNode || !targetNode) return;
    const source = feedbackLoop ? targetNode : sourceNode;
    const target = feedbackLoop ? sourceNode : targetNode;
    setEdges((current) => addEdge({
      id: `${source}-${target}-${current.length + 1}`,
      source,
      target,
      label: condition || (feedbackLoop ? 'feedback' : 'default'),
      data: condition ? { condition, condition_map: { billing: target, support: target, general: target } } : {},
    }, current));
  }

  function workflowDefinition() {
    const triggers = [
      ...(apiTrigger ? [{ channel: 'api', reply: true }] : []),
      ...(telegramTrigger ? [{ channel: 'telegram', reply: telegramReply }] : []),
    ];

    return {
      triggers,
      entry_node: nodes[0]?.id,
      end_nodes: nodes.length ? [nodes[nodes.length - 1].id] : [],
      nodes: nodes.map((node) => ({ id: node.id, agent_id: String(node.data.agent_id) })),
      edges: edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        condition: edge.data?.condition || null,
        condition_map: edge.data?.condition_map || null,
      })),
    };
  }

  async function saveWorkflow() {
    await fetch(getApiUrl('/api/workflows/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, definition: workflowDefinition(), is_template: false }),
    });
    await onSaved?.();
  }

  async function runDraft() {
    await saveWorkflow();
    const response = await fetch(getApiUrl('/api/workflows/'));
    const workflows = await response.json();
    const saved = workflows.find((workflow: any) => workflow.name === name && !workflow.is_template);
    if (!saved) return;
    const result = await fetch(getApiUrl(`/api/workflows/${saved.id}/execute`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_message: testMessage }),
    });
    const data = await result.json();
    setLastRun(data.response);
    await onSaved?.();
  }

  return (
    <div className="builderShell">
      <aside className="builderPanel">
        <div className="editorHeader">
          <div>
            <span className="eyebrow">Visual workflow</span>
            <h2>Builder</h2>
          </div>
          <GitBranch size={22} />
        </div>
        <label>
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          <span>Description</span>
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <fieldset className="channelField triggerField">
          <legend>Triggers</legend>
          <label>
            <input
              type="checkbox"
              checked={apiTrigger}
              onChange={(event) => setApiTrigger(event.target.checked)}
            />
            <span>API</span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={telegramTrigger}
              onChange={(event) => setTelegramTrigger(event.target.checked)}
            />
            <span>Telegram</span>
          </label>
        </fieldset>
        <label className="replyToggle">
          <input
            type="checkbox"
            checked={telegramReply}
            disabled={!telegramTrigger}
            onChange={(event) => setTelegramReply(event.target.checked)}
          />
          <span>Reply to Telegram with final output</span>
        </label>
        <label>
          <span>Agent</span>
          <select value={selectedAgent} onChange={(event) => setSelectedAgent(event.target.value)}>
            {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
          </select>
        </label>
        <button type="button" onClick={addNode}>
          <Plus size={18} />
          <span>Add node</span>
        </button>
        <div className="edgeTools">
          <label>
            <span>Source</span>
            <select value={sourceNode} onChange={(event) => setSourceNode(event.target.value)}>
              <option value="">Select</option>
              {nodes.map((node) => <option key={node.id} value={node.id}>{node.data.label as string}</option>)}
            </select>
          </label>
          <label>
            <span>Target</span>
            <select value={targetNode} onChange={(event) => setTargetNode(event.target.value)}>
              <option value="">Select</option>
              {nodes.map((node) => <option key={node.id} value={node.id}>{node.data.label as string}</option>)}
            </select>
          </label>
          <label>
            <span>Condition</span>
            <input value={condition} placeholder="intent == 'billing'" onChange={(event) => setCondition(event.target.value)} />
          </label>
          <div className="buttonGrid">
            <button type="button" onClick={() => addConfiguredEdge(false)}>Connect</button>
            <button type="button" onClick={() => addConfiguredEdge(true)}>Feedback loop</button>
          </div>
        </div>
        <label>
          <span>Test message</span>
          <textarea value={testMessage} onChange={(event) => setTestMessage(event.target.value)} />
        </label>
        <div className="buttonGrid">
          <button className="primary" type="button" onClick={saveWorkflow} title="Save workflow">
            <Save size={18} />
            <span>Save</span>
          </button>
          <button type="button" onClick={runDraft} title="Run workflow">
            <Play size={18} />
            <span>Run</span>
          </button>
        </div>
        {lastRun ? <div className="runResult">{lastRun}</div> : null}
      </aside>
      <div className="canvas">
        <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} fitView>
          <MiniMap />
          <Controls />
          <Background />
        </ReactFlow>
      </div>
    </div>
  );
}
