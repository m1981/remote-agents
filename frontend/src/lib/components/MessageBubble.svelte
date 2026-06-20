<!--
  MessageBubble — renders a single message in the conversation.
  Handles user, assistant, and tool result messages.
  Supports thinking blocks, tool calls, and tool execution progress.
-->
<script lang="ts">
  import type { Message, ContentBlock } from '$lib/types';
  import { sessionStore } from '$lib/stores/session.svelte';

  interface Props {
    message: Message;
  }

  let { message }: Props = $props();

  const isUser = $derived(message.role === 'user');
  const isAssistant = $derived(message.role === 'assistant');

  const contentBlocks = $derived.by(() => {
    if (typeof message.content === 'string') {
      return message.content ? [{ type: 'text', text: message.content }] : [];
    }
    if (Array.isArray(message.content)) {
      return message.content;
    }
    return [];
  });

  const textContent = $derived(() => {
    return contentBlocks
      .filter((b: ContentBlock) => b.type === 'text')
      .map((b: ContentBlock) => b.text ?? '')
      .join('');
  });

  const thinkingBlocks = $derived(() => {
    return contentBlocks.filter((b: ContentBlock) => b.type === 'thinking');
  });

  const toolCalls = $derived(() => {
    return contentBlocks.filter((b: ContentBlock) => b.type === 'toolCall');
  });

  /** Get tool execution progress for a toolCall. */
  function getToolExecution(toolCallId: string) {
    return sessionStore.toolExecutions.get(toolCallId);
  }

  /** Truncate long text for display. */
  function truncate(text: string, max: number = 200): string {
    if (text.length <= max) return text;
    return text.slice(0, max) + '…';
  }

  /** Format args for display. */
  function formatArgs(args: Record<string, unknown>): string {
    const entries = Object.entries(args);
    if (entries.length === 0) return '';
    return entries
      .map(([k, v]) => {
        const val = typeof v === 'string' ? truncate(v, 100) : JSON.stringify(v);
        return `${k}: ${val}`;
      })
      .join(', ');
  }
</script>

<div class="message" class:user={isUser} class:assistant={isAssistant}>
  <div class="message-header">
    <span class="role">
      {#if isUser}
        👤 You
      {:else if isAssistant}
        🤖 Agent
      {:else}
        ⚙️ {message.role}
      {/if}
    </span>
  </div>

  <div class="message-content">
    <!-- Thinking blocks -->
    {#each thinkingBlocks() as block}
      <details class="thinking">
        <summary>
          💭 Thinking
          {#if block.thinking}
            <span class="thinking-preview">— {truncate(block.thinking, 60)}</span>
          {/if}
        </summary>
        <pre>{block.thinking}</pre>
      </details>
    {/each}

    <!-- Tool calls -->
    {#each toolCalls() as tool}
      {@const exec = tool.id ? getToolExecution(tool.id) : undefined}
      <div class="tool-call" class:running={exec?.isRunning} class:error={exec?.isError}>
        <div class="tool-call-header">
          <span class="tool-icon">{exec?.isRunning ? '⏳' : exec?.isError ? '❌' : '🔧'}</span>
          <span class="tool-name">{tool.name ?? 'tool'}</span>
          {#if tool.arguments && Object.keys(tool.arguments).length > 0}
            <span class="tool-args-summary">{formatArgs(tool.arguments)}</span>
          {/if}
        </div>

        <!-- Tool execution output -->
        {#if exec}
          <details class="tool-output">
            <summary>
              {#if exec.isRunning}
                Running...
              {:else if exec.isError}
                Failed
              {:else}
                Output
              {/if}
            </summary>
            <pre>{exec.output || '(no output)'}</pre>
          </details>
        {/if}
      </div>
    {/each}

    <!-- Text content -->
    {#if textContent()}
      <div class="text">{textContent()}</div>
    {/if}
  </div>
</div>

<style>
  .message {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-width: 85%;
  }

  .message.user {
    align-self: flex-end;
  }

  .message.assistant {
    align-self: flex-start;
  }

  .message-header {
    font-size: 0.75rem;
    color: var(--text-muted);
    padding: 0 0.5rem;
  }

  .message-content {
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
  }

  .message.user .message-content {
    background: var(--primary);
    color: white;
    border-color: var(--primary);
  }

  .text {
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.5;
  }

  /* Thinking blocks */
  .thinking {
    margin-bottom: 0.5rem;
    font-size: 0.8rem;
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 0.375rem;
    overflow: hidden;
  }

  .thinking summary {
    cursor: pointer;
    font-weight: 500;
    padding: 0.375rem 0.625rem;
    background: var(--bg-tertiary);
  }

  .thinking summary:hover {
    background: var(--border);
  }

  .thinking-preview {
    font-weight: 400;
    opacity: 0.7;
  }

  .thinking pre {
    margin: 0;
    padding: 0.5rem 0.625rem;
    font-size: 0.75rem;
    overflow-x: auto;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }

  /* Tool calls */
  .tool-call {
    padding: 0.5rem 0.625rem;
    background: var(--bg-tertiary);
    border-radius: 0.375rem;
    font-size: 0.8rem;
    border: 1px solid var(--border);
  }

  .tool-call.running {
    border-color: var(--primary);
    animation: pulse-border 1.5s infinite;
  }

  .tool-call.error {
    border-color: var(--error);
  }

  @keyframes pulse-border {
    0%, 100% { border-color: var(--primary); }
    50% { border-color: transparent; }
  }

  .tool-call-header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .tool-icon {
    font-size: 0.75rem;
  }

  .tool-name {
    font-weight: 600;
    font-family: monospace;
    color: var(--primary);
  }

  .tool-args-summary {
    color: var(--text-muted);
    font-size: 0.75rem;
    font-family: monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tool-output {
    margin-top: 0.375rem;
    font-size: 0.75rem;
  }

  .tool-output summary {
    cursor: pointer;
    color: var(--text-muted);
    font-weight: 500;
    padding: 0.125rem 0;
  }

  .tool-output summary:hover {
    color: var(--text-primary);
  }

  .tool-output pre {
    margin: 0.25rem 0 0 0;
    padding: 0.375rem;
    background: var(--bg-primary);
    border-radius: 0.25rem;
    font-size: 0.7rem;
    overflow-x: auto;
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }
</style>
