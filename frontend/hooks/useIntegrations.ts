import { useEffect, useState } from 'react';

import { getApiUrl } from '@/config/api';

export type IntegrationStatus = {
  telegram: {
    configured: boolean;
    polling_enabled: boolean;
    status: string;
    mode: string;
    channel: string;
    chat_scope: string;
    route: string;
  };
  langfuse: {
    configured: boolean;
    status: string;
    host: string | null;
  };
};

export function useIntegrations() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(getApiUrl('/api/integrations/status'));
        if (response.ok) {
          setStatus(await response.json());
        }
      } catch (error) {
        console.error('Failed to fetch integrations:', error);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  return { status, loading };
}
