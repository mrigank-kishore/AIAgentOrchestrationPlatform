import { useEffect, useState } from 'react';
import { getApiUrl, API_BASE_URL } from '@/config/api';

export type WorkflowDefinition = {
  triggers?: Array<{
    channel: string;
    reply?: boolean;
  }>;
  entry_node?: string;
  end_nodes: string[];
  nodes: Array<{ id: string; agent_id: string }>;
  edges: Array<{
    source: string;
    target: string;
    condition?: string | null;
    condition_map?: Record<string, string> | null;
  }>;
};

export type Workflow = {
  id: string;
  name: string;
  description: string;
  definition: WorkflowDefinition;
  is_template: boolean;
  created_at: string;
};

export type MessageHistory = {
  id: string;
  workflow_run_id: string;
  agent_id: string | null;
  role: string;
  content: string;
  channel: string;
  token_count: number;
  cost_usd: number;
  langfuse_trace_id?: string | null;
  langfuse_trace_url?: string | null;
  timestamp: string;
};

export function useWorkflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [history, setHistory] = useState<MessageHistory[]>([]);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const [workflowResponse, historyResponse] = await Promise.all([
        fetch(getApiUrl('/api/workflows/')),
        fetch(getApiUrl('/api/workflows/history')),
      ]);
      if (workflowResponse.ok && historyResponse.ok) {
        setWorkflows(await workflowResponse.json());
        setHistory(await historyResponse.json());
      } else {
        console.warn('Workflow fetch returned non-ok status:', {
          workflows: workflowResponse.status,
          history: historyResponse.status,
        });
      }
    } catch (error) {
      console.error('Failed to fetch workflows. API Base URL:', API_BASE_URL, 'Error:', error);
    }
    setLoading(false);
  }

  async function executeWorkflow(id: string, user_message: string) {
    try {
      const url = getApiUrl(`/api/workflows/${id}/execute`);
      console.log('===== Workflow Execution Debug =====');
      console.log('Workflow ID:', id);
      console.log('API Base URL:', API_BASE_URL);
      console.log('Full URL:', url);
      console.log('User Message:', user_message);
      console.log('====================================');
      
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_message }),
      });
      
      console.log('Response Status:', response.status);
      console.log('Response Headers:', Object.fromEntries(response.headers.entries()));
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error Response:', errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('Response Result:', result);
      await refresh();
      return result as { response: string; workflow_run_id: string; token_count: number; cost_usd: number };
    } catch (error) {
      console.error('Failed to execute workflow:');
      console.error('Error Type:', error instanceof Error ? 'Error' : typeof error);
      console.error('Error Message:', error instanceof Error ? error.message : String(error));
      console.error('Full Error:', error);
      throw error;
    }
  }

  useEffect(() => {
    refresh().catch(() => setLoading(false));
  }, []);

  return {
    workflows,
    templates: workflows.filter((workflow) => workflow.is_template),
    userWorkflows: workflows.filter((workflow) => !workflow.is_template),
    history,
    loading,
    refresh,
    executeWorkflow,
  };
}
