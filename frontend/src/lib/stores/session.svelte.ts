/**
 * Session Store — manages a single live session with WebSocket.
 * Handles event streaming, message state, and commands.
 */

import type {
  Message,
  RpcEvent,
  SessionState,
  WsCommand,
  RemoteData,
} from '$lib/types';
import { ws, type WsRepository } from '$lib/repositories/ws.repository';

function createSessionStore() {
  // --- State ---
  let sessionId = $state<string>('');
  let sessionState = $state<SessionState>({});
  let messages = $state<Message[]>([]);
  let status = $state<RemoteData<null>>({ status: 'idle' });
  let connectionStatus = $state<'connecting' | 'connected' | 'disconnected'>('disconnected');
  let events = $state<RpcEvent[]>([]); // Ring buffer of recent events

  // Unsubscribe functions
  let unsubscribers: Array<() => void> = [];

  return {
    // --- Reads ---
    get sessionId() {
      return sessionId;
    },
    get sessionState() {
      return sessionState;
    },
    get messages() {
      return messages;
    },
    get status() {
      return status;
    },
    get connectionStatus() {
      return connectionStatus;
    },
    get events() {
      return events;
    },
    get isStreaming() {
      return sessionState.isStreaming ?? false;
    },
    get isConnected() {
      return connectionStatus === 'connected';
    },

    // --- Actions ---
    connect(id: string) {
      // Disconnect previous
      this.disconnect();

      sessionId = id;
      status = { status: 'loading' };
      events = [];
      messages = [];

      // Subscribe to WS events
      unsubscribers.push(
        ws.onSnapshot((state, msgs) => {
          sessionState = state as SessionState;
          messages = msgs as Message[];
          status = { status: 'success', data: null };
        }),
      );

      unsubscribers.push(
        ws.onEvent((event) => {
          this.handleEvent(event);
        }),
      );

      unsubscribers.push(
        ws.onError((reason) => {
          status = { status: 'error', error: reason };
        }),
      );

      unsubscribers.push(
        ws.onStatus((s) => {
          connectionStatus = s;
        }),
      );

      // Connect
      ws.connect(id);
    },

    disconnect() {
      // Unsubscribe all
      for (const unsub of unsubscribers) {
        unsub();
      }
      unsubscribers = [];
      ws.disconnect();
      sessionId = '';
      sessionState = {};
      messages = [];
      events = [];
      status = { status: 'idle' };
      connectionStatus = 'disconnected';
    },

    // --- Commands ---
    sendPrompt(message: string) {
      const cmd: WsCommand = { type: 'prompt', message };
      ws.send(cmd);
    },

    sendSteer(message: string) {
      const cmd: WsCommand = { type: 'steer', message };
      ws.send(cmd);
    },

    sendFollowUp(message: string) {
      const cmd: WsCommand = { type: 'follow_up', message };
      ws.send(cmd);
    },

    sendAbort() {
      const cmd: WsCommand = { type: 'abort' };
      ws.send(cmd);
    },

    // --- Internal ---
    handleEvent(event: RpcEvent) {
      // Add to ring buffer (keep last 200)
      events = [...events, event].slice(-200);

      // Handle specific event types
      switch (event.type) {
        case 'message_update':
          this.handleMessageUpdate(event);
          break;
        case 'agent_start':
          status = { status: 'streaming' };
          break;
        case 'agent_end':
          status = { status: 'success', data: null };
          break;
      }
    },

    handleMessageUpdate(event: RpcEvent) {
      const { message, assistantMessageEvent } = event as {
        message?: Message;
        assistantMessageEvent?: { type: string; delta?: string; content?: string };
      };

      if (!message || !assistantMessageEvent) return;

      // Update the last assistant message or create new one
      const lastIdx = messages.length - 1;
      const lastMsg = messages[lastIdx];

      if (lastMsg?.role === 'assistant' && assistantMessageEvent.type === 'text_delta') {
        // Append delta to existing message
        const currentText =
          typeof lastMsg.content === 'string' ? lastMsg.content : '';
        messages[lastIdx] = {
          ...lastMsg,
          content: currentText + (assistantMessageEvent.delta ?? ''),
        };
      } else if (assistantMessageEvent.type === 'text_delta') {
        // New assistant message
        messages = [
          ...messages,
          { role: 'assistant', content: assistantMessageEvent.delta ?? '' },
        ];
      }
    },
  };
}

// Singleton
export const sessionStore = createSessionStore();
