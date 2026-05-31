import { useEffect, useState } from 'react';
import { getApiUrl } from '@/config/api';

export type Agent = {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  tools: string[];
  channels: string[];
  skills: string[];
  interaction_rules: string;
  guardrails: string;
  limits: Record<string, unknown>;
  schedule?: string | null;
  memory_type: string;
};

export type AgentInput = Omit<Agent, 'id'>;

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const response = await fetch(getApiUrl('/api/agents/'));
      if (response.ok) {
        setAgents(await response.json());
      }
    } catch (error) {
      console.error('Failed to fetch agents:', error);
    }
    setLoading(false);
  }

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, []);

  async function createAgent(agent: AgentInput) {
    try {
      await fetch(getApiUrl('/api/agents/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agent),
      });
      await refresh();
    } catch (error) {
      console.error('Failed to create agent:', error);
    }
  }

  async function updateAgent(id: string, agent: Partial<AgentInput>) {
    try {
      await fetch(getApiUrl(`/api/agents/${id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agent),
      });
      await refresh();
    } catch (error) {
      console.error('Failed to update agent:', error);
    }
  }

  async function deleteAgent(id: string) {
    try {
      await fetch(getApiUrl(`/api/agents/${id}`), { method: 'DELETE' });
      await refresh();
    } catch (error) {
      console.error('Failed to delete agent:', error);
    }
  }

  return { agents, loading, refresh, createAgent, updateAgent, deleteAgent };
}
