import { Activity, Bot, CheckCircle2, CircleDollarSign, Radio, UserRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { getApiUrl } from '../config/api';
import { useWebSocket } from '../hooks/useWebSocket';

type MonitorEvent = {
  id?: string;
  type?: string;
  workflow_run_id?: string;
  workflow_id?: string;
  agent_id?: string | null;
  agent_name?: string;
  role?: string;
  content?: string;
  response?: string;
  channel?: string;
  token_count?: number;
  cost_usd?: number;
  langfuse_trace_url?: string;
  timestamp?: string;
};

type TimelineStep = MonitorEvent & {
  label: string;
  sortTime: number;
};

type RunTimeline = {
  id: string;
  workflowId?: string;
  traceUrl?: string;
  startedAt: number;
  updatedAt: number;
  steps: TimelineStep[];
  finalResponse?: string;
  tokenCount: number;
  costUsd: number;
};

function eventTime(event: MonitorEvent) {
  return event.timestamp ? new Date(event.timestamp).getTime() || 0 : 0;
}

function eventText(event: MonitorEvent) {
  if (event.content) return event.content;
  if (event.type === 'workflow_finished') return event.response || '';
  return '';
}

export function Monitor() {
  const { connected, events } = useWebSocket('/ws/monitor');
  const [historyEvents, setHistoryEvents] = useState<any[]>([]);
  const [historyError, setHistoryError] = useState('');
  const [agentById, setAgentById] = useState<Record<string, string>>({});
  const allEvents = useMemo<MonitorEvent[]>(() => [...events, ...historyEvents], [events, historyEvents]);

  const runTimelines = useMemo<RunTimeline[]>(() => {
    const byRun = new Map<string, RunTimeline>();
    const seenMessages = new Map<string, Set<string>>();

    for (const event of [...allEvents].sort((a, b) => eventTime(a) - eventTime(b))) {
      const runId = event.workflow_run_id || 'standalone';
      const sortTime = eventTime(event);
      const run = byRun.get(runId) || {
        id: runId,
        workflowId: event.workflow_id,
        traceUrl: event.langfuse_trace_url,
        startedAt: sortTime,
        updatedAt: sortTime,
        steps: [],
        tokenCount: 0,
        costUsd: 0,
      };
      run.workflowId = run.workflowId || event.workflow_id;
      run.traceUrl = run.traceUrl || event.langfuse_trace_url;
      run.startedAt = run.startedAt ? Math.min(run.startedAt, sortTime || run.startedAt) : sortTime;
      run.updatedAt = Math.max(run.updatedAt, sortTime);

      if (event.type === 'workflow_finished') {
        run.finalResponse = event.response;
      }

      const text = eventText(event);
      const isPrompt = event.role === 'user' || event.type === 'workflow_started';
      const isAgentMessage = event.role === 'agent' || event.type === 'agent_finished' || Boolean(event.agent_id);
      if (text && (isPrompt || isAgentMessage || event.type === 'message_recorded')) {
        const role = isPrompt ? 'user' : event.role || 'agent';
        const label = role === 'user'
          ? 'Inbound message'
          : event.agent_name || (event.agent_id ? agentById[String(event.agent_id)] : '') || 'Agent output';
        const key = `${role}|${event.agent_id || ''}|${text}`;
        const seen = seenMessages.get(runId) || new Set<string>();
        if (!seen.has(key)) {
          seen.add(key);
          seenMessages.set(runId, seen);
          run.steps.push({ ...event, role, content: text, label, sortTime });
          run.tokenCount += Number(event.token_count || 0);
          run.costUsd += Number(event.cost_usd || 0);
        }
      }

      byRun.set(runId, run);
    }

    return Array.from(byRun.values())
      .filter((run) => run.steps.length || run.finalResponse)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, 25);
  }, [allEvents, agentById]);

  const tokenTotal = runTimelines.reduce((total, run) => total + run.tokenCount, 0);
  const costTotal = runTimelines.reduce((total, run) => total + run.costUsd, 0);
  const costLabel = costTotal > 0 ? `$${costTotal.toFixed(6)}` : 'local $0';

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const response = await fetch(getApiUrl('/api/workflows/history'));
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const rows = await response.json();
        if (cancelled) {
          return;
        }
        setHistoryEvents(
          rows
            .map((row: any) => ({
              ...row,
              type: 'message_recorded',
            })),
        );
      } catch (error) {
        if (!cancelled) {
          setHistoryError(error instanceof Error ? error.message : 'Unable to load history');
        }
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadAgents() {
      try {
        const response = await fetch(getApiUrl('/api/agents/'));
        if (!response.ok) {
          return;
        }
        const rows = await response.json();
        if (!cancelled) {
          setAgentById(Object.fromEntries(rows.map((agent: any) => [agent.id, agent.name])));
        }
      } catch {
        if (!cancelled) {
          setAgentById({});
        }
      }
    }

    loadAgents();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="monitorGrid">
      <section className="metricPanel">
        <Radio size={20} />
        <div>
          <span>Connection</span>
          <strong className={connected ? 'okText' : ''}>{connected ? 'Live' : 'Offline'}</strong>
        </div>
      </section>
      <section className="metricPanel">
        <Activity size={20} />
        <div>
          <span>Runs</span>
          <strong>{runTimelines.length}</strong>
        </div>
      </section>
      <section className="metricPanel">
        <CircleDollarSign size={20} />
        <div>
          <span>Tokens / cost</span>
          <strong>{tokenTotal} / {costLabel}</strong>
        </div>
      </section>
      <section className="eventStream">
        {historyError ? <article><p>History unavailable: {historyError}</p></article> : null}
        {runTimelines.map((run) => (
          <article className="runTimeline" key={run.id}>
            <header>
              <strong>Workflow run {run.id === 'standalone' ? '' : run.id.slice(0, 8)}</strong>
              <span>{run.updatedAt ? new Date(run.updatedAt).toLocaleTimeString() : ''}</span>
            </header>
            <div className="conversationFlow">
              {run.steps.map((step, index) => {
                const isUser = step.role === 'user';
                return (
                  <div className="conversationStep" key={`${step.id || step.type || 'step'}-${index}`}>
                    <div className={isUser ? 'stepIcon userStep' : 'stepIcon agentStep'}>
                      {isUser ? <UserRound size={16} /> : <Bot size={16} />}
                    </div>
                    <div className="stepBody">
                      <div className="stepMeta">
                        <strong>{step.label}</strong>
                        <span>{step.sortTime ? new Date(step.sortTime).toLocaleTimeString() : ''}</span>
                      </div>
                      <p>{step.content}</p>
                      <footer>
                        {step.agent_id ? <span>{String(step.agent_id).slice(0, 8)}</span> : null}
                        {step.channel ? <span>{step.channel}</span> : null}
                        {step.token_count !== undefined ? <span>{step.token_count} tokens</span> : null}
                        {step.cost_usd !== undefined ? <span>{Number(step.cost_usd) > 0 ? `$${Number(step.cost_usd).toFixed(6)}` : 'local $0'}</span> : null}
                      </footer>
                    </div>
                  </div>
                );
              })}
            </div>
            <footer className="runSummary">
              <span><CheckCircle2 size={14} /> {run.finalResponse ? 'Finished' : 'In progress'}</span>
              <span>{run.tokenCount} tokens</span>
              <span>{run.costUsd > 0 ? `$${run.costUsd.toFixed(6)}` : 'local $0'}</span>
              {run.traceUrl ? <a href={run.traceUrl} target="_blank" rel="noreferrer">Langfuse</a> : null}
            </footer>
          </article>
        ))}
      </section>
    </div>
  );
}
