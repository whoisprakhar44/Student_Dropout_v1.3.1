import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Plus,
  Search,
  Trash2,
  Settings,
  Info,
  Volume2,
  VolumeX,
  X,
  Check,
  LayoutGrid,
  List,
  Ban,
  Loader2,
  Sparkles,
  Database,
  Layers,
  TableProperties
} from 'lucide-react';

import { useChatbot } from '../hooks/useChatbot';
import { SUGGESTION_LAYOUTS, CHAT_LAYERS } from '../constants/chatbotConstants';
import { speechService } from '../services/speechService';

export const ChatHistorySidebar = () => {
  const {
    sessions,
    activeSessionId,
    activeLayer,
    setActiveLayer,
    isSchemaEnabled,
    currentLayerSessions,
    loadSession,
    createNewSession,
    deleteSession,
    clearAllSessions,
    suggestionLayout,
    setSuggestionLayout,
    suggestionsDisabled,
    setSuggestionsDisabled,
    loadingSessions,
    activeRightView,
    openAboutView,
    closeAboutView
  } = useChatbot();

  const [searchQuery, setSearchQuery] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [speechState, setSpeechState] = useState(() => speechService.getState());

  useEffect(() => {
    const unsub = speechService.subscribe(setSpeechState);
    return () => unsub();
  }, []);
  
  const settingsModalRef = useRef(null);

  const appVersion =
    import.meta.env?.VITE_CHATBOT_VERSION ||
    import.meta.env?.VITE_APP_VERSION ||
    'v1.0.0';

  // Filter sessions matching active layer and search query
  const targetSessions = useMemo(() => {
    if (Array.isArray(currentLayerSessions)) {
      return currentLayerSessions;
    }
    return sessions.filter((s) => (s.layer || CHAT_LAYERS.CURATED) === activeLayer);
  }, [currentLayerSessions, sessions, activeLayer]);

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return targetSessions;

    const query = searchQuery.toLowerCase();

    return targetSessions.filter(
      (session) =>
        session.title?.toLowerCase().includes(query) ||
        (session.messages &&
          session.messages.some(
            (m) =>
              m.content &&
              m.content.toLowerCase().includes(query)
          ))
    );
  }, [targetSessions, searchQuery]);

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

  const isSchemaMode = activeLayer === CHAT_LAYERS.SCHEMA;

  return (
    <aside
      className="cb-sidebar"
      aria-label="Chat history navigation"
    >
      <div className="cb-sidebar-header">
        {/* Layer Mode Switcher (Curated vs Schema) - Controlled via SDUI / backend visibility */}
        {isSchemaEnabled && (
          <div className="cb-layer-switcher-wrap" aria-label="Conversation Type Switcher">
            <div className="cb-layer-tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={activeLayer === CHAT_LAYERS.CURATED}
                className={`cb-layer-tab ${activeLayer === CHAT_LAYERS.CURATED ? 'active' : ''}`}
                onClick={() => setActiveLayer(CHAT_LAYERS.CURATED)}
                title="Curated Mode: Verified questions, domain analytics & citizen schemes"
              >
                <Sparkles size={13} className="cb-layer-tab-icon" />
                <span>Curated</span>
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={activeLayer === CHAT_LAYERS.SCHEMA}
                className={`cb-layer-tab ${activeLayer === CHAT_LAYERS.SCHEMA ? 'active' : ''}`}
                onClick={() => setActiveLayer(CHAT_LAYERS.SCHEMA)}
                title="Schema Mode: Direct relational schema, table structures & metadata query"
              >
                <Database size={13} className="cb-layer-tab-icon" />
                <span>Schema</span>
                <span className="cb-layer-tab-badge">Beta</span>
              </button>
            </div>
          </div>
        )}

        <button
          className={`cb-new-chat-btn ${isSchemaMode ? 'schema-mode' : ''}`}
          onClick={() => createNewSession(activeLayer)}
          title={isSchemaMode ? 'Start new Schema Query session' : 'Start new Curated Conversation'}
        >
          <Plus size={16} />
          {isSchemaMode ? 'New Schema Chat' : 'New Chat'}
        </button>

        <div className="cb-search-input-wrap">
          <Search
            size={14}
            className="cb-search-icon"
          />

          <input
            type="text"
            className="cb-search-input"
            placeholder={isSchemaMode ? 'Search schema chats...' : 'Search conversations...'}
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
              padding: '32px 16px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '13px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            {isSchemaMode ? (
              <>
                <Database size={24} style={{ opacity: 0.4, color: 'var(--primary-color)' }} />
                <span>No Schema sessions found</span>
                <span style={{ fontSize: '11px', opacity: 0.7 }}>
                  Click "+ New Schema Chat" to query tables & column metadata.
                </span>
              </>
            ) : (
              <>
                <Sparkles size={24} style={{ opacity: 0.4, color: 'var(--primary-color)' }} />
                <span>No sessions found</span>
              </>
            )}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive =
              session.id === activeSessionId;

            const messageCount =
              session.messages?.length || 0;

            const sessionIsSchema = (session.layer || CHAT_LAYERS.CURATED) === CHAT_LAYERS.SCHEMA;

            return (
              <div
                key={session.id}
                className={`cb-session-item ${
                  isActive ? 'active' : ''
                } ${sessionIsSchema ? 'is-schema-session' : ''}`}
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
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="cb-session-title">
                      {session.title ||
                        (sessionIsSchema ? 'Untitled Schema Query' : 'Untitled Session')}
                    </span>
                    {loadingSessions?.[session.id] && (
                      <span className="cb-session-loading-badge" title="Query running in this chat...">
                        <Loader2 size={12} className="cb-icon-spin" />
                      </span>
                    )}
                  </div>

                  <div className="cb-session-meta">
                    {sessionIsSchema && (
                      <span className="cb-session-layer-tag" title="Schema Chat Layer">
                        Schema
                      </span>
                    )}
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
          title={`Chatbot Version: ${appVersion} | Mode: ${activeLayer}`}
        >
          <span className="cb-version-dot" style={{ background: isSchemaMode ? '#8b5cf6' : 'var(--primary-color)' }} />
          <span>Version {appVersion}</span>
        </div>

        <div className="cb-sidebar-footer-actions">
          <button
            type="button"
            className={`cb-info-btn ${activeRightView === 'about' ? 'active' : ''}`}
            onClick={() => {
              setShowSettings(false);
              if (activeRightView === 'about') {
                closeAboutView();
              } else {
                openAboutView();
              }
            }}
            aria-label="About Data Model & Canonical Schema"
            title="About Canonical Data Model & Schema"
          >
            <Info size={17} />
          </button>

          <button
            type="button"
            className={`cb-settings-btn ${showSettings ? 'active' : ''}`}
            onClick={() =>
              setShowSettings((prev) => !prev)
            }
            aria-label="Chatbot Settings"
            title="Chatbot Settings"
          >
            <Settings size={17} />
          </button>
        </div>

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

              {speechState.supported && (
                <div className="cb-settings-group">
                  <label className="cb-settings-label">
                    <Volume2 size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                    Speech & Voice (TTS)
                  </label>

                  {/* Auto-Play Toggle */}
                  <div className="cb-settings-tts-row">
                    <div>
                      <span className="cb-settings-sublabel">Auto-Play Summary</span>
                      <span className="cb-settings-subtext" style={{ display: 'block' }}>
                        Speak agent summary automatically
                      </span>
                    </div>
                    <button
                      type="button"
                      className={`cb-toggle-switch ${speechState.autoPlay ? 'active' : ''}`}
                      onClick={() => speechService.setAutoPlay(!speechState.autoPlay)}
                      aria-label="Toggle Auto Play Summary"
                    >
                      <span className="cb-toggle-knob" />
                    </button>
                  </div>

                  {/* Voice Selector */}
                  {speechState.voices.length > 0 && (
                    <div style={{ marginTop: '6px' }}>
                      <span className="cb-settings-subtext" style={{ display: 'block', marginBottom: '4px' }}>
                        Voice Pack ({speechState.voices.length} available):
                      </span>
                      <select
                        className="cb-voice-select"
                        value={speechState.selectedVoiceURI || ''}
                        onChange={(e) => speechService.setVoice(e.target.value)}
                        aria-label="Select Voice Pack"
                      >
                        {speechState.voices.map((v) => (
                          <option key={v.voiceURI || v.name} value={v.voiceURI || v.name}>
                            {v.name} ({v.lang})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Speech Speed / Rate */}
                  <div style={{ marginTop: '6px' }}>
                    <span className="cb-settings-subtext" style={{ display: 'block', marginBottom: '4px' }}>
                      Speech Speed ({speechState.rate}x):
                    </span>
                    <div className="cb-rate-options-grid">
                      {[0.8, 1.0, 1.25, 1.5].map((rateVal) => (
                        <button
                          key={rateVal}
                          type="button"
                          className={`cb-rate-btn ${speechState.rate === rateVal ? 'active' : ''}`}
                          onClick={() => speechService.setRate(rateVal)}
                        >
                          {rateVal}x
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

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
                        `Are you sure you want to clear ${isSchemaMode ? 'all schema query' : 'all chat'} conversations?`
                      )
                    ) {
                      clearAllSessions(activeLayer);
                      setShowSettings(false);
                    }
                  }}
                >
                  <Trash2 size={14} />
                  <span>
                    Clear {isSchemaMode ? 'Schema Conversations' : 'All Conversations'}
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