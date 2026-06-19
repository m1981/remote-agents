<!--
  SessionView — message log, composer, steering controls.
  Implements UC-2 (Resume Live Session) and UC-4 (Steer/Terminate).
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { sessionStore } from '$lib/stores/session.svelte';
  import MessageBubble from '$lib/components/MessageBubble.svelte';

  interface Props {
    sessionId: string;
    onBack: () => void;
  }

  let { sessionId, onBack }: Props = $props();

  let inputText = $state('');

  onMount(() => {
    sessionStore.connect(sessionId);
  });

  onDestroy(() => {
    sessionStore.disconnect();
  });

  function handleSend() {
    if (!inputText.trim()) return;

    if (sessionStore.isStreaming) {
      sessionStore.sendSteer(inputText);
    } else {
      sessionStore.sendPrompt(inputText);
    }
    inputText = '';
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }
</script>

<div class="session-page">
  <header class="session-header">
    <div class="header-info">
      <button class="back-btn" onclick={onBack}>← Back</button>
      <h1>{sessionStore.sessionState.sessionName ?? sessionId.slice(0, 8)}</h1>
      <div class="status-badges">
        <span class="badge badge-{sessionStore.connectionStatus}">
          {sessionStore.connectionStatus}
        </span>
        {#if sessionStore.isStreaming}
          <span class="badge badge-streaming">streaming</span>
        {/if}
      </div>
    </div>
    <div class="header-actions">
      {#if sessionStore.isStreaming}
        <button class="btn btn-danger btn-sm" onclick={() => sessionStore.sendAbort()}>
          Abort
        </button>
      {/if}
    </div>
  </header>

  {#if sessionStore.status.status === 'error'}
    <div class="error-banner">
      {sessionStore.status.error}
    </div>
  {/if}

  <div class="messages-container">
    {#if sessionStore.messages.length === 0}
      <div class="empty-state">
        <p>No messages yet. Start the conversation below.</p>
      </div>
    {:else}
      {#each sessionStore.messages as message}
        <MessageBubble {message} />
      {/each}
    {/if}
  </div>

  <div class="composer">
    <div class="input-row">
      <textarea
        bind:value={inputText}
        onkeydown={handleKeydown}
        placeholder={sessionStore.isStreaming ? 'Type to steer...' : 'Type a message...'}
        rows="1"
      ></textarea>
      <button class="btn btn-primary" onclick={handleSend} disabled={!inputText.trim()}>
        {sessionStore.isStreaming ? 'Steer' : 'Send'}
      </button>
    </div>
    {#if sessionStore.isStreaming}
      <div class="composer-hints">
        <span class="hint">Agent is streaming. Messages will be sent as steering.</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .session-page {
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
    max-width: 900px;
    margin: 0 auto;
  }

  .session-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    background: var(--bg-secondary);
  }

  .header-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .back-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 0.875rem;
    padding: 0.25rem 0.5rem;
    min-height: auto;
  }

  .back-btn:hover {
    color: var(--text-primary);
  }

  .header-info h1 {
    font-size: 1rem;
    font-weight: 600;
  }

  .status-badges {
    display: flex;
    gap: 0.5rem;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    font-size: 0.625rem;
    font-weight: 600;
    border-radius: 9999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .badge-connected {
    background: var(--success-bg);
    color: var(--success);
  }

  .badge-connecting {
    background: var(--warning-bg);
    color: var(--warning);
  }

  .badge-disconnected {
    background: var(--error-bg);
    color: var(--error);
  }

  .badge-streaming {
    background: var(--primary-bg);
    color: var(--primary);
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }

  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error);
    padding: 0.75rem 1rem;
    margin: 0.5rem 1rem;
    border-radius: 0.5rem;
    font-size: 0.875rem;
  }

  .composer {
    padding: 0.75rem 1rem;
    border-top: 1px solid var(--border);
    background: var(--bg-secondary);
  }

  .input-row {
    display: flex;
    gap: 0.5rem;
  }

  .input-row textarea {
    flex: 1;
    padding: 0.625rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.875rem;
    font-family: inherit;
    resize: none;
    min-height: 2.25rem;
    max-height: 10rem;
  }

  .input-row textarea:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 2px var(--primary-bg);
  }

  .composer-hints {
    margin-top: 0.25rem;
  }

  .hint {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 0.5rem;
    border: none;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .btn:hover {
    opacity: 0.9;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--primary);
    color: white;
  }

  .btn-danger {
    background: var(--error);
    color: white;
  }

  .btn-sm {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
  }
</style>
