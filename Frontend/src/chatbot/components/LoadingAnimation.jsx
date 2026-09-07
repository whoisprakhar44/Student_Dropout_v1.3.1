import React from 'react';
import { XCircle } from 'lucide-react';
import { useChatbot } from '../hooks/useChatbot';

export const LoadingAnimation = () => {
  const { cancelCurrentRequest } = useChatbot();

  return (
    <div className="cb-message-row assistant">
      <div className="cb-loading-container" aria-label="Assistant is generating response">
        <div className="cb-dot" />
        <div className="cb-dot" />
        <div className="cb-dot" />

        {cancelCurrentRequest && (
          <button
            type="button"
            className="cb-cancel-request-btn"
            onClick={cancelCurrentRequest}
            title="Cancel this request"
            aria-label="Cancel request"
          >
            <XCircle size={14} />
            <span>Cancel</span>
          </button>
        )}
      </div>
    </div>
  );
};

export default LoadingAnimation;
