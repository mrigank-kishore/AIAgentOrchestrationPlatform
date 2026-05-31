import { Play } from 'lucide-react';
import { useState } from 'react';

import { Layout } from '../components/Layout';
import { WorkflowBuilder } from '../components/WorkflowBuilder';
import { useAgents } from '../hooks/useAgents';
import { Workflow, useWorkflows } from '../hooks/useWorkflows';

function triggerLabels(workflow: Workflow) {
  return (workflow.definition.triggers || []).map((trigger) => (
    trigger.channel === 'telegram' && trigger.reply ? 'telegram reply' : trigger.channel
  ));
}

export default function WorkflowsPage() {
  const { agents } = useAgents();
  const { templates, userWorkflows, history, loading, refresh, executeWorkflow } = useWorkflows();
  const [messageByWorkflow, setMessageByWorkflow] = useState<Record<string, string>>({});
  const [result, setResult] = useState('');

  async function run(workflow: Workflow) {
    try {
      console.log('Running workflow:', workflow.id);
      const user_message = messageByWorkflow[workflow.id] || 'Please help me with a billing support issue';
      const response = await executeWorkflow(workflow.id, user_message);
      const costLabel = response.cost_usd > 0 ? `$${response.cost_usd.toFixed(6)}` : 'local $0';
      setResult(`${workflow.name}: ${response.response} (${response.token_count} tokens, ${costLabel})`);
    } catch (error) {
      console.error('Workflow execution error:', error);
      const errorMsg = error instanceof Error ? error.message : String(error);
      setResult(`Error running ${workflow.name}: ${errorMsg}`);
    }
  }

  return (
    <Layout>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">LangGraph orchestration</span>
          <h1>Workflows</h1>
        </div>
        <div className="headerStats">
          <strong>{templates.length}</strong>
          <span>templates</span>
        </div>
      </div>
      <section className="templateGrid">
        {loading ? <span>Loading</span> : templates.map((workflow) => (
          <article className="templateCard" key={workflow.id}>
            <h2>{workflow.name}</h2>
            <p>{workflow.description}</p>
            <div className="pillRow">
              <span>{workflow.definition.nodes.length} agents</span>
              <span>{workflow.definition.edges.length} edges</span>
              {triggerLabels(workflow).map((label) => <span key={label}>{label}</span>)}
              <span>template</span>
            </div>
            <textarea
              value={messageByWorkflow[workflow.id] || ''}
              placeholder="Run this template with a message"
              onChange={(event) => setMessageByWorkflow({ ...messageByWorkflow, [workflow.id]: event.target.value })}
            />
            <button type="button" onClick={() => run(workflow)}>
              <Play size={18} />
              <span>Run template</span>
            </button>
          </article>
        ))}
      </section>
      {result ? <div className="runBanner">{result}</div> : null}
      <WorkflowBuilder agents={agents} onSaved={refresh} />
      <section className="historyPanel">
        <div className="editorHeader">
          <div>
            <span className="eyebrow">Persisted runs</span>
            <h2>Message history</h2>
          </div>
          <span>{history.length} messages</span>
        </div>
        <div className="historyList">
          {history.slice(0, 12).map((message) => (
            <article key={message.id}>
              <div>
                <strong>{message.role}</strong>
                <span>{message.channel}</span>
              </div>
              <p>{message.content}</p>
              <footer>
                <span>{message.workflow_run_id.slice(0, 8)}</span>
                <span>{message.token_count} tokens</span>
                <span>{message.cost_usd > 0 ? `$${message.cost_usd.toFixed(6)}` : 'local $0'}</span>
                {message.langfuse_trace_url ? (
                  <a href={message.langfuse_trace_url} target="_blank" rel="noreferrer">Langfuse</a>
                ) : null}
              </footer>
            </article>
          ))}
        </div>
      </section>
      <section className="historyPanel">
        <div className="editorHeader">
          <div>
            <span className="eyebrow">Saved drafts</span>
            <h2>User workflows</h2>
          </div>
          <span>{userWorkflows.length} saved</span>
        </div>
        <div className="pillRow">
          {userWorkflows.map((workflow) => (
            <span key={workflow.id}>{workflow.name} {triggerLabels(workflow).join(', ')}</span>
          ))}
        </div>
      </section>
    </Layout>
  );
}
