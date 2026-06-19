/**
 * API Repository — typed REST client for the backend.
 * Follows repository pattern: swap backends, mock in tests, add caching.
 */

import type {
  ReposResponse,
  SessionsResponse,
  SpawnRequest,
  SpawnResponse,
  TerminateResponse,
} from '$lib/types';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class ApiRepository {
  constructor(private baseUrl: string = '') {}

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => 'Unknown error');
      throw new ApiError(res.status, text);
    }

    return res.json();
  }

  // ---------------------------------------------------------------------------
  // Repos
  // ---------------------------------------------------------------------------

  async listRepos(): Promise<ReposResponse> {
    return this.request<ReposResponse>('/repos');
  }

  // ---------------------------------------------------------------------------
  // Sessions
  // ---------------------------------------------------------------------------

  async listSessions(): Promise<SessionsResponse> {
    return this.request<SessionsResponse>('/sessions');
  }

  async spawnSession(req: SpawnRequest): Promise<SpawnResponse> {
    return this.request<SpawnResponse>('/sessions', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  }

  async terminateSession(sessionId: string): Promise<TerminateResponse> {
    return this.request<TerminateResponse>(`/sessions/${sessionId}/terminate`, {
      method: 'POST',
    });
  }
}

// Singleton instance
export const api = new ApiRepository();
