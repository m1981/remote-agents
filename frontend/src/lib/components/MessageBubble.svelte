<!--
  MessageBubble — renders a single message in the conversation.
  Handles user, assistant, and tool result messages.
-->
<script lang="ts">
  import type { Message, ContentBlock } from '$lib/types';

  interface Props {
    message: Message;
  }

  let { message }: Props = $props();

  const isUser = $derived(message.role === 'user');
  const isAssistant = $derived(message.role === 'assistant');

  const textContent = $derived(() => {
    if (typeof message.content === 'string') return message.content;
    if (Array.isArray(message.content)) {
      return message.content
        .filter((b: ContentBlock) => b.type === 'text')
        .map((b: ContentBlock) => b.text ?? '')
        .join('');
    }
    return '';
  });

  const thinkingContent = $derived(() => {
    if (!Array.isArray(message.content)) return null;
    const block = message.content.find((b: ContentBlock) => b.type === 'thinking');
    return block?.thinking ?? null;
  });

  const toolCalls = $derived(() => {
    if (!Array.isArray(message.content)) return [];
    return message.content.filter((b: ContentBlock) => b.type === 'toolCall');
  });
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
    {#if textContent()}
      <div class="text">{textContent()}</div>
    {/if}

    {#if thinkingContent()}
      <details class="thinking">
        <summary>💭 Thinking...</summary>
        <pre>{thinkingContent()}</pre>
      </details>
    {/if}

    {#if toolCalls().length > 0}
      <div class="tool-calls">
        {#each toolCalls() as tool}
          <div class="tool-call">
            <span class="tool-name">🔧 {tool.name ?? 'tool'}</span>
            {#if tool.arguments}
              <pre class="tool-args">{JSON.stringify(tool.arguments, null, 2)}</pre>
            {/if}
          </div>
        {/each}
      </div>
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

  .thinking {
    margin-top: 0.5rem;
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .thinking summary {
    cursor: pointer;
    font-weight: 500;
  }

  .thinking pre {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: var(--bg-tertiary);
    border-radius: 0.25rem;
    font-size: 0.75rem;
    overflow-x: auto;
  }

  .tool-calls {
    margin-top: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .tool-call {
    padding: 0.5rem;
    background: var(--bg-tertiary);
    border-radius: 0.25rem;
    font-size: 0.8rem;
  }

  .tool-name {
    font-weight: 600;
    font-family: monospace;
  }

  .tool-args {
    margin-top: 0.25rem;
    font-size: 0.7rem;
    overflow-x: auto;
  }
</style>
