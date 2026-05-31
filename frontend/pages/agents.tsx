import { Edit3, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { AgentForm } from '../components/AgentForm';
import { Layout } from '../components/Layout';
import { Agent, AgentInput, useAgents } from '../hooks/useAgents';

export default function AgentsPage() {
  const { agents, loading, createAgent, updateAgent, deleteAgent } = useAgents();
  const [editing, setEditing] = useState<Agent | null>(null);

  async function save(agent: AgentInput) {
    if (editing) {
      await updateAgent(editing.id, agent);
      setEditing(null);
    } else {
      await createAgent(agent);
    }
  }

  return (
    <Layout>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">Agent registry</span>
          <h1>Agents</h1>
        </div>
        <div className="headerStats">
          <strong>{agents.length}</strong>
          <span>configured</span>
        </div>
      </div>
      <AgentForm editing={editing} onCancel={() => setEditing(null)} onSaved={save} />
      <div className="agentGrid">
        {loading ? <span>Loading</span> : agents.map((agent) => (
          <article className="agentCard" key={agent.id}>
            <div className="cardHeader">
              <div>
                <h2>{agent.name}</h2>
                <p>{agent.role}</p>
              </div>
              <div className="buttonCluster">
                <button className="iconButton" type="button" onClick={() => setEditing(agent)} title="Edit agent">
                  <Edit3 size={17} />
                </button>
                <button className="iconButton danger" type="button" onClick={() => deleteAgent(agent.id)} title="Delete agent">
                  <Trash2 size={17} />
                </button>
              </div>
            </div>
            <div className="pillRow">
              <span>{agent.model}</span>
              <span>{agent.memory_type}</span>
              {agent.channels.map((channel) => <span key={channel}>{channel}</span>)}
            </div>
            <dl className="detailList">
              <div><dt>Tools</dt><dd>{agent.tools.join(', ') || 'None'}</dd></div>
              <div><dt>Skills</dt><dd>{agent.skills.join(', ') || 'None'}</dd></div>
              <div><dt>Guardrails</dt><dd>{agent.guardrails || 'None'}</dd></div>
            </dl>
          </article>
        ))}
      </div>
    </Layout>
  );
}
