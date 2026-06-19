<!--
  Root App — simple SPA router.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import SessionsView from '$lib/components/SessionsView.svelte';
  import SessionView from '$lib/components/SessionView.svelte';

  // Simple hash-based routing
  let currentPath = $state(window.location.hash.slice(1) || '/');

  onMount(() => {
    function handleHashChange() {
      currentPath = window.location.hash.slice(1) || '/';
    }
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  });

  function navigate(path: string) {
    window.location.hash = path;
  }

  // Extract session ID from path
  const sessionId = $derived(() => {
    const match = currentPath.match(/^\/sessions\/(.+)$/);
    return match ? match[1] : null;
  });
</script>

<div class="app">
  <nav class="navbar">
    <a href="#/" class="logo">🤖 remote-agents</a>
  </nav>

  <main class="content">
    {#if sessionId()}
      <SessionView sessionId={sessionId()} onBack={() => navigate('/')} />
    {:else}
      <SessionsView onNavigate={(path) => navigate(path)} />
    {/if}
  </main>
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    min-height: 100dvh;
    background: var(--bg-primary);
  }

  .navbar {
    display: flex;
    align-items: center;
    padding: 0.75rem 1rem;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
  }

  .logo {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
    text-decoration: none;
  }

  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
