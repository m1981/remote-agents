/**
 * Sessions Store — manages session list state.
 * Follows closure-based store pattern from stack-svelte skill.
 */

import type { SessionInfo, RemoteData } from '$lib/types';
import { api } from '$lib/repositories/api.repository';

function createSessionsStore() {
  // --- State ---
  let live = $state<SessionInfo[]>([]);
  let cold = $state<SessionInfo[]>([]);
  let repos = $state<string[]>([]);
  let status = $state<RemoteData<null>>({ status: 'idle' });

  return {
    // --- Reads ---
    get live() {
      return live;
    },
    get cold() {
      return cold;
    },
    get repos() {
      return repos;
    },
    get status() {
      return status;
    },
    get isLoading() {
      return status.status === 'loading';
    },

    // --- Grouped by repo ---
    get groupedLive(): Map<string, SessionInfo[]> {
      const groups = new Map<string, SessionInfo[]>();
      for (const s of live) {
        const repo = s.repo ?? 'unknown';
        if (!groups.has(repo)) groups.set(repo, []);
        groups.get(repo)!.push(s);
      }
      return groups;
    },

    get groupedCold(): Map<string, SessionInfo[]> {
      const groups = new Map<string, SessionInfo[]>();
      for (const s of cold) {
        const repo = s.repo ?? 'unknown';
        if (!groups.has(repo)) groups.set(repo, []);
        groups.get(repo)!.push(s);
      }
      return groups;
    },

    // --- Actions ---
    async fetchRepos() {
      try {
        const data = await api.listRepos();
        repos = data.repos;
      } catch (err) {
        console.error('[SessionsStore] Failed to fetch repos:', err);
      }
    },

    async fetchSessions() {
      status = { status: 'loading' };
      try {
        const data = await api.listSessions();
        live = data.live;
        cold = data.cold;
        status = { status: 'success', data: null };
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to fetch sessions';
        status = { status: 'error', error: msg };
      }
    },

    async spawnSession(repo: string, name?: string) {
      status = { status: 'loading' };
      try {
        const { session_id } = await api.spawnSession({ repo, name });
        // Refresh list
        await this.fetchSessions();
        return session_id;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to spawn session';
        status = { status: 'error', error: msg };
        throw err;
      }
    },

    async terminateSession(sessionId: string) {
      try {
        await api.terminateSession(sessionId);
        // Refresh list
        await this.fetchSessions();
      } catch (err) {
        console.error('[SessionsStore] Failed to terminate:', err);
        throw err;
      }
    },
  };
}

export const sessionsStore = createSessionsStore();
