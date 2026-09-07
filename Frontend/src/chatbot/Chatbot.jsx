import React from 'react';
import { useChatbot } from './hooks/useChatbot';
import { VIEW_MODES } from './constants/chatbotConstants';
import FloatingChatButton from './components/FloatingChatButton';
import MiniChatWindow from './components/MiniChatWindow';
import FullScreenChat from './components/FullScreenChat';
import './styles/chatbot.css';

export const Chatbot = () => {
  const { viewMode } = useChatbot();

  return (
    <div className="cb-root">
      {/* Floating Action Button always present at bottom-right */}
      <FloatingChatButton />

      {/* Render Mini Chat Window */}
      {viewMode === VIEW_MODES.MINI && <MiniChatWindow />}

      {/* Render Full Screen Overlay Mode */}
      {viewMode === VIEW_MODES.FULLSCREEN && <FullScreenChat />}
    </div>
  );
};

export default Chatbot;
