// API Configuration
// In development, use the environment variable or detect from hostname
const getApiBaseUrl = (): string => {
  // Server-side (during build)
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }
  
  // Client-side: use environment variable if set
  if (process.env.NEXT_PUBLIC_API_URL) {
    console.log('Using API_URL from env:', process.env.NEXT_PUBLIC_API_URL);
    return process.env.NEXT_PUBLIC_API_URL;
  }
  
  // Fallback: construct from current hostname + port 8000
  // This handles localhost, 127.0.0.1, and custom domains
  const protocol = window.location.protocol;
  const port = '8000';
  const url = `${protocol}//${window.location.hostname}:${port}`;
  console.log('Using constructed API_URL:', url);
  return url;
};

export const API_BASE_URL = getApiBaseUrl();

export const getApiUrl = (path: string): string => {
  const fullUrl = `${API_BASE_URL}${path.startsWith('/') ? path : '/' + path}`;
  console.debug('API URL:', fullUrl);
  return fullUrl;
};
