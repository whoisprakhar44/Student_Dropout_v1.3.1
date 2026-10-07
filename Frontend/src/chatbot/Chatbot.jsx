import React from 'react';
import { useChatbot } from './hooks/useChatbot';
import { VIEW_MODES } from './constants/chatbotConstants';
import FloatingChatButton from './components/FloatingChatButton';
import MiniChatWindow from './components/MiniChatWindow';
import FullScreenChat from './components/FullScreenChat';
import { ShieldAlert, Lock } from 'lucide-react';
import './styles/chatbot.css';

export const Chatbot = () => {
  const {
    viewMode,
    sduiPrivileges,
    securityToast,
    isDevToolsOpen,
    canAccessChatbot,
    isChatDisabledBySecurity
  } = useChatbot();

  const isCopyProtected = sduiPrivileges?.copyProtection ?? true;
  const isDevToolsProtected = sduiPrivileges?.devToolsProtection ?? true;

  // If user has NO chatbot privilege, do NOT even render chat windows or respond
  const canShowChat = canAccessChatbot && !isChatDisabledBySecurity;

  return (
    <div className={`cb-root ${isCopyProtected ? 'cb-copy-protected' : ''}`}>
      {/* Floating Action Button (handles its own privilege check to hide if no privilege) */}
      <FloatingChatButton />

      {/* Render Mini Chat Window only if user has privilege and not disabled by security */}
      {canShowChat && viewMode === VIEW_MODES.MINI && <MiniChatWindow />}

      {/* Render Full Screen Overlay Mode only if user has privilege and not disabled by security */}
      {canShowChat && viewMode === VIEW_MODES.FULLSCREEN && <FullScreenChat />}

      {/* Security Toast Notification */}
      {securityToast && (
        <div className="cb-security-toast" role="alert" aria-live="assertive">
          <Lock size={14} className="cb-security-toast-icon" />
          <span>{securityToast}</span>
        </div>
      )}

      {/* DevTools Open Warning Watermark */}
      {(isDevToolsOpen || isChatDisabledBySecurity) && isDevToolsProtected && viewMode !== VIEW_MODES.CLOSED && (
        <div className="cb-devtools-warning" role="status">
          <ShieldAlert size={14} />
          <span>Security Notice: DevTools inspection active. Chat option disabled from UI.</span>
        </div>
      )}
    </div>
  );
};

export default Chatbot;
