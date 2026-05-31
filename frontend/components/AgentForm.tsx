import { Save, X } from 'lucide-react';
import { FormEvent, useEffect, useState } from 'react';

import { Agent, AgentInput } from '../hooks/useAgents';

type AgentDraft = {
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  tools: string;
  channels: string;
  skills: string;
  interaction_rules: string;
  guardrails: string;
  limits: string;
  memory_type: string;
  schedule: string;
};

const defaults: AgentDraft = {
  name: '',
  role: '',
  system_prompt: '',
  model: 'ollama:llama3.2:3b',
  tools: 'search_kb,create_ticket',
  channels: 'api,telegram',
  skills: 'classification,handoff',
  interaction_rules: 'Be concise. Hand off when another agent is better suited.',
  guardrails: 'Do not invent customer records. Ask for clarification when unsure.',
  limits: '{"max_turns":4,"max_tokens":800}',
  memory_type: 'buffer',
  schedule: '',
};

function csv(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function toggleCsv(value: string, item: string) {
  const items = new Set(csv(value));
  if (items.has(item)) {
    items.delete(item);
  } else {
    items.add(item);
  }
  return Array.from(items).join(',');
}

function toDraft(agent?: Agent | null): AgentDraft {
  if (!agent) return defaults;
  return {
    name: agent.name,
    role: agent.role,
    system_prompt: agent.system_prompt,
    model: agent.model,
    tools: agent.tools.join(','),
    channels: agent.channels.join(','),
    skills: agent.skills.join(','),
    interaction_rules: agent.interaction_rules,
    guardrails: agent.guardrails,
    limits: JSON.stringify(agent.limits || {}),
    memory_type: agent.memory_type,
    schedule: agent.schedule || '',
  };
}

function toInput(form: AgentDraft): AgentInput {
  let limits: Record<string, unknown> = {};
  try {
    limits = JSON.parse(form.limits || '{}');
  } catch {
    limits = {};
  }
  return {
    name: form.name,
    role: form.role,
    system_prompt: form.system_prompt,
    model: form.model,
    tools: csv(form.tools),
    channels: csv(form.channels),
    skills: csv(form.skills),
    interaction_rules: form.interaction_rules,
    guardrails: form.guardrails,
    limits,
    schedule: form.schedule || null,
    memory_type: form.memory_type,
  };
}

export function AgentForm({
  editing,
  onCancel,
  onSaved,
}: {
  editing?: Agent | null;
  onCancel?: () => void;
  onSaved: (agent: AgentInput) => Promise<void>;
}) {
  const [form, setForm] = useState<AgentDraft>(toDraft(editing));

  useEffect(() => {
    setForm(toDraft(editing));
  }, [editing]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onSaved(toInput(form));
    setForm(defaults);
  }

  return (
    <form className="agentEditor" onSubmit={submit}>
      <div className="editorHeader">
        <div>
          <span className="eyebrow">{editing ? 'Edit agent' : 'New agent'}</span>
          <h2>{editing ? editing.name : 'Configure behavior'}</h2>
        </div>
        {editing && onCancel ? (
          <button className="iconButton" type="button" onClick={onCancel} title="Cancel edit">
            <X size={18} />
          </button>
        ) : null}
      </div>
      <div className="formGrid">
        <label>
          <span>Name</span>
          <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
        </label>
        <label>
          <span>Role</span>
          <input value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} required />
        </label>
        <label>
          <span>Model</span>
          <input value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} required />
        </label>
        <label>
          <span>Memory</span>
          <select value={form.memory_type} onChange={(event) => setForm({ ...form, memory_type: event.target.value })}>
            <option value="buffer">Buffer</option>
            <option value="summary">Summary</option>
            <option value="none">None</option>
          </select>
        </label>
        <label>
          <span>Tools</span>
          <input value={form.tools} onChange={(event) => setForm({ ...form, tools: event.target.value })} />
        </label>
        <fieldset className="channelField">
          <legend>Channels</legend>
          <label>
            <input
              type="checkbox"
              checked={csv(form.channels).includes('api')}
              onChange={() => setForm({ ...form, channels: toggleCsv(form.channels, 'api') })}
            />
            <span>API</span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={csv(form.channels).includes('telegram')}
              onChange={() => setForm({ ...form, channels: toggleCsv(form.channels, 'telegram') })}
            />
            <span>Telegram</span>
          </label>
        </fieldset>
        <label>
          <span>Skills</span>
          <input value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} />
        </label>
        <label>
          <span>Schedule</span>
          <input value={form.schedule} onChange={(event) => setForm({ ...form, schedule: event.target.value })} />
        </label>
      </div>
      <label>
        <span>System prompt</span>
        <textarea value={form.system_prompt} onChange={(event) => setForm({ ...form, system_prompt: event.target.value })} required />
      </label>
      <div className="formGrid compact">
        <label>
          <span>Interaction rules</span>
          <textarea value={form.interaction_rules} onChange={(event) => setForm({ ...form, interaction_rules: event.target.value })} />
        </label>
        <label>
          <span>Guardrails</span>
          <textarea value={form.guardrails} onChange={(event) => setForm({ ...form, guardrails: event.target.value })} />
        </label>
        <label>
          <span>Limits JSON</span>
          <textarea value={form.limits} onChange={(event) => setForm({ ...form, limits: event.target.value })} />
        </label>
      </div>
      <button className="primary" type="submit" title="Save agent">
        <Save size={18} />
        <span>{editing ? 'Update agent' : 'Create agent'}</span>
      </button>
    </form>
  );
}
