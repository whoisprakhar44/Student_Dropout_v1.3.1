import { chatStorage } from './chatStorage';

/**
 * Chatbot API Service Layer
 * 
 * Implements full backend integration with the unified `/ask` multiplexed endpoint
 * as documented in API_CONTRACT.md.
 * 
 * Actions supported:
 * - ask: Execute natural-language SQL queries / chat conversations
 * - cancel: Cancel an active running query
 * - history: List all session summaries scoped to current user
 * - history_session: Retrieve full message thread for a specific session ID
 * - delete_session: Delete a specific session thread
 * - clear_history: Delete all session threads for current user
 */

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

  const isUser = msg.role === 'user';
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
    timestamp: timestamp,
    sessionId: msg.session_id || msg.sessionId,
  };
};

export const chatbotApi = {
  /**
   * Send a user message to the backend via POST /ask with action: "ask"
   * 
   * @param {Object} params
   * @param {string} params.question - The natural-language prompt
   * @param {string} params.sessionId - Chat session ID
   * @param {string} [params.requestId] - Custom identifier to track/cancel request
   * @param {AbortSignal} [params.signal] - AbortSignal for network request cancellation
   * @returns {Promise<Object>} Formatted assistant response message
   */
  sendChatMessage: async ({ question, sessionId, requestId, signal }) => {
    const baseUrl = getApiBaseUrl();
    const username = chatStorage.getStoredUsername();
    const reqId = requestId || `req_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;

    const payload = {
      action: 'ask',
      question: question,
      username: username,
      request_id: reqId,
      session_id: sessionId,
    };

    try {
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

      // Transform backend response to standardized assistant message
      return normalizeBackendMessage({
        id: `msg_bot_${Date.now()}`,
        role: 'assistant',
        content: data.content || data.message || (data.result?.length === 0 ? 'No records found matching your query.' : ''),
        sql: data.sql,
        result: data.result,
        tables: data.tables,
        summary: data.summary,
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
   * Cancel an active running query via POST /ask with action: "cancel"
   * 
   * @param {Object} params
   * @param {string} params.requestId - Identifier of the request to cancel
   * @returns {Promise<Object>} Cancellation status
   */
  cancelChatRequest: async ({ requestId }) => {
    if (!requestId) return { status: 'noop' };

    const baseUrl = getApiBaseUrl();
    const username = chatStorage.getStoredUsername();

    try {
      const response = await fetch(`${baseUrl}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: 'cancel',
          username: username,
          request_id: requestId,
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
   * Retrieve all session summaries for the current user via POST /ask with action: "history"
   * 
   * @returns {Promise<Array>} List of session summaries: [{ id, title, created_at, updated_at }]
   */
  getChatSessions: async () => {
    const baseUrl = getApiBaseUrl();
    const username = chatStorage.getStoredUsername();

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
        messages: [], // messages hydrated on demand via getSessionHistory
      }));
    } catch (err) {
      console.warn('Could not fetch sessions from backend, using local cache:', err.message);
      return null; // Return null so provider can fall back to localStorage
    }
  },

  /**
   * Retrieve the full message thread for a specific session ID via POST /ask with action: "history_session"
   * 
   * @param {string} sessionId
   * @returns {Promise<Object>} Session object with complete messages array
   */
  getSessionHistory: async (sessionId) => {
    if (!sessionId) return null;

    const baseUrl = getApiBaseUrl();
    const username = chatStorage.getStoredUsername();

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
   * Delete a specific session thread via POST /ask with action: "delete_session"
   * 
   * @param {string} sessionId
   * @returns {Promise<boolean>} Success indicator
   */
  deleteChatSession: async (sessionId) => {
    if (!sessionId) return false;

    const baseUrl = getApiBaseUrl();
    const username = chatStorage.getStoredUsername();

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
   * Clear all session histories for current user via POST /ask with action: "clear_history"
   * 
   * @returns {Promise<boolean>} Success indicator
   */
  clearAllHistory: async () => {
    const baseUrl = getApiBaseUrl();
    const username = chatStorage.getStoredUsername();

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
};

export default chatbotApi;
