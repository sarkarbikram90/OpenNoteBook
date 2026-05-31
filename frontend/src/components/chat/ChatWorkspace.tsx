/** OpenNotebook — Chat workspace: message list, input, streaming, session management. */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { BookOpen, SlidersHorizontal } from 'lucide-react';
import { useSessions, useMessages, useDeleteSession, useExportSession, chatKeys } from '@/hooks/useChat';
import { useSources } from '@/hooks/useSources';
import { useStream } from '@/hooks/useStream';
import { MessageBubble } from '@/components/chat/MessageBubble';
import { ChatInput } from '@/components/chat/ChatInput';
import { SessionSidebar } from '@/components/chat/SessionSidebar';
import { Spinner } from '@/components/ui/Spinner';
import type { Message } from '@/lib/types';

interface ChatWorkspaceProps {
  notebookId: string;
}

export function ChatWorkspace({ notebookId }: ChatWorkspaceProps) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string[]>([]);
  const [showSourceFilter, setShowSourceFilter] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  // Queries
  const { data: sessions = [], isLoading: sessionsLoading } = useSessions(notebookId);
  const { data: messages = [], isLoading: messagesLoading } = useMessages(activeSessionId);
  const { data: sources = [] } = useSources(notebookId);
  const readySources = sources.filter((s) => s.status === 'READY');

  // Stream
  const stream = useStream();

  // Mutations
  const deleteMutation = useDeleteSession(notebookId);
  const exportMutation = useExportSession();

  // Auto-select first session
  useEffect(() => {
    if (!activeSessionId && sessions.length > 0) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessions, activeSessionId]);

  // Auto-scroll on new content
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, stream.content]);

  // On stream done, invalidate messages and sessions to refresh
  useEffect(() => {
    if (!stream.isStreaming && stream.messageId) {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions(notebookId) });
      if (activeSessionId) {
        queryClient.invalidateQueries({ queryKey: chatKeys.messages(activeSessionId) });
      }
    }
  }, [stream.isStreaming, stream.messageId, notebookId, activeSessionId, queryClient]);

  const handleSend = useCallback(
    (question: string) => {
      stream.send(notebookId, question, {
        sessionId: activeSessionId ?? undefined,
        sourceFilter: sourceFilter.length > 0 ? sourceFilter : undefined,
      });
    },
    [notebookId, activeSessionId, sourceFilter, stream],
  );

  const handleRegenerate = useCallback(() => {
    // Find the last user message and re-send it
    const lastUserMsg = [...messages].reverse().find((m: Message) => m.role === 'user');
    if (lastUserMsg) {
      handleSend(lastUserMsg.content);
    }
  }, [messages, handleSend]);

  const handleNewSession = useCallback(() => {
    setActiveSessionId(null);
    stream.reset();
  }, [stream]);

  return (
    <div className="flex h-full">
      {/* Session sidebar */}
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={(id) => {
          setActiveSessionId(id);
          stream.reset();
        }}
        onNewSession={handleNewSession}
        onDeleteSession={(id) => {
          deleteMutation.mutate(id);
          if (activeSessionId === id) {
            setActiveSessionId(null);
          }
        }}
        onExportSession={(id) => {
          exportMutation.mutate({ sessionId: id, format: 'markdown' });
        }}
        isLoading={sessionsLoading}
      />

      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {/* Chat header */}
        <div className="flex items-center justify-between border-b border-surface-700/30 px-6 py-3">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary-400" />
            <h2 className="text-sm font-medium text-surface-200">
              {activeSessionId
                ? sessions.find((s) => s.id === activeSessionId)?.title ?? 'Chat'
                : 'New Chat'}
            </h2>
          </div>

          {/* Source filter toggle */}
          {readySources.length > 0 && (
            <button
              onClick={() => setShowSourceFilter(!showSourceFilter)}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-surface-400 transition-colors hover:bg-surface-800 hover:text-surface-200 border border-surface-700/30"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              {sourceFilter.length > 0
                ? `${sourceFilter.length} source${sourceFilter.length > 1 ? 's' : ''} selected`
                : 'All sources'}
            </button>
          )}
        </div>

        {/* Source filter panel */}
        {showSourceFilter && (
          <div className="border-b border-surface-700/30 px-6 py-3 bg-surface-800/30 animate-slide-down">
            <p className="text-xs text-surface-500 mb-2">Query specific sources:</p>
            <div className="flex flex-wrap gap-2">
              {readySources.map((source) => {
                const isSelected = sourceFilter.includes(source.id);
                return (
                  <button
                    key={source.id}
                    onClick={() =>
                      setSourceFilter((prev) =>
                        isSelected
                          ? prev.filter((id) => id !== source.id)
                          : [...prev, source.id],
                      )
                    }
                    className={`rounded-lg px-3 py-1.5 text-xs transition-all border ${
                      isSelected
                        ? 'bg-primary-600/20 border-primary-500/40 text-primary-300'
                        : 'bg-surface-800/60 border-surface-700/30 text-surface-400 hover:border-surface-600'
                    }`}
                  >
                    {source.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messagesLoading ? (
            <div className="flex items-center justify-center py-20">
              <Spinner size="lg" />
            </div>
          ) : messages.length === 0 && !stream.content ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-lg shadow-primary-500/20 mb-6">
                <BookOpen className="h-8 w-8 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-surface-200 mb-2">
                Ask anything about your sources
              </h3>
              <p className="text-sm text-surface-500 max-w-md">
                Your answers will be grounded in the documents you've uploaded.
                Every claim includes inline citations.
              </p>
            </div>
          ) : (
            <div className="py-4">
              {messages.map((msg: Message, i: number) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isLast={
                    i === messages.length - 1 &&
                    msg.role === 'assistant' &&
                    !stream.isStreaming
                  }
                  onRegenerate={handleRegenerate}
                />
              ))}

              {/* Active streaming message */}
              {stream.content && (
                <MessageBubble
                  streamContent={stream.content}
                  streamCitations={stream.citations}
                  isStreaming={stream.isStreaming}
                  isLast={!stream.isStreaming}
                  onRegenerate={handleRegenerate}
                />
              )}

              {/* Error */}
              {stream.error && (
                <div className="mx-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
                  {stream.error}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          isStreaming={stream.isStreaming}
          disabled={readySources.length === 0}
          placeholder={
            readySources.length === 0
              ? 'Upload sources first to start chatting...'
              : 'Ask a question about your sources...'
          }
        />
      </div>
    </div>
  );
}
