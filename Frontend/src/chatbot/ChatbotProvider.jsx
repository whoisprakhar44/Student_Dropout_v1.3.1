import React, { createContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  VIEW_MODES,
  ROLES,
  INITIAL_WELCOME_MESSAGE,
  INITIAL_SCHEMA_WELCOME_MESSAGE,
  SUGGESTION_LAYOUTS,
  WS_CONNECTION_STATUS,
  CHAT_LAYERS,
  DEFAULT_LAYER
} from './constants/chatbotConstants';
import { chatStorage } from './services/chatStorage';
import { chatbotApi } from './services/chatbotApi';
import { chatWebSocketService } from './services/chatWebSocketService';
import { suggestionsService } from './services/suggestionsService';
import { speechService } from './services/speechService';

export const ChatbotContext = createContext(null);

export const ChatbotProvider = ({ children, initialLayer, schemaEnabled }) => {
  // 1. Initial State Hydration from localStorage & Props
  const [viewMode, setViewMode] = useState(() => chatStorage.getViewMode());
  const [activeLayer, setActiveLayerState] = useState(() => {
    return initialLayer || chatStorage.getActiveLayer() || DEFAULT_LAYER;
  });

  // SDUI Privileges state (includes table export, copy permissions, copy protection, devtools protection)
  const [sduiPrivileges, setSduiPrivilegesState] = useState(() => {
    const privs = chatStorage.getSduiPrivileges();
    if (schemaEnabled !== undefined) {
      privs.isSchemaEnabled = Boolean(schemaEnabled);
    }
    return privs;
  });

  const [isSchemaEnabled, setIsSchemaEnabledState] = useState(() => {
    if (schemaEnabled !== undefined) return Boolean(schemaEnabled);
    return chatStorage.getIsSchemaEnabled();
  });

  const [securityToast, setSecurityToast] = useState(null);
  const [isDevToolsOpen, setIsDevToolsOpen] = useState(false);
  const securityToastTimeoutRef = useRef(null);

  const [sessions, setSessions] = useState(() => chatStorage.getSessions());
  const [activeSessionId, setActiveSessionId] = useState(() => chatStorage.getActiveSessionId(chatStorage.getActiveLayer()));
  const [unreadCount, setUnreadCount] = useState(() => chatStorage.getUnreadCount());
  const [loadingSessions, setLoadingSessions] = useState({}); // { [sessionId]: true }
  const [sessionProgress, setSessionProgress] = useState({}); // { [sessionId]: progressObj }
  const [connectionStatus, setConnectionStatus] = useState(chatWebSocketService.status);
  const [suggestionLayout, setSuggestionLayoutState] = useState(() => {
    return chatStorage.getSuggestionLayout() || (import.meta.env?.VITE_SUGGESTION_LAYOUT || SUGGESTION_LAYOUTS.HORIZONTAL).toLowerCase();
  });
  const [suggestionsDisabled, setSuggestionsDisabledState] = useState(
    () => suggestionsService.isSuggestionsDisabled()
  );
  const [inputText, setInputText] = useState('');
  const [activeRightView, setActiveRightView] = useState('chat'); // 'chat' | 'about'
  const [selectedSchemaGroup, setSelectedSchemaGroup] = useState(null);

  const activeRequestsRef = useRef({}); // { [sessionId]: { requestId, controller } }

  // Derived loading & progress for active session
  const isLoading = Boolean(loadingSessions[activeSessionId]);
  const activeProgress = sessionProgress[activeSessionId] || null;

  const isSessionLoading = useCallback((sessionId) => {
    return Boolean(loadingSessions[sessionId]);
  }, [loadingSessions]);

  // Security Toast Trigger
  const showSecurityToast = useCallback((msg = '🔒 Content copy & export protection is enabled.') => {
    if (securityToastTimeoutRef.current) {
      clearTimeout(securityToastTimeoutRef.current);
    }
    setSecurityToast(msg);
    securityToastTimeoutRef.current = setTimeout(() => {
      setSecurityToast(null);
    }, 3200);
  }, []);

  // Update SDUI Privileges dynamically
  const updateSduiPrivileges = useCallback((patch) => {
    setSduiPrivilegesState(prev => {
      const next = { ...prev, ...patch };
      chatStorage.saveSduiPrivileges(next);
      if (patch.isSchemaEnabled !== undefined) {
        setIsSchemaEnabledState(Boolean(patch.isSchemaEnabled));
        chatStorage.saveIsSchemaEnabled(Boolean(patch.isSchemaEnabled));
      }
      return next;
    });
  }, []);

  // Helper to construct a new session object
  const createSessionObject = useCallback((initialMessages = [], layer = activeLayer) => {
    const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    const now = new Date().toISOString();
    const isSchema = layer === CHAT_LAYERS.SCHEMA;
    const defaultWelcome = isSchema ? INITIAL_SCHEMA_WELCOME_MESSAGE : INITIAL_WELCOME_MESSAGE;

    return {
      id: newId,
      title: isSchema ? 'New Schema Query' : 'New Conversation',
      layer: layer || CHAT_LAYERS.CURATED,
      createdAt: now,
      updatedAt: now,
      messages: initialMessages.length > 0 ? initialMessages : [{ ...defaultWelcome, sessionId: newId, layer: layer || CHAT_LAYERS.CURATED }],
    };
  }, [activeLayer]);

  // Derived sessions for current layer
  const currentLayerSessions = useMemo(() => {
    return sessions.filter(s => (s.layer || CHAT_LAYERS.CURATED) === activeLayer);
  }, [sessions, activeLayer]);

  // 2. Initialize WebSocket Connection and Listen to Connection Status
  useEffect(() => {
    chatWebSocketService.connect();
    const unsub = chatWebSocketService.onStatusChange((status) => {
      setConnectionStatus(status);
    });
    return () => unsub();
  }, []);

  // Dynamic SDUI Synchronization with Backend
  const syncSduiSettings = useCallback(async (customUsername = null) => {
    try {
      const serverSdui = await chatbotApi.getSduiSettings(customUsername);
      if (serverSdui && typeof serverSdui === 'object') {
        setSduiPrivilegesState(prev => {
          const merged = { ...prev, ...serverSdui };
          chatStorage.saveSduiPrivileges(merged);

          // Schema Layer Enforcement
          if (merged.isSchemaEnabled !== undefined) {
            const schemaOn = Boolean(merged.isSchemaEnabled);
            setIsSchemaEnabledState(schemaOn);
            chatStorage.saveIsSchemaEnabled(schemaOn);
            if (!schemaOn) {
              setActiveLayerState(curr => {
                if (curr === CHAT_LAYERS.SCHEMA) {
                  chatStorage.saveActiveLayer(CHAT_LAYERS.CURATED);
                  return CHAT_LAYERS.CURATED;
                }
                return curr;
              });
            }
          }

          // About Section Enforcement
          if (merged.showAboutSection === false) {
            setActiveRightView(curr => (curr === 'about' ? 'chat' : curr));
          }

          // Account Suspension Warning
          if (merged.is_active === false) {
            showSecurityToast('🔒 Account suspended by administrator. Access restricted.');
          }

          return merged;
        });
        return serverSdui;
      }
    } catch (err) {
      console.warn('SDUI synchronization failed:', err);
    }
    return null;
  }, [showSecurityToast]);

  // 3. Fetch SDUI Settings & Privileges on Chat Init & Storage Listeners
  useEffect(() => {
    syncSduiSettings();

    const handleStorageChange = (e) => {
      if (e.key === 'username' || e.key === 'userInfo' || e.key === 'token') {
        syncSduiSettings();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [syncSduiSettings]);

  // 4. Fetch Sessions & History from Backend on Mount
  useEffect(() => {
    let isMounted = true;

    const syncWithBackend = async () => {
      try {
        const backendSessions = await chatbotApi.getChatSessions(activeLayer);

        if (!isMounted) return;

        if (Array.isArray(backendSessions) && backendSessions.length > 0) {
          // Merge sessions: update current layer backend sessions while retaining local
          setSessions(prev => {
            const otherLayerSessions = prev.filter(s => (s.layer || CHAT_LAYERS.CURATED) !== activeLayer);
            return [...backendSessions, ...otherLayerSessions];
          });

          const currentLayerExisting = backendSessions.filter(s => (s.layer || CHAT_LAYERS.CURATED) === activeLayer);
          const targetId = (activeSessionId && currentLayerExisting.some(s => s.id === activeSessionId))
            ? activeSessionId
            : currentLayerExisting[0]?.id;

          if (targetId) {
            setActiveSessionId(targetId);

            // Fetch full message thread for the active session
            const sessionDetails = await chatbotApi.getSessionHistory(targetId, activeLayer);
            if (isMounted && sessionDetails && Array.isArray(sessionDetails.messages)) {
              setSessions(prev =>
                prev.map(s => (s.id === targetId ? { ...s, messages: sessionDetails.messages } : s))
              );
            }
          }
        } else if (sessions.length === 0 || !sessions.some(s => (s.layer || CHAT_LAYERS.CURATED) === activeLayer)) {
          // No backend sessions and no local sessions for active layer: initialize default session
          const defaultSession = createSessionObject([], activeLayer);
          setSessions(prev => [defaultSession, ...prev.filter(s => s.id !== defaultSession.id)]);
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
  }, [activeLayer, createSessionObject]);

  // 5. Copy Protection & DevTools Heuristic Detection
  useEffect(() => {
    const isCopyProtected = sduiPrivileges?.copyProtection;
    const isDevToolsProtected = sduiPrivileges?.devToolsProtection;

    if (!isCopyProtected && !isDevToolsProtected) return;

    const handleCopy = (e) => {
      if (!isCopyProtected) return;
      const isInsideChat = e.target?.closest?.('.cb-root') || document.activeElement?.closest?.('.cb-root');
      if (isInsideChat) {
        e.preventDefault();
        if (e.clipboardData) {
          e.clipboardData.setData('text/plain', '');
        }
        showSecurityToast('🔒 Content copy protection is enabled by administrator.');
      }
    };

    const handleCut = (e) => {
      if (!isCopyProtected) return;
      if (e.target?.closest?.('.cb-root')) {
        e.preventDefault();
        showSecurityToast('🔒 Content modification is restricted.');
      }
    };

    const handleContextMenu = (e) => {
      if (!isCopyProtected) return;
      if (e.target?.closest?.('.cb-root')) {
        e.preventDefault();
        showSecurityToast('🔒 Right-click context menu is restricted on protected content.');
      }
    };

    const handleKeyDown = (e) => {
      if (!isCopyProtected && !isDevToolsProtected) return;
      const isInsideChat = e.target?.closest?.('.cb-root');

      // Intercept Ctrl+C / Cmd+C inside chat
      if (isCopyProtected && (e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C')) {
        if (isInsideChat) {
          e.preventDefault();
          showSecurityToast('🔒 Clipboard copy shortcut is disabled by policy.');
          return;
        }
      }

      // Intercept Ctrl+U (View Source)
      if (isCopyProtected && (e.ctrlKey || e.metaKey) && (e.key === 'u' || e.key === 'U')) {
        if (isInsideChat) {
          e.preventDefault();
          showSecurityToast('🔒 Source viewing is restricted.');
          return;
        }
      }

      // Intercept DevTools shortcuts
      if (isDevToolsProtected) {
        if (
          e.key === 'F12' ||
          ((e.ctrlKey || e.metaKey) && e.shiftKey && ['I', 'i', 'J', 'j', 'C', 'c'].includes(e.key))
        ) {
          if (isInsideChat) {
            e.preventDefault();
            showSecurityToast('🔒 Developer inspection tools are restricted.');
          }
        }

        if (e.key === 'PrintScreen') {
          showSecurityToast('⚠️ Screenshot detection: protected data.');
        }
      }
    };

    // DevTools detection heuristic
    const checkDevTools = () => {
      if (!isDevToolsProtected) {
        setIsDevToolsOpen(false);
        return;
      }
      const threshold = 160;
      const widthThreshold = window.outerWidth - window.innerWidth > threshold;
      const heightThreshold = window.outerHeight - window.innerHeight > threshold;
      setIsDevToolsOpen(widthThreshold || heightThreshold);
    };

    window.addEventListener('copy', handleCopy, true);
    window.addEventListener('cut', handleCut, true);
    window.addEventListener('contextmenu', handleContextMenu, true);
    window.addEventListener('keydown', handleKeyDown, true);
    window.addEventListener('resize', checkDevTools);

    const intervalId = setInterval(checkDevTools, 2500);

    return () => {
      window.removeEventListener('copy', handleCopy, true);
      window.removeEventListener('cut', handleCut, true);
      window.removeEventListener('contextmenu', handleContextMenu, true);
      window.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('resize', checkDevTools);
      clearInterval(intervalId);
    };
  }, [sduiPrivileges, showSecurityToast]);

  // 6. Persist State Changes to localStorage
  useEffect(() => {
    chatStorage.saveViewMode(viewMode);
  }, [viewMode]);

  useEffect(() => {
    chatStorage.saveActiveLayer(activeLayer);
  }, [activeLayer]);

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
    chatStorage.saveActiveSessionId(activeSessionId, activeLayer);
  }, [activeSessionId, activeLayer]);

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
    const inLayer = sessions.find(s => s.id === activeSessionId && (s.layer || CHAT_LAYERS.CURATED) === activeLayer);
    if (inLayer) return inLayer;
    const fallbackInLayer = sessions.find(s => (s.layer || CHAT_LAYERS.CURATED) === activeLayer);
    return fallbackInLayer || sessions[0] || null;
  }, [sessions, activeSessionId, activeLayer]);

  const messages = useMemo(() => {
    return activeSession ? (activeSession.messages || []) : [];
  }, [activeSession]);

  // Layer Switcher Handler
  const setActiveLayer = useCallback(async (newLayer) => {
    if (newLayer !== CHAT_LAYERS.SCHEMA && newLayer !== CHAT_LAYERS.CURATED) {
      newLayer = DEFAULT_LAYER;
    }

    if (newLayer === activeLayer) return;

    setActiveLayerState(newLayer);
    chatStorage.saveActiveLayer(newLayer);
    setActiveRightView('chat');

    // Check for existing session in target layer
    const matchingSessions = sessions.filter(s => (s.layer || CHAT_LAYERS.CURATED) === newLayer);
    const savedLayerSessionId = chatStorage.getActiveSessionId(newLayer);

    let targetSession = null;
    if (savedLayerSessionId && matchingSessions.some(s => s.id === savedLayerSessionId)) {
      targetSession = matchingSessions.find(s => s.id === savedLayerSessionId);
    } else if (matchingSessions.length > 0) {
      targetSession = matchingSessions[0];
    }

    if (targetSession) {
      setActiveSessionId(targetSession.id);
      chatStorage.saveActiveSessionId(targetSession.id, newLayer);

      // If messages not loaded, load session history
      if (!targetSession.messages || targetSession.messages.length <= 1) {
        try {
          const details = await chatbotApi.getSessionHistory(targetSession.id, newLayer);
          if (details && Array.isArray(details.messages) && details.messages.length > 0) {
            setSessions(prev => prev.map(s => (s.id === targetSession.id ? { ...s, messages: details.messages } : s)));
          }
        } catch (e) {
          // ignore
        }
      }
    } else {
      // Create fresh session for this layer
      const fresh = createSessionObject([], newLayer);
      setSessions(prev => [fresh, ...prev]);
      setActiveSessionId(fresh.id);
      chatStorage.saveActiveSessionId(fresh.id, newLayer);
    }

    // Attempt background sync for this layer from backend
    try {
      const backendHistory = await chatbotApi.getChatSessions(newLayer);
      if (Array.isArray(backendHistory) && backendHistory.length > 0) {
        setSessions(prev => {
          const otherLayers = prev.filter(s => (s.layer || CHAT_LAYERS.CURATED) !== newLayer);
          return [...backendHistory, ...otherLayers];
        });
      }
    } catch (err) {
      console.warn(`Failed to fetch chat history for layer ${newLayer}:`, err);
    }
  }, [activeLayer, sessions, createSessionObject]);

  // SDUI Visibility Controller
  const setIsSchemaEnabled = useCallback((enabled) => {
    const val = Boolean(enabled);
    setIsSchemaEnabledState(val);
    chatStorage.saveIsSchemaEnabled(val);
    setSduiPrivilegesState(prev => {
      const next = { ...prev, isSchemaEnabled: val };
      chatStorage.saveSduiPrivileges(next);
      return next;
    });
    if (!val && activeLayer === CHAT_LAYERS.SCHEMA) {
      setActiveLayer(CHAT_LAYERS.CURATED);
    }
  }, [activeLayer, setActiveLayer]);

  // Layout switcher
  const setSuggestionLayout = useCallback((layout) => {
    const valid =
      layout === SUGGESTION_LAYOUTS.VERTICAL
        ? SUGGESTION_LAYOUTS.VERTICAL
        : SUGGESTION_LAYOUTS.HORIZONTAL;

    setSuggestionLayoutState(valid);
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

  // Schema & About View Handlers
  const openAboutView = useCallback((groupName = null) => {
    setActiveRightView('about');
    if (groupName !== undefined && groupName !== null) {
      setSelectedSchemaGroup(groupName);
    }
  }, []);

  const closeAboutView = useCallback(() => {
    setActiveRightView('chat');
  }, []);

  // Session Handlers
  const createNewSession = useCallback((layerOverride) => {
    const targetLayer = layerOverride || activeLayer;
    const newSession = createSessionObject([], targetLayer);
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    chatStorage.saveActiveSessionId(newSession.id, targetLayer);
    setActiveRightView('chat');
    return newSession.id;
  }, [activeLayer, createSessionObject]);

  const loadSession = useCallback(async (sessionId) => {
    if (!sessionId) return;
    setActiveSessionId(sessionId);
    setActiveRightView('chat');

    const current = sessions.find(s => s.id === sessionId);
    const sessionLayer = current?.layer || activeLayer;
    chatStorage.saveActiveSessionId(sessionId, sessionLayer);

    // If messages are not yet loaded for this session, fetch from backend
    if (!current || !current.messages || current.messages.length <= 1) {
      try {
        const sessionDetails = await chatbotApi.getSessionHistory(sessionId, sessionLayer);
        if (sessionDetails && Array.isArray(sessionDetails.messages) && sessionDetails.messages.length > 0) {
          setSessions(prev =>
            prev.map(s => (s.id === sessionId ? { ...s, messages: sessionDetails.messages } : s))
          );
        }
      } catch (err) {
        console.warn('Failed to load session messages from backend:', err);
      }
    }
  }, [sessions, activeLayer]);

  const cancelCurrentRequest = useCallback(async (sessionIdToCancel) => {
    const targetId = sessionIdToCancel || activeSessionId;
    if (!targetId) return;

    const sessionReq = activeRequestsRef.current[targetId];
    if (sessionReq) {
      if (sessionReq.controller) {
        sessionReq.controller.abort();
      }
      if (sessionReq.requestId) {
        try {
          await chatbotApi.cancelChatRequest({ requestId: sessionReq.requestId });
        } catch (err) {
          console.warn('Failed to send cancel signal:', err);
        }
      }
      delete activeRequestsRef.current[targetId];
    }

    setLoadingSessions(prev => {
      const next = { ...prev };
      delete next[targetId];
      return next;
    });
    setSessionProgress(prev => {
      const next = { ...prev };
      delete next[targetId];
      return next;
    });
  }, [activeSessionId]);

  const deleteSession = useCallback(async (sessionId) => {
    // If target session has an in-flight request, cancel it first
    if (activeRequestsRef.current[sessionId]) {
      cancelCurrentRequest(sessionId);
    }

    const sessionToDelete = sessions.find(s => s.id === sessionId);
    const sessionLayer = sessionToDelete?.layer || activeLayer;

    // 1. Optimistic local update
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId);
      const remainingInLayer = filtered.filter(s => (s.layer || CHAT_LAYERS.CURATED) === sessionLayer);

      if (remainingInLayer.length === 0) {
        const fresh = createSessionObject([], sessionLayer);
        if (activeSessionId === sessionId) {
          setActiveSessionId(fresh.id);
          chatStorage.saveActiveSessionId(fresh.id, sessionLayer);
        }
        return [fresh, ...filtered];
      }

      if (activeSessionId === sessionId) {
        setActiveSessionId(remainingInLayer[0].id);
        chatStorage.saveActiveSessionId(remainingInLayer[0].id, sessionLayer);
      }
      return filtered;
    });

    // 2. Call backend delete action
    try {
      await chatbotApi.deleteChatSession(sessionId, sessionLayer);
    } catch (err) {
      console.warn('Backend deleteSession warning:', err);
    }
  }, [activeSessionId, activeLayer, cancelCurrentRequest, sessions, createSessionObject]);

  const clearChat = useCallback(async () => {
    if (!activeSessionId) return;

    const currentSession = sessions.find(s => s.id === activeSessionId);
    const sessionLayer = currentSession?.layer || activeLayer;
    const isSchema = sessionLayer === CHAT_LAYERS.SCHEMA;
    const defaultWelcome = isSchema ? INITIAL_SCHEMA_WELCOME_MESSAGE : INITIAL_WELCOME_MESSAGE;

    // Reset messages in local active session
    setSessions(prev => prev.map(session => {
      if (session.id === activeSessionId) {
        return {
          ...session,
          updatedAt: new Date().toISOString(),
          messages: [{ ...defaultWelcome, id: `welcome_${Date.now()}`, sessionId: session.id, layer: sessionLayer }],
        };
      }
      return session;
    }));

    // Notify backend
    try {
      await chatbotApi.deleteChatSession(activeSessionId, sessionLayer);
    } catch (err) {
      console.warn('Backend clearChat warning:', err);
    }
  }, [activeSessionId, activeLayer, sessions]);

  const clearAllSessions = useCallback(async (layerOverride) => {
    const targetLayer = layerOverride || activeLayer;

    // Cancel all in-flight queries across all sessions
    Object.keys(activeRequestsRef.current).forEach(sId => {
      cancelCurrentRequest(sId);
    });

    const fresh = createSessionObject([], targetLayer);
    setSessions(prev => {
      const otherLayers = prev.filter(s => (s.layer || CHAT_LAYERS.CURATED) !== targetLayer);
      return [fresh, ...otherLayers];
    });
    setActiveSessionId(fresh.id);
    chatStorage.saveActiveSessionId(fresh.id, targetLayer);

    try {
      await chatbotApi.clearAllHistory(targetLayer);
    } catch (err) {
      console.warn('Backend clearAllHistory warning:', err);
    }
  }, [activeLayer, cancelCurrentRequest, createSessionObject]);

  // Core Send Message Handler
  const sendMessage = useCallback(async (content, targetSessionIdOverride, layerOverride) => {
    const trimmed = content?.trim();
    if (!trimmed) return;

    let targetSessionId = targetSessionIdOverride || activeSessionId;
    const targetLayer = layerOverride || (sessions.find(s => s.id === targetSessionId)?.layer) || activeLayer;

    // Ensure we have an active session
    if (!targetSessionId || !sessions.some(s => s.id === targetSessionId)) {
      targetSessionId = createNewSession(targetLayer);
    }

    // Check user active status from SDUI RBAC
    if (sduiPrivileges?.is_active === false) {
      showSecurityToast('🔒 Account suspended by administrator. Access restricted.');
      return;
    }

    // Check schema layer permission from SDUI RBAC
    if (targetLayer === CHAT_LAYERS.SCHEMA && sduiPrivileges?.isSchemaEnabled === false) {
      showSecurityToast('🔒 Schema layer querying is restricted for your role.');
      return;
    }

    // Prevent duplicate concurrent requests in the same session
    if (loadingSessions[targetSessionId]) {
      return;
    }

    const now = new Date().toISOString();
    const userMsg = {
      id: `msg_user_${Date.now()}`,
      role: ROLES.USER,
      content: trimmed,
      timestamp: now,
      sessionId: targetSessionId,
      layer: targetLayer,
    };

    // 1. Instantly append user message to target session in local state
    setSessions(prev => prev.map(session => {
      if (session.id === targetSessionId) {
        const isFirstUserMsg = (session.messages || []).filter(m => m.role === ROLES.USER).length === 0;
        const newTitle = isFirstUserMsg
          ? trimmed.slice(0, 30) + (trimmed.length > 30 ? '...' : '')
          : session.title;

        return {
          ...session,
          title: newTitle,
          layer: targetLayer,
          updatedAt: now,
          messages: [...(session.messages || []), userMsg],
        };
      }
      return session;
    }));

    // Set loading & initial progress specifically for targetSessionId
    setLoadingSessions(prev => ({ ...prev, [targetSessionId]: true }));
    setSessionProgress(prev => ({
      ...prev,
      [targetSessionId]: {
        step: 'queued',
        message: targetLayer === CHAT_LAYERS.SCHEMA ? 'Inspecting schema model & analyzing request...' : 'Submitting query to assistant...',
        timestamp: new Date().toISOString(),
      },
    }));

    const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    const controller = new AbortController();
    activeRequestsRef.current[targetSessionId] = { requestId, controller };

    try {
      // 2. Call backend via WebSocket or HTTP fallback with progress streaming
      const assistantMsg = await chatbotApi.sendChatMessage({
        question: trimmed,
        sessionId: targetSessionId,
        requestId: requestId,
        signal: controller.signal,
        layer: targetLayer,
        onProgress: (prog) => {
          setSessionProgress(prev => ({
            ...prev,
            [targetSessionId]: prog,
          }));
        },
      });

      // 3. Append assistant response to target session
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

      // Auto-play speech if enabled in settings and message contains content/summary
      if (targetSessionId === activeSessionId) {
        speechService.handleAutoPlayNewMessage(assistantMsg);
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
          layer: targetLayer,
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
      setLoadingSessions(prev => {
        const next = { ...prev };
        delete next[targetSessionId];
        return next;
      });
      setSessionProgress(prev => {
        const next = { ...prev };
        delete next[targetSessionId];
        return next;
      });
      delete activeRequestsRef.current[targetSessionId];
    }
  }, [activeSessionId, activeLayer, sessions, loadingSessions, viewMode, createNewSession]);

  const value = useMemo(() => ({
    viewMode,
    isChatOpen: viewMode !== VIEW_MODES.CLOSED,
    isFullscreen: viewMode === VIEW_MODES.FULLSCREEN,

    // Layer & SDUI Privileges State
    activeLayer,
    setActiveLayer,
    isSchemaEnabled,
    setIsSchemaEnabled,
    currentLayerSessions,
    sduiPrivileges,
    updateSduiPrivileges,
    securityToast,
    showSecurityToast,
    isDevToolsOpen,

    connectionStatus,
    isConnected: connectionStatus === WS_CONNECTION_STATUS.CONNECTED,
    activeProgress,
    loadingSessions,
    isSessionLoading,

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

    activeRightView,
    setActiveRightView,
    selectedSchemaGroup,
    setSelectedSchemaGroup,
    openAboutView,
    closeAboutView,

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

    // SDUI & RBAC Governance
    syncSduiSettings,
    userRole: sduiPrivileges?.role || 'Citizen Viewer',
    isUserActive: sduiPrivileges?.is_active ?? true,
    canShowAboutSection: sduiPrivileges?.showAboutSection ?? true,
  }), [
    viewMode,
    activeLayer,
    setActiveLayer,
    isSchemaEnabled,
    setIsSchemaEnabled,
    currentLayerSessions,
    sduiPrivileges,
    updateSduiPrivileges,
    securityToast,
    showSecurityToast,
    isDevToolsOpen,
    connectionStatus,
    activeProgress,
    loadingSessions,
    isSessionLoading,
    sessions,
    activeSessionId,
    activeSession,
    messages,
    isLoading,
    unreadCount,
    suggestionLayout,
    suggestionsDisabled,
    inputText,
    activeRightView,
    selectedSchemaGroup,
    openAboutView,
    closeAboutView,
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
    syncSduiSettings,
  ]);

  return (
    <ChatbotContext.Provider value={value}>
      {children}
    </ChatbotContext.Provider>
  );
};

export default ChatbotProvider;
