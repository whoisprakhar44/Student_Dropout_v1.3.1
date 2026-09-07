import { useContext } from 'react';
import { ChatbotContext } from '../ChatbotProvider';

/**
 * Custom hook to easily consume the Chatbot context.
 * Throws a clear error if used outside of <ChatbotProvider>.
 */
export const useChatbot = () => {
  const context = useContext(ChatbotContext);
  if (!context) {
    throw new Error('useChatbot must be used within a <ChatbotProvider>');
  }
  return context;
};
