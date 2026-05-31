import { Layout } from '../components/Layout';
import { Monitor } from '../components/Monitor';

export default function MonitorPage() {
  return (
    <Layout>
      <div className="pageHeader">
        <h1>Monitor</h1>
      </div>
      <Monitor />
    </Layout>
  );
}
