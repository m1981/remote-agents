/**
 * WebSocket Repository — manages WS connection with auto-reconnect.
 * Emits typed events for the store to consume.
 */

import type { WsCommand, WsMessage, WsEvent, WsSnapshot, WsError, RpcEvent } from '$lib/types';

export type WsEventHandler = (event: RpcEvent) => void;
export type WsSnapshotHandler = (state: Record<string, unknown>, messages: unknown[]) => void;
export type WsErrorHandler = (reason: string) => void;
export type WsStatusHandler = (status: 'connecting' | 'connected' | 'disconnected') => void;

export class WsRepository {
  private ws: WebSocket | null = null;
  private sessionId: string = '';
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private isManualClose = false;

  // Event handlers
  private eventHandlers: Set<WsEventHandler> = new Set();
  private snapshotHandlers: Set<WsSnapshotHandler> = new Set();
  private errorHandlers: Set<WsErrorHandler> = new Set();
  private statusHandlers: Set<WsStatusHandler> = new Set();

  connect(sessionId: string): void {
    this.sessionId = sessionId;
    this.isManualClose = false;
    this.doConnect();
  }

  disconnect(): void {
    this.isManualClose = true;
    this.clearReconnect();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.notifyStatus('disconnected');
  }

  send(command: WsCommand): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[WsRepository] Cannot send: not connected');
      return;
    }
    this.ws.send(JSON.stringify(command));
  }

  // ---------------------------------------------------------------------------
  // Event subscription
  // ---------------------------------------------------------------------------

  onEvent(handler: WsEventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  onSnapshot(handler: WsSnapshotHandler): () => void {
    this.snapshotHandlers.add(handler);
    return () => this.snapshotHandlers.delete(handler);
  }

  onError(handler: WsErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  onStatus(handler: WsStatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  // ---------------------------------------------------------------------------
  // Internal
  // ---------------------------------------------------------------------------

  private doConnect(): void {
    if (this.ws) {
      this.ws.close();
    }

    this.notifyStatus('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/sessions/${this.sessionId}`;

    try {
      this.ws = new WebSocket(url);
    } catch (err) {
      console.error('[WsRepository] Failed to create WebSocket:', err);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log('[WsRepository] Connected:', this.sessionId);
      this.reconnectDelay = 1000; // Reset delay on success
      this.notifyStatus('connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        this.handleMessage(msg);
      } catch (err) {
        console.error('[WsRepository] Failed to parse message:', err);
      }
    };

    this.ws.onclose = () => {
      console.log('[WsRepository] Disconnected');
      this.notifyStatus('disconnected');
      if (!this.isManualClose) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (event) => {
      console.error('[WsRepository] WebSocket error:', event);
    };
  }

  private handleMessage(msg: WsMessage): void {
    switch (msg.kind) {
      case 'snapshot':
        this.handleSnapshot(msg as WsSnapshot);
        break;
      case 'event':
        this.handleEvent(msg as WsEvent);
        break;
      case 'error':
        this.handleError(msg as WsError);
        break;
    }
  }

  private handleSnapshot(msg: WsSnapshot): void {
    for (const handler of this.snapshotHandlers) {
      handler(msg.state, msg.messages);
    }
  }

  private handleEvent(msg: WsEvent): void {
    for (const handler of this.eventHandlers) {
      handler(msg.event);
    }
  }

  private handleError(msg: WsError): void {
    for (const handler of this.errorHandlers) {
      handler(msg.reason);
    }
  }

  private notifyStatus(status: 'connecting' | 'connected' | 'disconnected'): void {
    for (const handler of this.statusHandlers) {
      handler(status);
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnect();
    console.log(`[WsRepository] Reconnecting in ${this.reconnectDelay}ms...`);
    this.reconnectTimer = setTimeout(() => {
      this.doConnect();
      // Exponential backoff
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    }, this.reconnectDelay);
  }

  private clearReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

// Singleton instance
export const ws = new WsRepository();
