import Link from 'next/link';
import { Bot, GitBranch, Radio } from 'lucide-react';
import { Layout } from '../components/Layout';

export default function Home() {
  return (
    <Layout>
      <div className="pageHeader">
        <h1>AIAgentOrchestrationPlatform</h1>
        <p>Create agents, wire workflows, and watch executions stream in real time.</p>
      </div>
      <div className="metricGrid">
        <Link className="metric" href="/agents"><Bot size={22} /><strong>Agents</strong><span>Configure behavior, models, tools, and memory.</span></Link>
        <Link className="metric" href="/workflows"><GitBranch size={22} /><strong>Workflows</strong><span>Connect agents into LangGraph executions.</span></Link>
        <Link className="metric" href="/monitor"><Radio size={22} /><strong>Monitor</strong><span>Inspect broker events as runs progress.</span></Link>
      </div>
    </Layout>
  );
}
