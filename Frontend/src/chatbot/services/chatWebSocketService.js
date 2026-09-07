import { WS_CONNECTION_STATUS, PLANNER_STEPS } from '../constants/chatbotConstants';
import { chatStorage } from './chatStorage';

/**
 * Resolves the appropriate WebSocket URL from environment variables or falls back intelligently
 */
export const resolveWebSocketUrl = () => {
  const explicitWsUrl = import.meta.env?.VITE_CHATBOT_WS_URL;
  if (explicitWsUrl && typeof explicitWsUrl === 'string' && explicitWsUrl.trim().length > 0) {
    return explicitWsUrl.trim();
  }

  const apiUrl = import.meta.env?.VITE_CHATBOT_API_URL;
  if (apiUrl && typeof apiUrl === 'string' && apiUrl.trim().length > 0) {
    try {
      const parsed = new URL(apiUrl.trim());
      const wsProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
      
      // Replace /ask with /ws or append /ws
      let pathname = parsed.pathname || '/';
      if (pathname.endsWith('/ask') || pathname.endsWith('/ask/')) {
        pathname = pathname.replace(/\/ask\/?$/, '/ws');
      } else if (!pathname.endsWith('/ws')) {
        pathname = pathname.endsWith('/') ? `${pathname}ws` : `${pathname}/ws`;
      }
      return `${wsProtocol}//${parsed.host}${pathname}`;
    } catch {
      // If URL parsing fails, convert simple prefixes
      return apiUrl.replace(/^https?:\/\//i, (match) => (match.toLowerCase().startsWith('https') ? 'wss://' : 'ws://'));
    }
  }

  // Fallback local dev
  const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:';
  return isHttps ? 'wss://localhost:8000/ws' : 'ws://localhost:8000/ws';
};

class ChatWebSocketService {
  constructor() {
    this.ws = null;
    this.wsUrl = resolveWebSocketUrl();
    this.status = WS_CONNECTION_STATUS.DISCONNECTED;
    this.pendingRequests = new Map(); // requestId -> { resolve, reject, onProgress, timeoutId }
    this.statusListeners = new Set();
    this.progressListeners = new Set();
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 10000;
    this.pingIntervalId = null;
    this.isExplicitlyClosed = false;
    this.authHeaders = null;
  }

  /**
   * Subscribe to connection status transitions
   * @param {Function} callback (status: WS_CONNECTION_STATUS) => void
   * @returns {Function} Unsubscribe function
   */
  onStatusChange(callback) {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => this.statusListeners.delete(callback);
  }

  /**
   * Subscribe to all live planner progress stream events
   * @param {Function} callback (event: Object) => void
   * @returns {Function} Unsubscribe function
   */
  onPlannerProgress(callback) {
    this.progressListeners.add(callback);
    return () => this.progressListeners.delete(callback);
  }

  _setStatus(newStatus) {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((listener) => {
        try {
          listener(newStatus);
        } catch (e) {
          console.warn('[WS] Status listener error:', e);
        }
      });
    }
  }

  /**
   * Connect to WebSocket backend
   */
  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isExplicitlyClosed = false;
    this.wsUrl = resolveWebSocketUrl();
    this._setStatus(WS_CONNECTION_STATUS.CONNECTING);

    try {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this._setStatus(WS_CONNECTION_STATUS.CONNECTED);
        this._startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        this._handleIncomingMessage(event);
      };

      this.ws.onerror = (err) => {
        console.warn('[WS] Socket encounter error:', err);
        this._setStatus(WS_CONNECTION_STATUS.ERROR);
      };

      this.ws.onclose = (event) => {
        this._stopHeartbeat();
        this._setStatus(WS_CONNECTION_STATUS.DISCONNECTED);
        
        // Reject all pending requests on unexpected disconnect
        this.pendingRequests.forEach((entry, reqId) => {
          if (entry.timeoutId) clearTimeout(entry.timeoutId);
          entry.reject(new Error(`WebSocket disconnected unexpectedly (code: ${event.code})`));
        });
        this.pendingRequests.clear();

        if (!this.isExplicitlyClosed) {
          this._scheduleReconnect();
        }
      };
    } catch (err) {
      console.warn('[WS] Connection creation failed:', err);
      this._setStatus(WS_CONNECTION_STATUS.ERROR);
      this._scheduleReconnect();
    }
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.pingIntervalId = setInterval(() => {
      if (this.isConnected()) {
        try {
          this.ws.send(JSON.stringify({
            action: 'ws_ping',
            request_id: `ping_${Date.now()}`
          }));
        } catch (e) {
          console.warn('[WS] Ping failed:', e);
        }
      }
    }, 25000);
  }

  _stopHeartbeat() {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return;

    this.reconnectAttempts++;
    // Exponential backoff with jitter: 1s, 2s, 4s, ... max 10s
    const baseDelay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts - 1), this.maxReconnectDelay);
    const delay = baseDelay + Math.random() * 500;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.isExplicitlyClosed && !this.isConnected()) {
        this.connect();
      }
    }, delay);
  }

  /**
   * Disconnect cleanly
   */
  disconnect() {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this._stopHeartbeat();

    if (this.ws) {
      try {
        this.ws.close(1000, 'Client closed connection');
      } catch {
        // ignore
      }
      this.ws = null;
    }
    this._setStatus(WS_CONNECTION_STATUS.DISCONNECTED);
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Handle server-to-client frames
   */
  _handleIncomingMessage(event) {
    try {
      const msg = JSON.parse(event.data);
      if (!msg || typeof msg !== 'object') return;

      const { type, action, request_id, status, step, message, data, queue_position } = msg;

      // 1. Heartbeat Pong
      if (type === 'pong' || action === 'ws_ping' || action === 'ping') {
        return;
      }

      // 2. Real-time Status / Planner progress stream
      if (type === 'status') {
        const progressEvent = {
          requestId: request_id,
          action,
          status,
          step: step || status,
          message: message || '',
          queuePosition: queue_position,
          data: data || {},
          timestamp: new Date().toISOString(),
        };

        // Notify specific request progress callback
        if (request_id && this.pendingRequests.has(request_id)) {
          const entry = this.pendingRequests.get(request_id);
          if (typeof entry.onProgress === 'function') {
            entry.onProgress(progressEvent);
          }
        }

        // Notify global progress subscribers
        this.progressListeners.forEach((listener) => {
          try {
            listener(progressEvent);
          } catch (e) {
            console.warn('[WS] Progress listener error:', e);
          }
        });
        return;
      }

      // 3. Final Result Frame
      if (type === 'result') {
        if (request_id && this.pendingRequests.has(request_id)) {
          const entry = this.pendingRequests.get(request_id);
          if (entry.timeoutId) clearTimeout(entry.timeoutId);
          this.pendingRequests.delete(request_id);

          entry.resolve(msg);
        }
        return;
      }

      // 4. Error Frame
      if (type === 'error') {
        if (request_id && this.pendingRequests.has(request_id)) {
          const entry = this.pendingRequests.get(request_id);
          if (entry.timeoutId) clearTimeout(entry.timeoutId);
          this.pendingRequests.delete(request_id);

          entry.reject(new Error(msg.detail || msg.message || 'WebSocket request failed'));
        }
      }
    } catch (err) {
      console.error('[WS] Failed to parse message frame:', err, event.data);
    }
  }

  /**
   * Send action envelope over WebSocket with Promise resolution and AbortSignal support
   * 
   * @param {string} action - Action name (e.g. 'ws_ask', 'ws_history', 'ws_cancel')
   * @param {Object} payload - Parameters for action
   * @param {Object} [options]
   * @param {Function} [options.onProgress] - Live step callback
   * @param {AbortSignal} [options.signal] - Abort controller signal
   * @param {number} [options.timeoutMs] - Request timeout in milliseconds (default: 90000ms)
   * @returns {Promise<Object>} Server response frame
   */
  async sendAction(action, payload = {}, options = {}) {
    const { onProgress, signal, timeoutMs = 90000 } = options;

    if (!this.isConnected()) {
      // Attempt quick auto-connect
      this.connect();
      // Wait up to 3000ms for connection
      await new Promise((resolve, reject) => {
        let timer = null;
        const checkOpen = () => {
          if (this.isConnected()) {
            if (timer) clearTimeout(timer);
            resolve();
          }
        };

        if (this.isConnected()) {
          return resolve();
        }

        timer = setTimeout(() => {
          reject(new Error('WebSocket is not connected'));
        }, 3000);

        const unsub = this.onStatusChange((s) => {
          if (s === WS_CONNECTION_STATUS.CONNECTED) {
            unsub();
            if (timer) clearTimeout(timer);
            resolve();
          }
        });
      });
    }

    const requestId = payload.request_id || `req_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    const username = payload.username || chatStorage.getStoredUsername() || 'user';

    const frame = {
      action,
      ...payload,
      request_id: requestId,
      username,
    };

    return new Promise((resolve, reject) => {
      let timeoutId = null;

      if (timeoutMs > 0) {
        timeoutId = setTimeout(() => {
          if (this.pendingRequests.has(requestId)) {
            this.pendingRequests.delete(requestId);
            reject(new Error(`WebSocket request timed out after ${Math.round(timeoutMs / 1000)}s`));
          }
        }, timeoutMs);
      }

      // Handle abort signal
      if (signal) {
        if (signal.aborted) {
          if (timeoutId) clearTimeout(timeoutId);
          return reject(new Error('Query request was cancelled.'));
        }

        signal.addEventListener('abort', () => {
          if (this.pendingRequests.has(requestId)) {
            if (timeoutId) clearTimeout(timeoutId);
            this.pendingRequests.delete(requestId);
            // Proactively notify backend of cancellation
            this.sendAction('ws_cancel', { target_request_id: requestId }).catch(() => {});
            reject(new Error('Query request was cancelled.'));
          }
        }, { once: true });
      }

      this.pendingRequests.set(requestId, {
        resolve,
        reject,
        onProgress,
        timeoutId,
      });

      try {
        this.ws.send(JSON.stringify(frame));
      } catch (err) {
        if (timeoutId) clearTimeout(timeoutId);
        this.pendingRequests.delete(requestId);
        reject(err);
      }
    });
  }

  /**
   * Action Shorthand Helpers
   */
  ask({ question, sessionId, username, requestId, onProgress, signal }) {
    return this.sendAction('ws_ask', {
      question,
      session_id: sessionId,
      username,
      request_id: requestId,
    }, { onProgress, signal });
  }

  cancel(targetRequestId) {
    return this.sendAction('ws_cancel', {
      target_request_id: targetRequestId,
    });
  }

  getHistory(username) {
    return this.sendAction('ws_history', { username });
  }

  getSessionHistory(sessionId, username) {
    return this.sendAction('ws_history_session', { session_id: sessionId, username });
  }

  deleteSession(sessionId, username) {
    return this.sendAction('ws_delete_session', { session_id: sessionId, username });
  }

  clearAllHistory(username) {
    return this.sendAction('ws_clear_history', { username });
  }

  getSuggestions(limit = 50) {
    return this.sendAction('ws_suggestions', { limit });
  }

  getSuggestionsMeta() {
    return this.sendAction('ws_suggestions_meta', {});
  }

  renderChart(chartType, data) {
    return this.sendAction('ws_chart', { chart_type: chartType, data });
  }
}

export const chatWebSocketService = new ChatWebSocketService();
export default chatWebSocketService;
