/** OpenNotebook — Streaming text display with blinking cursor. */

import Markdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';

interface StreamingTextProps {
  content: string;
  isStreaming: boolean;
}

export function StreamingText({ content, isStreaming }: StreamingTextProps) {
  if (!content && isStreaming) {
    return (
      <div className="flex items-center gap-1.5 py-2">
        <span className="h-2 w-2 rounded-full bg-primary-400 animate-pulse" style={{ animationDelay: '0ms' }} />
        <span className="h-2 w-2 rounded-full bg-primary-400 animate-pulse" style={{ animationDelay: '150ms' }} />
        <span className="h-2 w-2 rounded-full bg-primary-400 animate-pulse" style={{ animationDelay: '300ms' }} />
      </div>
    );
  }

  return (
    <div className="prose-chat">
      <Markdown rehypePlugins={[rehypeHighlight]}>
        {content}
      </Markdown>
      {isStreaming && (
        <span className="inline-block h-5 w-0.5 bg-primary-400 ml-0.5 animate-blink align-text-bottom" />
      )}
    </div>
  );
}
