import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles/global.css';

function bootstrapApiKeyFromUrl(): void {
  const url = new URL(window.location.href);
  const apiKey = url.searchParams.get('nexra_api_key') ?? url.searchParams.get('api_key');
  const userEmail = url.searchParams.get('nexra_user_email') ?? url.searchParams.get('user_email');
  if (!apiKey && !userEmail) return;

  if (apiKey) {
    localStorage.setItem('nexra_api_key', apiKey);
  }
  if (userEmail) {
    localStorage.setItem('nexra_user_email', userEmail.toLowerCase());
  }
  url.searchParams.delete('nexra_api_key');
  url.searchParams.delete('api_key');
  url.searchParams.delete('nexra_user_email');
  url.searchParams.delete('user_email');
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
