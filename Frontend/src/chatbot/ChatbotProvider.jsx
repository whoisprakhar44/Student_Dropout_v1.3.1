import React, { createContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { VIEW_MODES, ROLES, INITIAL_WELCOME_MESSAGE, SUGGESTION_LAYOUTS } from './constants/chatbotConstants';
import { chatStorage } from './services/chatStorage';
import { chatbotApi } from './services/chatbotApi';
import { suggestionsService } from './services/suggestionsService';

export const ChatbotContext = createContext(null);

export const ChatbotProvider = ({ children }) => {
  // 1. Initial State Hydration from localStorage
  const [viewMode, setViewMode] = useState(() => chatStorage.getViewMode());
  const [sessions, setSessions] = useState(() => chatStorage.getSessions());
  const [activeSessionId, setActiveSessionId] = useState(() => chatStorage.getActiveSessionId());
  const [unreadCount, setUnreadCount] = useState(() => chatStorage.getUnreadCount());
  const [isLoading, setIsLoading] = useState(false);
  const [suggestionLayout, setSuggestionLayoutState] = useState(() => {
    return chatStorage.getSuggestionLayout() || (import.meta.env?.VITE_SUGGESTION_LAYOUT || SUGGESTION_LAYOUTS.HORIZONTAL).toLowerCase();
  });
  const [suggestionsDisabled, setSuggestionsDisabledState] = useState(
    () => suggestionsService.isSuggestionsDisabled()
  );
  const [inputText, setInputText] = useState('');

  const activeRequestIdRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Helper to construct a new session object
  const createSessionObject = (initialMessages = []) => {
    const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    const now = new Date().toISOString();
    return {
      id: newId,
      title: 'New Conversation',
      createdAt: now,
      updatedAt: now,
      messages: initialMessages.length > 0 ? initialMessages : [{ ...INITIAL_WELCOME_MESSAGE, sessionId: newId }],
    };
  };

  // 2. Fetch Sessions & History from Backend on Mount
  useEffect(() => {
    let isMounted = true;

    const syncWithBackend = async () => {
      try {
        const backendSessions = await chatbotApi.getChatSessions();

        if (!isMounted) return;

        if (Array.isArray(backendSessions) && backendSessions.length > 0) {
          // Merge / replace sessions with backend data
          setSessions(backendSessions);

          const targetId = (activeSessionId && backendSessions.some(s => s.id === activeSessionId))
            ? activeSessionId
            : backendSessions[0].id;

          setActiveSessionId(targetId);

          // Fetch full message thread for the active session
          const sessionDetails = await chatbotApi.getSessionHistory(targetId);
          if (isMounted && sessionDetails && Array.isArray(sessionDetails.messages)) {
            setSessions(prev =>
              prev.map(s => (s.id === targetId ? { ...s, messages: sessionDetails.messages } : s))
            );
          }
        } else if (sessions.length === 0) {
          // No backend sessions and no local sessions: initialize default session
          const defaultSession = createSessionObject();
          setSessions([defaultSession]);
          setActiveSessionId(defaultSession.id);
        }
      } catch (err) {
        console.warn('Backend sync failed, continuing with cached session state:', err);
      }
    };

    syncWithBackend();

    return () => {
      isMounted = false;
    };
  }, []);

  // 3. Persist State Changes to localStorage
  useEffect(() => {
    chatStorage.saveViewMode(viewMode);
  }, [viewMode]);

  // Prevent browser back page navigation while in Fullscreen mode (minimize to MINI view instead)
  useEffect(() => {
    if (viewMode === VIEW_MODES.FULLSCREEN) {
      window.history.pushState({ cbFullscreen: true }, '');

      const handlePopState = () => {
        setViewMode(VIEW_MODES.MINI);
      };

      window.addEventListener('popstate', handlePopState);

      return () => {
        window.removeEventListener('popstate', handlePopState);
        if (window.history.state?.cbFullscreen) {
          window.history.back();
        }
      };
    }
  }, [viewMode]);

  useEffect(() => {
    chatStorage.saveSessions(sessions);
  }, [sessions]);

  useEffect(() => {
    chatStorage.saveActiveSessionId(activeSessionId);
  }, [activeSessionId]);

  useEffect(() => {
    chatStorage.saveUnreadCount(unreadCount);
  }, [unreadCount]);

  useEffect(() => {
    localStorage.setItem(
      'chatbot_suggestions_disabled',
      String(suggestionsDisabled)
    );
  }, [suggestionsDisabled]);

  // Derived active session & messages
  const activeSession = useMemo(() => {
    return sessions.find(s => s.id === activeSessionId) || sessions[0] || null;
  }, [sessions, activeSessionId]);

  const messages = useMemo(() => {
    return activeSession ? (activeSession.messages || []) : [];
  }, [activeSession]);

  // Layout switcher
  const setSuggestionLayout = useCallback((layout) => {
    const valid =
      layout === SUGGESTION_LAYOUTS.VERTICAL
        ? SUGGESTION_LAYOUTS.VERTICAL
        : SUGGESTION_LAYOUTS.HORIZONTAL;

    setSuggestionLayoutState(valid);

    // selecting a layout automatically enables suggestions
    setSuggestionsDisabledState(false);
    suggestionsService.setSuggestionsDisabled(false);

    chatStorage.saveSuggestionLayout(valid);
  }, []);

  const setSuggestionsDisabled = useCallback((disabled) => {
    const val = Boolean(disabled);
    setSuggestionsDisabledState(val);
    suggestionsService.setSuggestionsDisabled(val);
  }, []);

  // UI State Control Handlers
  const openChat = useCallback((mode = VIEW_MODES.MINI) => {
    setViewMode(mode);
    setUnreadCount(0);
  }, []);

  const closeChat = useCallback(() => {
    setViewMode(VIEW_MODES.CLOSED);
  }, []);

  const toggleFullscreen = useCallback(() => {
    setViewMode(prev => (prev === VIEW_MODES.FULLSCREEN ? VIEW_MODES.MINI : VIEW_MODES.FULLSCREEN));
    setUnreadCount(0);
  }, []);

  const markAsRead = useCallback(() => {
    setUnreadCount(0);
  }, []);

  // Session Handlers
  const createNewSession = useCallback(() => {
    const newSession = createSessionObject();
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    return newSession.id;
  }, []);

  const loadSession = useCallback(async (sessionId) => {
    if (!sessionId) return;
    setActiveSessionId(sessionId);

    // If messages are not yet loaded for this session, fetch from backend
    const current = sessions.find(s => s.id === sessionId);
    if (!current || !current.messages || current.messages.length === 0) {
      try {
        const sessionDetails = await chatbotApi.getSessionHistory(sessionId);
        if (sessionDetails && Array.isArray(sessionDetails.messages)) {
          setSessions(prev =>
            prev.map(s => (s.id === sessionId ? { ...s, messages: sessionDetails.messages } : s))
          );
        }
      } catch (err) {
        console.warn('Failed to load session messages from backend:', err);
      }
    }
  }, [sessions]);

  const deleteSession = useCallback(async (sessionId) => {
    // 1. Optimistic local update
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId);
      if (filtered.length === 0) {
        const fresh = createSessionObject();
        setActiveSessionId(fresh.id);
        return [fresh];
      }
      if (activeSessionId === sessionId) {
        setActiveSessionId(filtered[0].id);
      }
      return filtered;
    });

    // 2. Call backend delete action
    try {
      await chatbotApi.deleteChatSession(sessionId);
    } catch (err) {
      console.warn('Backend deleteSession warning:', err);
    }
  }, [activeSessionId]);

  const clearChat = useCallback(async () => {
    if (!activeSessionId) return;

    // Reset messages in local active session
    setSessions(prev => prev.map(session => {
      if (session.id === activeSessionId) {
        return {
          ...session,
          updatedAt: new Date().toISOString(),
          messages: [{ ...INITIAL_WELCOME_MESSAGE, id: `welcome_${Date.now()}`, sessionId: session.id }],
        };
      }
      return session;
    }));

    // Optionally notify backend to delete/clear session
    try {
      await chatbotApi.deleteChatSession(activeSessionId);
    } catch (err) {
      console.warn('Backend clearChat warning:', err);
    }
  }, [activeSessionId]);

  const clearAllSessions = useCallback(async () => {
    const fresh = createSessionObject();
    setSessions([fresh]);
    setActiveSessionId(fresh.id);

    try {
      await chatbotApi.clearAllHistory();
    } catch (err) {
      console.warn('Backend clearAllHistory warning:', err);
    }
  }, []);

  // Cancel In-Flight Request
  const cancelCurrentRequest = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const currentReqId = activeRequestIdRef.current;
    if (currentReqId) {
      try {
        await chatbotApi.cancelChatRequest({ requestId: currentReqId });
      } catch (err) {
        console.warn('Failed to send cancel signal:', err);
      }
    }

    setIsLoading(false);
  }, []);

  // Core Send Message Handler
  const sendMessage = useCallback(async (content) => {
    const trimmed = content?.trim();
    if (!trimmed || isLoading) return;

    let targetSessionId = activeSessionId;

    // Ensure we have an active session
    if (!targetSessionId || !sessions.some(s => s.id === targetSessionId)) {
      targetSessionId = createNewSession();
    }

    const now = new Date().toISOString();
    const userMsg = {
      id: `msg_user_${Date.now()}`,
      role: ROLES.USER,
      content: trimmed,
      timestamp: now,
      sessionId: targetSessionId,
    };

    // 1. Instantly append user message to local state
    setSessions(prev => prev.map(session => {
      if (session.id === targetSessionId) {
        const isFirstUserMsg = (session.messages || []).filter(m => m.role === ROLES.USER).length === 0;
        const newTitle = isFirstUserMsg
          ? trimmed.slice(0, 30) + (trimmed.length > 30 ? '...' : '')
          : session.title;

        return {
          ...session,
          title: newTitle,
          updatedAt: now,
          messages: [...(session.messages || []), userMsg],
        };
      }
      return session;
    }));

    setIsLoading(true);

    const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    activeRequestIdRef.current = requestId;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // 2. Call backend /ask endpoint
      const assistantMsg = await chatbotApi.sendChatMessage({
        question: trimmed,
        sessionId: targetSessionId,
        requestId: requestId,
        signal: controller.signal,
      });

      // 3. Append assistant response
      setSessions(prev => prev.map(session => {
        if (session.id === targetSessionId) {
          return {
            ...session,
            updatedAt: new Date().toISOString(),
            messages: [...(session.messages || []), assistantMsg],
          };
        }
        return session;
      }));

      // Increment unread count if chat window is closed
      if (viewMode === VIEW_MODES.CLOSED) {
        setUnreadCount(count => count + 1);
      }
    } catch (err) {
      if (err.message !== 'Query request was cancelled.') {
        console.error('Error sending message:', err);
        const errorMsg = {
          id: `msg_err_${Date.now()}`,
          role: ROLES.ASSISTANT,
          content: err.message || 'Sorry, I ran into an issue connecting to the service. Please try again.',
          timestamp: new Date().toISOString(),
          sessionId: targetSessionId,
        };
        setSessions(prev => prev.map(session => {
          if (session.id === targetSessionId) {
            return {
              ...session,
              messages: [...(session.messages || []), errorMsg],
            };
          }
          return session;
        }));
      }
    } finally {
      setIsLoading(false);
      activeRequestIdRef.current = null;
      abortControllerRef.current = null;
    }
  }, [activeSessionId, sessions, isLoading, viewMode, createNewSession]);

  const value = useMemo(() => ({
    viewMode,
    isChatOpen: viewMode !== VIEW_MODES.CLOSED,
    isFullscreen: viewMode === VIEW_MODES.FULLSCREEN,

    sessions,
    activeSessionId,
    activeSession,
    messages,

    isLoading,
    unreadCount,

    suggestionLayout,
    setSuggestionLayout,

    suggestionsDisabled,
    setSuggestionsDisabled,

    inputText,
    setInputText,

    openChat,
    closeChat,
    toggleFullscreen,
    markAsRead,

    sendMessage,
    cancelCurrentRequest,

    createNewSession,
    loadSession,
    deleteSession,

    clearChat,
    clearAllSessions,
  }), [
    viewMode,
    sessions,
    activeSessionId,
    activeSession,
    messages,
    isLoading,
    unreadCount,
    suggestionLayout,
    suggestionsDisabled,
    inputText,
    setSuggestionLayout,
    setSuggestionsDisabled,
    openChat,
    closeChat,
    toggleFullscreen,
    markAsRead,
    sendMessage,
    cancelCurrentRequest,
    createNewSession,
    loadSession,
    deleteSession,
    clearChat,
    clearAllSessions,
  ]);

  return (
    <ChatbotContext.Provider value={value}>
      {children}
    </ChatbotContext.Provider>
  );
};

export default ChatbotProvider;
