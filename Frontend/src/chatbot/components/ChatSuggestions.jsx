import React from 'react';
import { Sparkles, ArrowUpRight, X, EyeOff } from 'lucide-react';

/**
 * ChatSuggestions Component
 * 
 * Renders ranked question suggestions above the chat input bar in either:
 * - Horizontal (scrollable pills carousel)
 * - Vertical (stacked list)
 * 
 * Features:
 * - Transparent bubble styling strictly using parent CSS variables
 * - Click bubble: Fills input field and allows editing
 * - Click direct-send icon: Sends query immediately
 * - Dismiss / disable button with hover hint
 */
export const ChatSuggestions = ({
  suggestions = [],
  layout = 'horizontal',
  isScoring = false,
  onSelect,
  onSend,
  onDismiss,
  onToggleDisabled,
}) => {
  if ((!suggestions || suggestions.length === 0) && !isScoring) {
    return null;
  }

  const isVertical = layout === 'vertical';

  return (
    <div
      className={`cb-suggestions-container ${isVertical ? 'vertical' : 'horizontal'}`}
      role="region"
      aria-label="Suggested Prompts"
    >
      <div className="cb-suggestions-header">
        <div className="cb-suggestions-label">
          <Sparkles size={13} className="cb-suggestions-icon" />
          <span>{isScoring ? 'Searching suggestions...' : 'Suggested queries'}</span>
          {isScoring && <span className="cb-suggestions-shimmer-dot" />}
        </div>

        <div className="cb-suggestions-actions">
          {onToggleDisabled && (
            <button
              type="button"
              className="cb-suggestion-ctrl-btn"
              onClick={onToggleDisabled}
              title="Disable suggestion ranking"
              aria-label="Disable suggestions"
            >
              <EyeOff size={13} />
            </button>
          )}

          {onDismiss && (
            <button
              type="button"
              className="cb-suggestion-ctrl-btn"
              onClick={onDismiss}
              title="Dismiss suggestions"
              aria-label="Dismiss suggestions"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      <div className={`cb-suggestions-list ${isVertical ? 'vertical' : 'horizontal'}`}>
        {suggestions.map((item) => (
          <div
            key={item.id}
            className="cb-suggestion-bubble"
            onClick={() => onSelect && onSelect(item.question)}
            role="button"
            tabIndex={0}
            title="Click to edit in input bar"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect && onSelect(item.question);
              }
            }}
          >
            <span className="cb-suggestion-text">{item.question}</span>

            {/* Direct Send Quick Action */}
            {onSend && (
              <button
                type="button"
                className="cb-suggestion-send-action"
                onClick={(e) => {
                  e.stopPropagation();
                  onSend(item.question);
                }}
                title="Send directly"
                aria-label={`Send: ${item.question}`}
              >
                <ArrowUpRight size={13} />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChatSuggestions;