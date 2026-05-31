/** OpenNotebook — Chat message bubble for user and assistant. */

import { clsx } from 'clsx';
import { Copy, Check, RotateCcw, User, Sparkles } from 'lucide-react';
import { useState, useCallback } from 'react';
import { StreamingText } from '@/components/chat/StreamingText';
import { CitationList } from '@/components/chat/CitationChip';
import type { Message, Citation } from '@/lib/types';

interface MessageBubbleProps {
  message?: Message;
  /** For streaming messages — raw content text. */
  streamContent?: string;
  /** For streaming messages — citations collected so far. */
  streamCitations?: Citation[];
  /** Whether this message is currently streaming. */
  isStreaming?: boolean;
  /** Whether this is the last assistant message (shows regenerate). */
  isLast?: boolean;
  /** Callback to regenerate the answer. */
  onRegenerate?: () => void;
}

export function MessageBubble({
  message,
  streamContent,
  streamCitations,
  isStreaming = false,
  isLast = false,
  onRegenerate,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);

  const role = message?.role ?? 'assistant';
  const content = streamContent ?? message?.content ?? '';
  const citations = streamCitations ?? (message?.citations as Citation[]) ?? [];

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  const isUser = role === 'user';

  return (
    <div
      className={clsx(
        'group flex gap-3 px-4 py-4 animate-fade-in',
        isUser ? 'justify-end' : 'justify-start',
      )}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="shrink-0 mt-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-md shadow-primary-500/20">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
        </div>
      )}

      {/* Message content */}
      <div
        className={clsx(
          'max-w-[75%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-primary-600 text-white rounded-tr-md'
            : 'bg-surface-800/80 border border-surface-700/40 text-surface-100 rounded-tl-md',
        )}
      >
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{content}</p>
        ) : (
          <>
            <StreamingText content={content} isStreaming={isStreaming} />
            <CitationList citations={citations} />
          </>
        )}

        {/* Action bar — visible on hover for completed messages */}
        {!isStreaming && content && (
          <div
            className={clsx(
              'mt-2 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100',
              isUser ? 'justify-end' : 'justify-start',
            )}
          >
            <button
              onClick={handleCopy}
              className="rounded-md p-1 text-surface-400 transition-colors hover:text-surface-200 hover:bg-surface-700/50"
              title="Copy to clipboard"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-emerald-400" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
            {!isUser && isLast && onRegenerate && (
              <button
                onClick={onRegenerate}
                className="rounded-md p-1 text-surface-400 transition-colors hover:text-surface-200 hover:bg-surface-700/50"
                title="Regenerate answer"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="shrink-0 mt-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-surface-700 border border-surface-600/50">
            <User className="h-4 w-4 text-surface-300" />
          </div>
        </div>
      )}
    </div>
  );
}
