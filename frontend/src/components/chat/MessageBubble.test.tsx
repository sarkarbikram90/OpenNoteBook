import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageBubble } from './MessageBubble';
import type { Message } from '@/lib/types';

const assistantMessage: Message = {
  id: 'm1',
  session_id: 's1',
  role: 'assistant',
  content: 'Grounded answer with no citations.',
  citations: [],
  retrieval_meta: {},
  created_at: '2026-01-01T00:00:00Z',
};

describe('MessageBubble feedback', () => {
  it('invokes onFeedback with "up" when the thumbs-up button is clicked', () => {
    const onFeedback = vi.fn();
    render(<MessageBubble message={assistantMessage} onFeedback={onFeedback} />);

    fireEvent.click(screen.getByTitle('Good answer'));

    expect(onFeedback).toHaveBeenCalledWith('up');
  });

  it('invokes onFeedback with "down" when the thumbs-down button is clicked', () => {
    const onFeedback = vi.fn();
    render(<MessageBubble message={assistantMessage} onFeedback={onFeedback} />);

    fireEvent.click(screen.getByTitle('Poor answer'));

    expect(onFeedback).toHaveBeenCalledWith('down');
  });

  it('does not render feedback buttons for user messages', () => {
    const onFeedback = vi.fn();
    render(
      <MessageBubble
        message={{ ...assistantMessage, role: 'user' }}
        onFeedback={onFeedback}
      />,
    );

    expect(screen.queryByTitle('Good answer')).toBeNull();
  });

  it('does not render feedback buttons when no handler is provided', () => {
    render(<MessageBubble message={assistantMessage} />);

    expect(screen.queryByTitle('Good answer')).toBeNull();
  });
});
