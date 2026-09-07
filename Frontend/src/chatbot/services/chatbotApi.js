import { chatStorage } from './chatStorage';
import { chatWebSocketService } from './chatWebSocketService';
import { TRANSPORT_MODES } from '../constants/chatbotConstants';

/**
 * Chatbot API Service Layer
 * 
 * Implements hybrid transport integration supporting both real-time WebSocket
 * action routing and standard HTTP REST fallback.
 * 
 * Transport modes configured via `VITE_CHATBOT_TRANSPORT`:
 * - 'auto' (default): Uses WebSocket when available, falls back to HTTP POST seamlessly
 * - 'websocket': Exclusively uses WebSocket connection
 * - 'http': Exclusively uses HTTP POST requests
 */

const getTransportMode = () => {
  const mode = import.meta.env?.VITE_CHATBOT_TRANSPORT || TRANSPORT_MODES.AUTO;
  return mode.toLowerCase();
};

const getApiBaseUrl = () => {
  return import.meta.env?.VITE_CHATBOT_API_URL;
};

/**
 * Helper to build standard headers including mandatory Authorization bearer token
 */
const getAuthHeaders = () => {
  const token = chatStorage.getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
};

/**
 * Helper to format raw backend message into UI message structure
 */
export const normalizeBackendMessage = (msg) => {
  if (!msg) return null;

  const timestamp = msg.created_at || msg.timestamp || new Date().toISOString();

  let tables = [];
  let summary = msg.summary || null;
  let content = msg.content || '';

  // Check if backend returned SQL query tabular data
  if (Array.isArray(msg.result) && msg.result.length > 0) {
    const firstRow = msg.result[0];

    // Check for failed status payload
    if (firstRow && (firstRow.status === 'failed' || firstRow.error)) {
      content = firstRow.error || 'The query could not be executed.';
    } else {
      tables = [
        {
          title: 'Query Result',
          rows: msg.result,
          summary: summary || `${msg.result.length} record${msg.result.length !== 1 ? 's' : ''} retrieved.`,
        },
      ];
    }
  } else if (msg.tables) {
    tables = msg.tables;
  } else if (msg.tableData) {
    tables = Array.isArray(msg.tableData) ? msg.tableData : [msg.tableData];
  }

  return {
    id: msg.id || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
    role: msg.role || 'assistant',
    content: content,
    sql: msg.sql || null,
    tables: tables,
    summary: summary,
    timings: msg.timings || null,
    timestamp: timestamp,
    sessionId: msg.session_id || msg.sessionId,
  };
};

export const chatbotApi = {
  /**
   * Send a user message to the backend via WebSocket or HTTP fallback
   * 
   * @param {Object} params
   * @param {string} params.question - The natural-language prompt
   * @param {string} params.sessionId - Chat session ID
   * @param {string} [params.requestId] - Custom identifier to track/cancel request
   * @param {AbortSignal} [params.signal] - AbortSignal for network request cancellation
   * @param {Function} [params.onProgress] - Callback for real-time planner execution steps
   * @returns {Promise<Object>} Formatted assistant response message
   */
  sendChatMessage: async ({ question, sessionId, requestId, signal, onProgress }) => {
    const transport = getTransportMode();
    const reqId = requestId || `req_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    const username = chatStorage.getStoredUsername();

    // 1. Try WebSocket if enabled and available
    if (transport === TRANSPORT_MODES.WEBSOCKET || (transport === TRANSPORT_MODES.AUTO && chatWebSocketService.isConnected())) {
      try {
        const wsResponse = await chatWebSocketService.ask({
          question,
          sessionId,
          username,
          requestId: reqId,
          onProgress,
          signal,
        });

        const payloadData = wsResponse.data || {};
        return normalizeBackendMessage({
          id: `msg_bot_${Date.now()}`,
          role: 'assistant',
          content: payloadData.content || payloadData.summary || (payloadData.result?.length === 0 ? 'No records found matching your query.' : ''),
          sql: payloadData.sql,
          result: payloadData.result,
          tables: payloadData.tables,
          summary: payloadData.summary,
          timings: payloadData.timings,
          sessionId: sessionId,
          created_at: new Date().toISOString(),
        });
      } catch (wsErr) {
        // If query was intentionally cancelled, rethrow
        if (wsErr.message?.includes('cancelled')) {
          throw wsErr;
        }

        console.warn('[Chatbot API] WebSocket send failed, checking fallback:', wsErr.message);

        // If forced WebSocket mode, throw error
        if (transport === TRANSPORT_MODES.WEBSOCKET) {
          throw wsErr;
        }
        // Otherwise fall through to HTTP POST fallback
      }
    }

    // 2. HTTP POST Fallback
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) {
      throw new Error('API Base URL is not configured.');
    }

    const payload = {
      action: 'ask',
      question: question,
      username: username,
      request_id: reqId,
      session_id: sessionId,
    };

    try {
      if (onProgress) {
        onProgress({
          requestId: reqId,
          status: 'processing',
          step: 'http_request',
          message: 'Connecting via HTTP service...',
        });
      }

      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
        signal: signal,
      });

      if (!response.ok) {
        let errMessage = `API Request failed with status ${response.status}`;
        try {
          const errData = await response.json();
          if (errData?.message || errData?.detail || errData?.error) {
            errMessage = errData.message || errData.detail || errData.error;
          }
        } catch {
          // ignore parsing error
        }
        throw new Error(errMessage);
      }

      const data = await response.json();

      return normalizeBackendMessage({
        id: `msg_bot_${Date.now()}`,
        role: 'assistant',
        content: data.content || data.message || (data.result?.length === 0 ? 'No records found matching your query.' : ''),
        sql: data.sql,
        result: data.result,
        tables: data.tables,
        summary: data.summary,
        timings: data.timings,
        sessionId: sessionId,
        created_at: new Date().toISOString(),
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error('Query request was cancelled.');
      }
      console.error('Chatbot API sendChatMessage error:', err);
      throw err;
    }
  },

  /**
   * Cancel an active running query via WebSocket or POST /ask
   * 
   * @param {Object} params
   * @param {string} params.requestId - Identifier of the request to cancel
   * @returns {Promise<Object>} Cancellation status
   */
  cancelChatRequest: async ({ requestId }) => {
    if (!requestId) return { status: 'noop' };

    // Try WebSocket cancel if connected
    if (chatWebSocketService.isConnected()) {
      try {
        const res = await chatWebSocketService.cancel(requestId);
        return res;
      } catch (err) {
        console.warn('WS Cancel error:', err);
      }
    }

    const baseUrl = getApiBaseUrl();
    if (!baseUrl) return { status: 'error', message: 'No API URL' };

    const username = chatStorage.getStoredUsername();

    try {
      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: 'cancel',
          username: username,
          request_id: requestId,
          target_request_id: requestId,
        }),
      });

      if (!response.ok) {
        return { status: 'error', message: `Cancel failed with status ${response.status}` };
      }

      return await response.json();
    } catch (err) {
      console.warn('Chatbot API cancelChatRequest warning:', err);
      return { status: 'error', message: err.message };
    }
  },

  /**
   * Retrieve all session summaries for the current user via WebSocket or POST /ask
   * 
   * @returns {Promise<Array>} List of session summaries: [{ id, title, created_at, updated_at }]
   */
  getChatSessions: async () => {
    const username = chatStorage.getStoredUsername();

    // 1. Try WebSocket first if connected
    if (chatWebSocketService.isConnected()) {
      try {
        const wsRes = await chatWebSocketService.getHistory(username);
        const sessionsData = wsRes.data;
        if (Array.isArray(sessionsData)) {
          return sessionsData.map((s) => ({
            id: s.id || s.session_id,
            title: s.title || 'Conversation',
            createdAt: s.created_at || s.createdAt || new Date().toISOString(),
            updatedAt: s.updated_at || s.updatedAt || new Date().toISOString(),
            messages: [],
          }));
        }
      } catch (wsErr) {
        console.warn('[WS] getChatSessions failed, using HTTP fallback:', wsErr.message);
      }
    }

    // 2. HTTP Fallback
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) return null;

    try {
      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: 'history',
          username: username,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to load history (HTTP ${response.status})`);
      }

      const sessionsData = await response.json();
      if (!Array.isArray(sessionsData)) {
        return [];
      }

      return sessionsData.map((s) => ({
        id: s.id || s.session_id,
        title: s.title || 'Conversation',
        createdAt: s.created_at || s.createdAt || new Date().toISOString(),
        updatedAt: s.updated_at || s.updatedAt || new Date().toISOString(),
        messages: [],
      }));
    } catch (err) {
      console.warn('Could not fetch sessions from backend, using local cache:', err.message);
      return null;
    }
  },

  /**
   * Retrieve the full message thread for a specific session ID via WebSocket or POST /ask
   * 
   * @param {string} sessionId
   * @returns {Promise<Object>} Session object with complete messages array
   */
  getSessionHistory: async (sessionId) => {
    if (!sessionId) return null;
    const username = chatStorage.getStoredUsername();

    // 1. Try WebSocket first if connected
    if (chatWebSocketService.isConnected()) {
      try {
        const wsRes = await chatWebSocketService.getSessionHistory(sessionId, username);
        const data = wsRes.data;
        if (data) {
          const rawMessages = Array.isArray(data.messages) ? data.messages : [];
          const normalizedMessages = rawMessages.map(normalizeBackendMessage).filter(Boolean);

          return {
            id: data.id || sessionId,
            title: data.title || 'Conversation',
            createdAt: data.created_at || new Date().toISOString(),
            updatedAt: data.updated_at || new Date().toISOString(),
            messages: normalizedMessages,
          };
        }
      } catch (wsErr) {
        console.warn('[WS] getSessionHistory failed, using HTTP fallback:', wsErr.message);
      }
    }

    // 2. HTTP Fallback
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) return null;

    try {
      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: 'history_session',
          username: username,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch session history (HTTP ${response.status})`);
      }

      const data = await response.json();
      const rawMessages = Array.isArray(data.messages) ? data.messages : [];
      const normalizedMessages = rawMessages.map(normalizeBackendMessage).filter(Boolean);

      return {
        id: data.id || sessionId,
        title: data.title || 'Conversation',
        createdAt: data.created_at || new Date().toISOString(),
        updatedAt: data.updated_at || new Date().toISOString(),
        messages: normalizedMessages,
      };
    } catch (err) {
      console.warn(`Could not fetch session history for ${sessionId} from backend:`, err.message);
      return null;
    }
  },

  /**
   * Delete a specific session thread via WebSocket or POST /ask
   * 
   * @param {string} sessionId
   * @returns {Promise<boolean>} Success indicator
   */
  deleteChatSession: async (sessionId) => {
    if (!sessionId) return false;
    const username = chatStorage.getStoredUsername();

    // 1. Try WebSocket
    if (chatWebSocketService.isConnected()) {
      try {
        const res = await chatWebSocketService.deleteSession(sessionId, username);
        if (res.status === 'success') return true;
      } catch (wsErr) {
        console.warn('[WS] deleteChatSession failed, falling back to HTTP:', wsErr.message);
      }
    }

    // 2. HTTP Fallback
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) return false;

    try {
      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: 'delete_session',
          username: username,
          session_id: sessionId,
        }),
      });

      return response.ok;
    } catch (err) {
      console.warn(`Failed to delete session ${sessionId} on backend:`, err.message);
      return false;
    }
  },

  /**
   * Clear all session histories for current user via WebSocket or POST /ask
   * 
   * @returns {Promise<boolean>} Success indicator
   */
  clearAllHistory: async () => {
    const username = chatStorage.getStoredUsername();

    // 1. Try WebSocket
    if (chatWebSocketService.isConnected()) {
      try {
        const res = await chatWebSocketService.clearAllHistory(username);
        if (res.status === 'success') return true;
      } catch (wsErr) {
        console.warn('[WS] clearAllHistory failed, falling back to HTTP:', wsErr.message);
      }
    }

    // 2. HTTP Fallback
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) return false;

    try {
      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: 'clear_history',
          username: username,
        }),
      });

      return response.ok;
    } catch (err) {
      console.warn('Failed to clear all history on backend:', err.message);
      return false;
    }
  },

  /**
   * Request SVG Chart Rendering from backend
   * 
   * @param {string} chartType - 'bar' | 'line' | 'pie' | etc.
   * @param {Array} data - Tabular dataset
   * @returns {Promise<string|null>} SVG XML string
   */
  renderSvgChart: async (chartType, data) => {
    if (!chartType || !data) return null;

    // 1. Try WebSocket
    if (chatWebSocketService.isConnected()) {
      try {
        const res = await chatWebSocketService.renderChart(chartType, data);
        if (res.status === 'success' && res.data?.svg) {
          return res.data.svg;
        }
      } catch (wsErr) {
        console.warn('[WS] renderChart failed, falling back to HTTP:', wsErr.message);
      }
    }

    // 2. HTTP Fallback
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) return null;

    try {
      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: 'chart',
          chart_type: chartType,
          data: data,
          username: chatStorage.getStoredUsername(),
        }),
      });

      if (!response.ok) return null;
      const json = await response.json();
      return json.data?.svg || json.svg || null;
    } catch (err) {
      console.warn('Failed to render chart on backend:', err.message);
      return null;
    }
  },
};

export default chatbotApi;
