<!--
  SessionsView — lists live and cold sessions grouped by repo.
  Implements UC-5 (Survey Sessions).
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { sessionsStore } from '$lib/stores/sessions.svelte';

  interface Props {
    onNavigate: (path: string) => void;
  }

  let { onNavigate }: Props = $props();

  let selectedRepo = $state<string>('');
  let sessionName = $state<string>('');
  let showNewSession = $state(false);

  onMount(() => {
    sessionsStore.fetchRepos();
    sessionsStore.fetchSessions();
  });

  async function handleSpawn() {
    if (!selectedRepo) return;
    try {
      const sessionId = await sessionsStore.spawnSession(selectedRepo, sessionName || undefined);
      showNewSession = false;
      sessionName = '';
      onNavigate(`/sessions/${sessionId}`);
    } catch (err) {
      console.error('Failed to spawn:', err);
    }
  }

  async function handleTerminate(sessionId: string) {
    if (!confirm('Terminate this session?')) return;
    try {
      await sessionsStore.terminateSession(sessionId);
    } catch (err) {
      console.error('Failed to terminate:', err);
    }
  }
</script>

<div class="sessions-page">
  <header class="page-header">
    <h1>Sessions</h1>
    <button class="btn btn-primary" onclick={() => showNewSession = !showNewSession}>
      {showNewSession ? 'Cancel' : '+ New Session'}
    </button>
  </header>

  {#if showNewSession}
    <div class="new-session-form">
      <h2>Start New Session</h2>
      <div class="form-group">
        <label for="repo">Repository</label>
        <select id="repo" bind:value={selectedRepo}>
          <option value="">Select a repo...</option>
          {#each sessionsStore.repos as repo}
            <option value={repo}>{repo}</option>
          {/each}
        </select>
      </div>
      <div class="form-group">
        <label for="name">Name (optional)</label>
        <input id="name" type="text" bind:value={sessionName} placeholder="e.g., fix-auth-bug" />
      </div>
      <button class="btn btn-primary" onclick={handleSpawn} disabled={!selectedRepo || sessionsStore.isLoading}>
        {sessionsStore.isLoading ? 'Starting...' : 'Start Session'}
      </button>
    </div>
  {/if}

  {#if sessionsStore.status.status === 'error'}
    <div class="error-banner">
      {sessionsStore.status.error}
    </div>
  {/if}

  <section class="session-section">
    <h2>🟢 Live Sessions</h2>
    {#if sessionsStore.live.length === 0}
      <p class="empty-state">No live sessions</p>
    {:else}
      {#each [...sessionsStore.groupedLive.entries()] as [repo, sessions]}
        <div class="repo-group">
          <h3 class="repo-name">{repo}</h3>
          <div class="session-list">
            {#each sessions as session}
              <div class="session-card live">
                <div class="session-info">
                  <button class="session-link" onclick={() => onNavigate(`/sessions/${session.session_id}`)}>
                    <span class="session-name">{session.name ?? session.session_id.slice(0, 8)}</span>
                    <span class="session-id">{session.session_id.slice(0, 8)}...</span>
                  </button>
                </div>
                <button class="btn btn-danger btn-sm" onclick={() => handleTerminate(session.session_id)}>
                  Terminate
                </button>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    {/if}
  </section>

  <section class="session-section">
    <h2>⚪ Cold Sessions</h2>
    {#if sessionsStore.cold.length === 0}
      <p class="empty-state">No cold sessions</p>
    {:else}
      {#each [...sessionsStore.groupedCold.entries()] as [repo, sessions]}
        <div class="repo-group">
          <h3 class="repo-name">{repo}</h3>
          <div class="session-list">
            {#each sessions as session}
              <div class="session-card cold">
                <div class="session-info">
                  <span class="session-name">{session.name ?? session.session_id.slice(0, 8)}</span>
                  <span class="session-id">{session.session_id.slice(0, 8)}...</span>
                </div>
                <button class="btn btn-secondary btn-sm" onclick={() => onNavigate(`/sessions/${session.session_id}`)}>
                  Resume
                </button>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    {/if}
  </section>
</div>

<style>
  .sessions-page {
    max-width: 800px;
    margin: 0 auto;
    padding: 1.5rem;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
  }

  .new-session-form {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .new-session-form h2 {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 1rem;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    font-size: 0.875rem;
    font-weight: 500;
    margin-bottom: 0.25rem;
    color: var(--text-secondary);
  }

  .form-group select,
  .form-group input {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.875rem;
  }

  .session-section {
    margin-bottom: 2rem;
  }

  .session-section h2 {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 1rem;
  }

  .repo-group {
    margin-bottom: 1rem;
  }

  .repo-name {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
    padding-left: 0.5rem;
  }

  .session-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .session-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
  }

  .session-card.live {
    border-left: 3px solid var(--success);
  }

  .session-card.cold {
    border-left: 3px solid var(--text-muted);
  }

  .session-info {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .session-link {
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    color: var(--text-primary);
    padding: 0;
    min-height: auto;
  }

  .session-link:hover {
    color: var(--primary);
  }

  .session-name {
    font-weight: 500;
  }

  .session-id {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: monospace;
  }

  .empty-state {
    color: var(--text-muted);
    font-size: 0.875rem;
    padding: 1rem;
    text-align: center;
    background: var(--bg-secondary);
    border-radius: 0.5rem;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error);
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
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

  .btn-secondary {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border);
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
