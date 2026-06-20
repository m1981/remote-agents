/**
 * Session Store — manages a single live session with WebSocket.
 * Handles event streaming, message state, and commands.
 *
 * Supports all pi RPC event types:
 * - thinking_start/delta/end → thinking content blocks
 * - toolcall_start/delta/end → toolCall content blocks
 * - text_start/delta/end → text content blocks
 * - tool_execution_start/update/end → tool execution progress
 */

import type {
  Message,
  ContentBlock,
  RpcEvent,
  SessionState,
  WsCommand,
  RemoteData,
} from '$lib/types';
import { ws, type WsRepository } from '$lib/repositories/ws.repository';

/** Tracks tool execution progress by toolCallId. */
interface ToolExecution {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  output: string;
  isRunning: boolean;
  isError: boolean;
}

function createSessionStore() {
  // --- State ---
  let sessionId = $state<string>('');
  let sessionState = $state<SessionState>({});
  let messages = $state<Message[]>([]);
  let status = $state<RemoteData<null>>({ status: 'idle' });
  let connectionStatus = $state<'connecting' | 'connected' | 'disconnected'>('disconnected');
  let events = $state<RpcEvent[]>([]); // Ring buffer of recent events
  let toolExecutions = $state<Map<string, ToolExecution>>(new Map());

  // Streaming state — accumulates content blocks during a turn
  let streamingBlocks = $state<ContentBlock[]>([]);
  let streamingMessageIdx = $state<number>(-1);

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
    get toolExecutions() {
      return toolExecutions;
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
      toolExecutions = new Map();
      streamingBlocks = [];
      streamingMessageIdx = -1;

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
      toolExecutions = new Map();
      streamingBlocks = [];
      streamingMessageIdx = -1;
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

      switch (event.type) {
        case 'message_start':
          this.handleMessageStart(event);
          break;
        case 'message_update':
          this.handleMessageUpdate(event);
          break;
        case 'message_end':
          this.handleMessageEnd(event);
          break;
        case 'tool_execution_start':
          this.handleToolExecutionStart(event);
          break;
        case 'tool_execution_update':
          this.handleToolExecutionUpdate(event);
          break;
        case 'tool_execution_end':
          this.handleToolExecutionEnd(event);
          break;
        case 'agent_start':
          status = { status: 'streaming' };
          break;
        case 'agent_end':
          this.handleAgentEnd(event);
          break;
      }
    },

    handleMessageStart(event: RpcEvent) {
      const msg = event.message as Message | undefined;
      if (!msg) return;

      // Add message to list
      messages = [...messages, msg];

      // If assistant message, start tracking streaming blocks
      if (msg.role === 'assistant') {
        streamingBlocks = Array.isArray(msg.content) ? [...msg.content] : [];
        streamingMessageIdx = messages.length - 1;
      }
    },

    handleMessageUpdate(event: RpcEvent) {
      const { assistantMessageEvent: ame } = event as {
        assistantMessageEvent?: {
          type: string;
          contentIndex?: number;
          delta?: string;
          content?: string;
          toolCall?: ContentBlock;
          partial?: Message;
        };
      };

      if (!ame) return;

      const ci = ame.contentIndex ?? 0;

      switch (ame.type) {
        case 'thinking_start':
          this.ensureBlock(ci, { type: 'thinking', thinking: '' });
          break;

        case 'thinking_delta':
          this.appendToBlock(ci, 'thinking', ame.delta ?? '');
          break;

        case 'thinking_end':
          this.setBlockContent(ci, 'thinking', ame.content ?? '');
          break;

        case 'toolcall_start':
          this.ensureBlock(ci, { type: 'toolCall', id: '', name: '', arguments: {} });
          break;

        case 'toolcall_delta':
          // toolcall_delta streams the arguments JSON
          this.appendToBlockArgs(ci, ame.delta ?? '');
          break;

        case 'toolcall_end':
          if (ame.toolCall) {
            this.setBlockFromToolCall(ci, ame.toolCall as ContentBlock);
          }
          break;

        case 'text_start':
          this.ensureBlock(ci, { type: 'text', text: '' });
          break;

        case 'text_delta':
          this.appendToBlock(ci, 'text', ame.delta ?? '');
          break;

        case 'text_end':
          this.setBlockContent(ci, 'text', ame.content ?? '');
          break;

        case 'done':
          // Message generation complete
          break;
      }
    },

    handleMessageEnd(event: RpcEvent) {
      // Finalize the streaming message with all accumulated blocks
      if (streamingMessageIdx >= 0 && streamingBlocks.length > 0) {
        const updated = [...messages];
        updated[streamingMessageIdx] = {
          ...updated[streamingMessageIdx],
          content: [...streamingBlocks],
        };
        messages = updated;
      }
      streamingBlocks = [];
      streamingMessageIdx = -1;
    },

    handleToolExecutionStart(event: RpcEvent) {
      const { toolCallId, toolName, args } = event as {
        toolCallId: string;
        toolName: string;
        args: Record<string, unknown>;
      };
      const newMap = new Map(toolExecutions);
      newMap.set(toolCallId, {
        toolCallId,
        toolName,
        args: args ?? {},
        output: '',
        isRunning: true,
        isError: false,
      });
      toolExecutions = newMap;
    },

    handleToolExecutionUpdate(event: RpcEvent) {
      const { toolCallId, partialResult } = event as {
        toolCallId: string;
        partialResult?: { content?: Array<{ type: string; text?: string }> };
      };
      const existing = toolExecutions.get(toolCallId);
      if (!existing) return;

      const outputText = partialResult?.content?.[0]?.text ?? '';
      const newMap = new Map(toolExecutions);
      newMap.set(toolCallId, { ...existing, output: outputText });
      toolExecutions = newMap;
    },

    handleToolExecutionEnd(event: RpcEvent) {
      const { toolCallId, result, isError } = event as {
        toolCallId: string;
        result?: { content?: Array<{ type: string; text?: string }> };
        isError: boolean;
      };
      const existing = toolExecutions.get(toolCallId);
      if (!existing) return;

      const finalOutput = result?.content?.[0]?.text ?? existing.output;
      const newMap = new Map(toolExecutions);
      newMap.set(toolCallId, {
        ...existing,
        output: finalOutput,
        isRunning: false,
        isError: isError ?? false,
      });
      toolExecutions = newMap;
    },

    handleAgentEnd(event: RpcEvent) {
      status = { status: 'success', data: null };
      // Clear tool executions after a delay
      setTimeout(() => {
        toolExecutions = new Map();
      }, 2000);
    },

    // --- Content block helpers ---

    /** Ensure a block exists at the given contentIndex. */
    ensureBlock(index: number, block: ContentBlock) {
      while (streamingBlocks.length <= index) {
        streamingBlocks = [...streamingBlocks, { type: 'text', text: '' }];
      }
      if (!streamingBlocks[index] || streamingBlocks[index].type !== block.type) {
        const updated = [...streamingBlocks];
        updated[index] = block;
        streamingBlocks = updated;
      }
      this.syncStreamingToMessage();
    },

    /** Append text to a block's content field (thinking or text). */
    appendToBlock(index: number, field: 'thinking' | 'text', delta: string) {
      if (index >= streamingBlocks.length) return;
      const block = streamingBlocks[index];
      const updated = [...streamingBlocks];
      updated[index] = {
        ...block,
        [field]: ((block[field] as string) ?? '') + delta,
      };
      streamingBlocks = updated;
      this.syncStreamingToMessage();
    },

    /** Append to toolcall arguments (streams as JSON string).
     *  We buffer args as a hidden field and parse on toolcall_end.
     */
    appendToBlockArgs(index: number, delta: string) {
      if (index >= streamingBlocks.length) return;
      const block = streamingBlocks[index] as ContentBlock & { _argsBuf?: string };
      const updated = [...streamingBlocks];
      updated[index] = {
        ...block,
        _argsBuf: (block._argsBuf ?? '') + delta,
      };
      streamingBlocks = updated;
      this.syncStreamingToMessage();
    },

    /** Set a block's content from the end event. */
    setBlockContent(index: number, field: 'thinking' | 'text', content: string) {
      if (index >= streamingBlocks.length) return;
      const updated = [...streamingBlocks];
      updated[index] = {
        ...updated[index],
        [field]: content,
      };
      streamingBlocks = updated;
      this.syncStreamingToMessage();
    },

    /** Set a block from a full toolCall object (from toolcall_end). */
    setBlockFromToolCall(index: number, toolCall: ContentBlock) {
      if (index >= streamingBlocks.length) return;
      const updated = [...streamingBlocks];
      updated[index] = {
        type: 'toolCall',
        id: toolCall.id ?? '',
        name: toolCall.name ?? '',
        arguments: toolCall.arguments ?? {},
      };
      streamingBlocks = updated;
      this.syncStreamingToMessage();
    },

    /** Sync streamingBlocks to the current assistant message. */
    syncStreamingToMessage() {
      if (streamingMessageIdx < 0 || streamingMessageIdx >= messages.length) return;
      const updated = [...messages];
      updated[streamingMessageIdx] = {
        ...updated[streamingMessageIdx],
        content: [...streamingBlocks],
      };
      messages = updated;
    },
  };
}

// Singleton
export const sessionStore = createSessionStore();
