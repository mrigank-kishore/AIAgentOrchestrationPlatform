import { MessageCircle, Radio, Route, Shield, SquareActivity } from 'lucide-react';

import { Layout } from '../components/Layout';
import { useIntegrations } from '../hooks/useIntegrations';

export default function IntegrationsPage() {
  const { status, loading } = useIntegrations();
  const telegram = status?.telegram;
  const langfuse = status?.langfuse;
  const telegramPollingEnabled = telegram?.polling_enabled ?? telegram?.status === 'polling';
  const telegramActive = Boolean(telegram?.configured && telegramPollingEnabled);

  return (
    <Layout>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">Connected channels</span>
          <h1>Integrations</h1>
        </div>
        <div className="headerStats">
          <strong>{telegramActive ? 1 : 0}</strong>
          <span>active</span>
        </div>
      </div>

      <div className="integrationGrid">
        <article className="integrationPanel">
          <div className="cardHeader">
            <div>
              <span className="eyebrow">Telegram</span>
              <h2>Bot channel</h2>
            </div>
            <MessageCircle size={24} />
          </div>
          <div className="statusLine">
            <span className={telegramActive ? 'statusDot on' : 'statusDot'} />
            <strong>{loading ? 'Checking' : telegramActive ? 'Polling' : telegram?.configured ? 'Configured, paused' : 'Disabled'}</strong>
          </div>
          <dl className="detailList">
            <div><dt>Mode</dt><dd>{telegram?.mode || 'long_polling'}</dd></div>
            <div><dt>Polling</dt><dd>{telegramPollingEnabled ? 'Enabled' : 'Disabled'}</dd></div>
            <div><dt>Channel</dt><dd>{telegram?.channel || 'telegram'}</dd></div>
            <div><dt>Scope</dt><dd>{telegram?.chat_scope || 'private'}</dd></div>
            <div><dt>Route</dt><dd>{telegram?.route || 'default_workflow'}</dd></div>
          </dl>
        </article>

        <article className="integrationPanel">
          <div className="cardHeader">
            <div>
              <span className="eyebrow">Langfuse</span>
              <h2>Tracing</h2>
            </div>
            <SquareActivity size={24} />
          </div>
          <div className="statusLine">
            <span className={langfuse?.configured ? 'statusDot on' : 'statusDot'} />
            <strong>{loading ? 'Checking' : langfuse?.configured ? 'Configured' : 'Disabled'}</strong>
          </div>
          <dl className="detailList">
            <div><dt>Host</dt><dd>{langfuse?.host || 'Not set'}</dd></div>
            <div><dt>Visibility</dt><dd>Trace links in Monitor</dd></div>
          </dl>
          {langfuse?.host ? (
            <a className="primary linkButton" href={langfuse.host} target="_blank" rel="noreferrer">Open Langfuse</a>
          ) : null}
        </article>

        <section className="metricPanel">
          <Radio size={20} />
          <div>
            <span>Runtime</span>
            <strong>{telegram?.status || 'unknown'}</strong>
          </div>
        </section>
        <section className="metricPanel">
          <Route size={20} />
          <div>
            <span>Workflow entry</span>
            <strong>{telegram?.route || 'default_workflow'}</strong>
          </div>
        </section>
        <section className="metricPanel">
          <Shield size={20} />
          <div>
            <span>Chat scope</span>
            <strong>{telegram?.chat_scope || 'private'}</strong>
          </div>
        </section>
      </div>
    </Layout>
  );
}
