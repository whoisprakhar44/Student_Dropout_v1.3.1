import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
  Plus,
  Search,
  Trash2,
  Settings,
  X,
  Check,
  LayoutGrid,
  List,
  Ban
} from 'lucide-react';

import { useChatbot } from '../hooks/useChatbot';
import { SUGGESTION_LAYOUTS } from '../constants/chatbotConstants';

export const ChatHistorySidebar = () => {
  const {
    sessions,
    activeSessionId,
    loadSession,
    createNewSession,
    deleteSession,
    clearAllSessions,
    suggestionLayout,
    setSuggestionLayout,
    suggestionsDisabled,
    setSuggestionsDisabled
  } = useChatbot();

  const [searchQuery, setSearchQuery] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  
  const settingsModalRef = useRef(null);

  const appVersion =
    import.meta.env?.VITE_CHATBOT_VERSION ||
    import.meta.env?.VITE_APP_VERSION ||
    'v1.0.0';

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;

    const query = searchQuery.toLowerCase();

    return sessions.filter(
      (session) =>
        session.title?.toLowerCase().includes(query) ||
        (session.messages &&
          session.messages.some(
            (m) =>
              m.content &&
              m.content.toLowerCase().includes(query)
          ))
    );
  }, [sessions, searchQuery]);

  const formatDate = (isoString) => {
    if (!isoString) return '';

    try {
      const date = new Date(isoString);

      return date.toLocaleDateString([], {
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return '';
    }
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && showSettings) {
        setShowSettings(false);
      }
    };

    const handleClickOutside = (e) => {
      if (
        settingsModalRef.current &&
        !settingsModalRef.current.contains(e.target)
      ) {
        setShowSettings(false);
      }
    };

    if (showSettings) {
      document.addEventListener(
        'keydown',
        handleKeyDown
      );
      document.addEventListener(
        'mousedown',
        handleClickOutside
      );
    }

    return () => {
      document.removeEventListener(
        'keydown',
        handleKeyDown
      );
      document.removeEventListener(
        'mousedown',
        handleClickOutside
      );
    };
  }, [showSettings]);



  return (
    <aside
      className="cb-sidebar"
      aria-label="Chat history navigation"
    >
      <div className="cb-sidebar-header">
        <button
          className="cb-new-chat-btn"
          onClick={createNewSession}
        >
          <Plus size={16} />
          New Chat
        </button>

        <div className="cb-search-input-wrap">
          <Search
            size={14}
            className="cb-search-icon"
          />

          <input
            type="text"
            className="cb-search-input"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) =>
              setSearchQuery(e.target.value)
            }
            aria-label="Search conversation history"
          />
        </div>
      </div>

      <div className="cb-sidebar-list">
        {filteredSessions.length === 0 ? (
          <div
            style={{
              padding: '24px 16px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '13px'
            }}
          >
            No sessions found
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive =
              session.id === activeSessionId;

            const messageCount =
              session.messages?.length || 0;

            return (
              <div
                key={session.id}
                className={`cb-session-item ${
                  isActive ? 'active' : ''
                }`}
                onClick={() =>
                  loadSession(session.id)
                }
                role="button"
                tabIndex={0}
                onKeyDown={(e) =>
                  e.key === 'Enter' &&
                  loadSession(session.id)
                }
                aria-label={`Select session: ${session.title}`}
              >
                <div className="cb-session-details">
                  <span className="cb-session-title">
                    {session.title ||
                      'Untitled Session'}
                  </span>

                  <div className="cb-session-meta">
                    <span>
                      {formatDate(
                        session.updatedAt ||
                          session.createdAt
                      )}
                    </span>

                    {messageCount > 0 && (
                      <>
                        <span>•</span>
                        <span>
                          {messageCount} msg
                          {messageCount !== 1
                            ? 's'
                            : ''}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  className="cb-delete-session-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(session.id);
                  }}
                  title="Delete Session"
                  aria-label={`Delete conversation ${session.title}`}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            );
          })
        )}
      </div>

      <div className="cb-sidebar-footer">
        <div
          className="cb-version-tag"
          title={`Chatbot Version: ${appVersion}`}
        >
          <span className="cb-version-dot" />
          <span>Version {appVersion}</span>
        </div>

        <button
          type="button"
          className="cb-settings-btn"
          onClick={() =>
            setShowSettings((prev) => !prev)
          }
          aria-label="Chatbot Settings"
          title="Chatbot Settings"
        >
          <Settings size={17} />
        </button>

        {showSettings && (
          <div
            className="cb-settings-modal"
            ref={settingsModalRef}
            role="dialog"
            aria-label="Chatbot Settings"
          >
            <div className="cb-settings-modal-header">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <Settings
                  size={15}
                  color="var(--primary-color)"
                />
                <span className="cb-settings-modal-title">
                  Settings
                </span>
              </div>

              <button
                type="button"
                className="cb-settings-close-btn"
                onClick={() =>
                  setShowSettings(false)
                }
                aria-label="Close Settings"
              >
                <X size={15} />
              </button>
            </div>

            <div className="cb-settings-modal-body">
              <div className="cb-settings-group">
                <label className="cb-settings-label">
                  Suggestions Layout
                </label>

                <span className="cb-settings-subtext">
                  Choose how prompt
                  recommendations are displayed:
                </span>

                <div className="cb-settings-options-grid">
                  <button
                    type="button"
                    className={`cb-settings-option-btn ${
                      !suggestionsDisabled &&
                      suggestionLayout ===
                        SUGGESTION_LAYOUTS.HORIZONTAL
                        ? 'active'
                        : ''
                    }`}
                    onClick={() => {
                              setSuggestionLayout(
                                SUGGESTION_LAYOUTS.HORIZONTAL
                              );

                              setSuggestionsDisabled(false);
                            }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <LayoutGrid size={15} />
                      <span>Horizontal</span>
                    </div>

                    {!suggestionsDisabled &&
                      suggestionLayout ===
                        SUGGESTION_LAYOUTS.HORIZONTAL && (
                        <Check size={14} />
                      )}
                  </button>

                  <button
                    type="button"
                    className={`cb-settings-option-btn ${
                      !suggestionsDisabled &&
                      suggestionLayout ===
                        SUGGESTION_LAYOUTS.VERTICAL
                        ? 'active'
                        : ''
                    }`}
                    onClick={() => {
                              setSuggestionLayout(
                                SUGGESTION_LAYOUTS.VERTICAL
                              );

                              setSuggestionsDisabled(false);
                            }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <List size={15} />
                      <span>Vertical</span>
                    </div>

                    {!suggestionsDisabled &&
                      suggestionLayout ===
                        SUGGESTION_LAYOUTS.VERTICAL && (
                        <Check size={14} />
                      )}
                  </button>

                  <button
                    type="button"
                    className={`cb-settings-option-btn ${
                      suggestionsDisabled
                        ? 'active'
                        : ''
                    }`}
                    onClick={() => {setSuggestionsDisabled(true);}}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <Ban size={15} />
                      <span>
                        Disable Suggestions
                      </span>
                    </div>

                    {suggestionsDisabled && (
                      <Check size={14} />
                    )}
                  </button>
                </div>
              </div>

              <div className="cb-settings-group">
                <label className="cb-settings-label">
                  Conversation Data
                </label>

                <button
                  type="button"
                  className="cb-clear-all-btn"
                  onClick={() => {
                    if (
                      window.confirm(
                        'Are you sure you want to clear all chat conversations?'
                      )
                    ) {
                      clearAllSessions();
                      setShowSettings(false);
                    }
                  }}
                >
                  <Trash2 size={14} />
                  <span>
                    Clear All Conversations
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};

export default ChatHistorySidebar;