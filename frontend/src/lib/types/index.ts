/**
 * Core types for the remote-agents frontend.
 * Maps to the backend's Pydantic models.
 */

// ---------------------------------------------------------------------------
// Session types
// ---------------------------------------------------------------------------

export interface SessionInfo {
  session_id: string;
  repo: string | null;
  name: string | null;
  is_live: boolean;
}

export interface SessionsResponse {
  live: SessionInfo[];
  cold: SessionInfo[];
}

export interface SpawnRequest {
  repo: string;
  name?: string;
}

export interface SpawnResponse {
  session_id: string;
}

export interface TerminateResponse {
  status: string;
}

export interface ReposResponse {
  repos: string[];
}

// ---------------------------------------------------------------------------
// RPC event types (from pi.dev)
// ---------------------------------------------------------------------------

export interface RpcEvent {
  type: string;
  [key: string]: unknown;
}

export interface ResponseEvent extends RpcEvent {
  type: 'response';
  id: string | null;
  command: string;
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

export interface AgentStartEvent extends RpcEvent {
  type: 'agent_start';
}

export interface AgentEndEvent extends RpcEvent {
  type: 'agent_end';
  messages: Message[];
}

export interface TurnStartEvent extends RpcEvent {
  type: 'turn_start';
}

export interface TurnEndEvent extends RpcEvent {
  type: 'turn_end';
  message?: Message;
  toolResults?: ToolResult[];
}

export interface MessageStartEvent extends RpcEvent {
  type: 'message_start';
  message: Message;
}

export interface MessageUpdateEvent extends RpcEvent {
  type: 'message_update';
  message: Message;
  assistantMessageEvent: AssistantMessageEvent;
}

export interface MessageEndEvent extends RpcEvent {
  type: 'message_end';
  message: Message;
}

export interface ToolExecutionStartEvent extends RpcEvent {
  type: 'tool_execution_start';
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
}

export interface ToolExecutionEndEvent extends RpcEvent {
  type: 'tool_execution_end';
  toolCallId: string;
  toolName: string;
  result?: ToolResult;
  isError: boolean;
}

export interface QueueUpdateEvent extends RpcEvent {
  type: 'queue_update';
  steering: string[];
  followUp: string[];
}

// ---------------------------------------------------------------------------
// Message types
// ---------------------------------------------------------------------------

export interface Message {
  role: 'user' | 'assistant' | 'toolResult' | 'bashExecution';
  content: string | ContentBlock[];
  timestamp?: number;
  [key: string]: unknown;
}

export interface ContentBlock {
  type: 'text' | 'thinking' | 'toolCall' | 'image';
  text?: string;
  thinking?: string;
  id?: string;
  name?: string;
  arguments?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ToolResult {
  content: ContentBlock[];
  [key: string]: unknown;
}

export interface AssistantMessageEvent {
  type: string;
  contentIndex?: number;
  delta?: string;
  content?: string;
  partial?: Message;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// WebSocket message types
// ---------------------------------------------------------------------------

export interface WsSnapshot {
  kind: 'snapshot';
  state: Record<string, unknown>;
  messages: Message[];
}

export interface WsEvent {
  kind: 'event';
  event: RpcEvent;
}

export interface WsError {
  kind: 'error';
  reason: string;
}

export type WsMessage = WsSnapshot | WsEvent | WsError;

// Client → Server commands
export interface WsCommand {
  type: 'prompt' | 'steer' | 'follow_up' | 'abort';
  message?: string;
}

// ---------------------------------------------------------------------------
// State types
// ---------------------------------------------------------------------------

export type AsyncStatus = 'idle' | 'loading' | 'streaming' | 'error' | 'success';

export interface RemoteData<T, E = string> {
  status: AsyncStatus;
  data?: T;
  error?: E;
  partial?: string;
}

// Session state from get_state
export interface SessionState {
  sessionId?: string;
  sessionName?: string;
  isStreaming?: boolean;
  messageCount?: number;
  pendingMessageCount?: number;
  [key: string]: unknown;
}
