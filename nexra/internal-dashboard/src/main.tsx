import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles/global.css';

function bootstrapApiKeyFromUrl(): void {
  const url = new URL(window.location.href);
  const apiKey = url.searchParams.get('nexra_api_key') ?? url.searchParams.get('api_key');
  if (!apiKey) return;

  localStorage.setItem('nexra_api_key', apiKey);
  url.searchParams.delete('nexra_api_key');
  url.searchParams.delete('api_key');
  window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
}

bootstrapApiKeyFromUrl();

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
