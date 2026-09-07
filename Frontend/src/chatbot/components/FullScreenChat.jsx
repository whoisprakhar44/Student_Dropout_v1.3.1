import React, { useRef, useEffect } from 'react';
import { useChatbot } from '../hooks/useChatbot';
import { VIEW_MODES } from '../constants/chatbotConstants';
import ChatHeader from './ChatHeader';
import ChatHistorySidebar from './ChatHistorySidebar';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import LoadingAnimation from './LoadingAnimation';

export const FullScreenChat = ({ suggestionLayout }) => {
  const { messages, sendMessage, isLoading, openChat, suggestionLayout: contextLayout, suggestionsDisabled, setSuggestionsDisabled } = useChatbot();
  const messagesEndRef = useRef(null);

  // Read fullscreen gap percentage from env variable (default: 3%)
  const gapPercent = Number(import.meta.env?.VITE_FULLSCREEN_GAP_PERCENT ?? 3);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Apply gap padding ONLY to cb-fullscreen-backdrop inside cb-root (does not affect parent application root)
  const backdropStyle = React.useMemo(() => {
    if (!gapPercent || gapPercent <= 0) return {};
    return {
      padding: `${gapPercent}%`,
      boxSizing: 'border-box'
    };
  }, [gapPercent]);

  return (
    <div
      className="cb-fullscreen-backdrop"
      style={backdropStyle}
      onClick={() => openChat(VIEW_MODES.MINI)}
      aria-label="Close fullscreen view backdrop"
    >
      <div
        className="cb-fullscreen-overlay"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Full Screen Chatbot"
      >
        <ChatHeader isFullscreen={true} />

        <div className="cb-fullscreen-body">
          <ChatHistorySidebar />

          <main className="cb-fullscreen-main">
            <div className="cb-fullscreen-messages">
              {messages.map(msg => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              {isLoading && <LoadingAnimation />}
              <div ref={messagesEndRef} />
            </div>

            <div className="cb-fullscreen-input-wrap">
              <ChatInput
                onSend={sendMessage}
                disabled={isLoading}
                suggestionLayout={suggestionLayout || contextLayout}
                suggestionsDisabled={suggestionsDisabled}
              />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default FullScreenChat;