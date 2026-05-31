import { useEffect, useState } from 'react';
import { API_BASE_URL } from '@/config/api';

export function useWebSocket(path: string) {
  const [events, setEvents] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const protocol = API_BASE_URL.startsWith('https') ? 'wss' : 'ws';
    const host = API_BASE_URL.replace('https://', '').replace('http://', '');
    const socket = new WebSocket(`${protocol}://${host}${path}`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (message) => {
      setEvents((current) => [JSON.parse(message.data), ...current].slice(0, 100));
    };
    return () => socket.close();
  }, [path]);

  return { connected, events };
}
