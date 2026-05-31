/** OpenNotebook — Chat input with send, keyboard shortcuts, and quick prompts. */

import { useState, useRef, useCallback, type KeyboardEvent } from 'react';
import { clsx } from 'clsx';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isStreaming: boolean;
  disabled?: boolean;
  quickPrompts?: string[];
  placeholder?: string;
}

export function ChatInput({
  onSend,
  isStreaming,
  disabled = false,
  quickPrompts = [],
  placeholder = 'Ask a question about your sources...',
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed);
    setValue('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, isStreaming, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  return (
    <div className="border-t border-surface-700/40 bg-surface-900/80 backdrop-blur-sm p-4">
      {/* Quick prompts */}
      {quickPrompts.length > 0 && !value && (
        <div className="mb-3 flex flex-wrap gap-2">
          {quickPrompts.map((prompt, i) => (
            <button
              key={i}
              onClick={() => {
                setValue(prompt);
                textareaRef.current?.focus();
              }}
              className="rounded-xl border border-surface-700/40 bg-surface-800/60 px-3 py-1.5 text-xs text-surface-300 transition-all hover:border-primary-500/30 hover:bg-surface-800 hover:text-surface-100"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="flex items-end gap-3">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              handleInput();
            }}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className={clsx(
              'w-full resize-none rounded-xl border bg-surface-800/60 px-4 py-3 text-sm text-surface-100',
              'placeholder:text-surface-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50',
              'border-surface-700/40 transition-all',
              'scrollbar-thin',
              disabled && 'opacity-50 cursor-not-allowed',
            )}
          />
        </div>

        <button
          onClick={handleSend}
          disabled={!value.trim() || isStreaming || disabled}
          className={clsx(
            'flex h-11 w-11 items-center justify-center rounded-xl transition-all',
            value.trim() && !isStreaming && !disabled
              ? 'bg-primary-600 text-white shadow-lg shadow-primary-500/25 hover:bg-primary-500 active:scale-95'
              : 'bg-surface-800 text-surface-500 cursor-not-allowed',
          )}
          title="Send message (Enter)"
        >
          {isStreaming ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Send className="h-5 w-5" />
          )}
        </button>
      </div>

      <p className="mt-2 text-center text-xs text-surface-600">
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
