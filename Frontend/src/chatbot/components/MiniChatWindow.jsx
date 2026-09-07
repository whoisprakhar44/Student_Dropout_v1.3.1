import React, { useRef, useEffect } from 'react';
import { useChatbot } from '../hooks/useChatbot';
import ChatHeader from './ChatHeader';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import LoadingAnimation from './LoadingAnimation';

export const MiniChatWindow = ({ suggestionLayout }) => {
  const { messages, sendMessage, isLoading, suggestionLayout: contextLayout , suggestionsDisabled, setSuggestionsDisabled } = useChatbot();
  const messagesEndRef = useRef(null);

  // Auto-scroll to latest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  return (
    <div className="cb-mini-window" role="dialog" aria-label="Mini Chat Window">
      <ChatHeader isFullscreen={false} />

      <div className="cb-mini-body">
        {messages.map(msg => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        {isLoading && <LoadingAnimation />}
        <div ref={messagesEndRef} />
      </div>

      <div className="cb-mini-input-wrap">
        <ChatInput
          onSend={sendMessage}
          disabled={isLoading}
          suggestionLayout={suggestionLayout || contextLayout}
          suggestionsDisabled={suggestionsDisabled}
        />
      </div>
    </div>
  );
};

export default MiniChatWindow;