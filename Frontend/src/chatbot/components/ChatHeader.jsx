import React from 'react';
import { Maximize2, Minimize2, X, RotateCcw } from 'lucide-react';
import { useChatbot } from '../hooks/useChatbot';
import { DEFAULT_BOT_INFO } from '../constants/chatbotConstants';

export const ChatHeader = ({ isFullscreen = false, onToggleSidebar = null }) => {
  const { closeChat, toggleFullscreen, clearChat } = useChatbot();

  return (
    <div className="cb-header">
      <div className="cb-header-info">
        <div className="cb-avatar-wrapper">
          <svg xmlns="http://www.w3.org/2000/svg" width="25.204" height="24.475" viewBox="0 0 25.204 24.475">
            <path id="chatbot-icon_1_" data-name="chatbot-icon (1)" d="M11.79,5.988V4.825a2.955,2.955,0,0,1-.41-.191,2.5,2.5,0,0,1-1.036-3.1,2.541,2.541,0,0,1,.541-.81,2.5,2.5,0,0,1,.8-.539A2.461,2.461,0,0,1,12.645,0,2.486,2.486,0,0,1,14.4,4.247l-.012.012a2.613,2.613,0,0,1-.484.375,2.309,2.309,0,0,1-.41.191V5.988h5.841A3.173,3.173,0,0,1,22.5,9.153v.47h1.083a1.626,1.626,0,0,1,1.62,1.622v3.767a1.626,1.626,0,0,1-1.62,1.622H22.508v.425a3.175,3.175,0,0,1-3.168,3.164H11.327l-4.8,4.124a.529.529,0,0,1-.749-.059.539.539,0,0,1-.129-.379L5.9,20.217H5.859A3.168,3.168,0,0,1,2.7,17.058v-.425H1.622A1.626,1.626,0,0,1,0,15.012V11.244A1.626,1.626,0,0,1,1.62,9.622H2.7V9.151a3.168,3.168,0,0,1,3.16-3.162ZM16.968,9.7a1.92,1.92,0,1,1-1.92,1.92,1.92,1.92,0,0,1,1.92-1.92Zm-8.732,0a1.92,1.92,0,1,1-1.92,1.92A1.92,1.92,0,0,1,8.236,9.7Zm1.308,6.431a.467.467,0,0,1-.078-.078.447.447,0,0,1-.107-.279.453.453,0,0,1,.094-.285.492.492,0,0,1,.08-.08.66.66,0,0,1,.8-.016,4.586,4.586,0,0,0,1.155.664,3.048,3.048,0,0,0,1.122.205,3.318,3.318,0,0,0,1.134-.226,5.207,5.207,0,0,0,1.179-.66.664.664,0,0,1,.8.037.615.615,0,0,1,.076.084.455.455,0,0,1,.086.287.478.478,0,0,1-.119.277.47.47,0,0,1-.088.078,6.273,6.273,0,0,1-1.5.82,4.569,4.569,0,0,1-1.544.293,4.352,4.352,0,0,1-1.55-.263,5.7,5.7,0,0,1-1.52-.853h0Zm9.793-9.081H5.859a2.1,2.1,0,0,0-2.1,2.1v7.906a2.1,2.1,0,0,0,2.1,2.1h.65A.535.535,0,0,1,7,19.725L6.8,22.715l3.958-3.406a.525.525,0,0,1,.375-.154h8.2a2.1,2.1,0,0,0,2.1-2.1V9.151a2.1,2.1,0,0,0-2.094-2.1Z" transform="translate(0 0)" fill="#fff"/>
          </svg>
          <span className="cb-status-dot" title="Bot Status: Online" />
        </div>
        <div className="cb-bot-details">
          <span className="cb-bot-name">{DEFAULT_BOT_INFO.name}</span>
          <span className="cb-bot-status">
            {DEFAULT_BOT_INFO.status}
          </span>
        </div>
      </div>

      <div className="cb-header-actions">
        <button
          className="cb-icon-btn"
          onClick={clearChat}
          aria-label="Clear current chat messages"
          title="Clear Conversation"
        >
          <RotateCcw size={16} />
        </button>

        <button
          className="cb-icon-btn"
          onClick={toggleFullscreen}
          aria-label={isFullscreen ? 'Minimize chat window' : 'Expand full screen chat'}
          title={isFullscreen ? 'Exit Full Screen' : 'Full Screen View'}
        >
          {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>

        <button
          className="cb-icon-btn"
          onClick={closeChat}
          aria-label="Close chatbot panel"
          title="Close"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
};

export default ChatHeader;
