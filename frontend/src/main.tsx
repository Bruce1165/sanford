import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { getAuthorizationHeaderValue } from './api';

async function ensureLatestFrontendBuild() {
  const scriptEl = document.querySelector<HTMLScriptElement>('script[type="module"][src]');
  const src = scriptEl?.getAttribute('src') || '';
  if (!src.includes('/assets/')) {
    return;
  }

  const localName = src.split('/').pop() || '';
  const localHash = (localName.startsWith('index-') && localName.endsWith('.js'))
    ? localName.slice('index-'.length, -'.js'.length)
    : '';
  if (!localHash) return;

  const url = new URL(window.location.href);
  const currentV = url.searchParams.get('v') || '';

  let remoteHash = '';
  try {
    const auth = getAuthorizationHeaderValue();
    const resp = await fetch('/api/version', {
      cache: 'no-store',
      headers: auth ? { Authorization: auth } : undefined,
    });
    if (!resp.ok) return;
    const data: any = await resp.json();
    remoteHash = String(data?.frontend?.entry_hash || '');
  } catch {
    return;
  }

  if (!remoteHash) return;
  if (remoteHash === localHash) return;
  if (currentV === remoteHash) return;

  url.searchParams.set('v', remoteHash);
  window.location.replace(url.toString());
}

const root = ReactDOM.createRoot(document.getElementById('root')!);
ensureLatestFrontendBuild()
  .catch(() => {})
  .finally(() => {
    root.render(React.createElement(App));
  });

console.log('React mounted');
