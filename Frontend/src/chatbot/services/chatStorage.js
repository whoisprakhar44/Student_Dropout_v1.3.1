import { STORAGE_KEYS, VIEW_MODES } from '../constants/chatbotConstants';

/**
 * Storage Service for persisting chatbot state in localStorage.
 * Includes graceful fallbacks in case localStorage is unavailable or corrupted.
 */

export const chatStorage = {
  /**
   * Load saved chat sessions
   */
  getSessions: () => {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.SESSIONS);
      return data ? JSON.parse(data) : [];
    } catch (error) {
      console.warn('Failed to load chat sessions from localStorage:', error);
      return [];
    }
  },

  /**
   * Save chat sessions array
   */
  saveSessions: (sessions) => {
    try {
      localStorage.setItem(STORAGE_KEYS.SESSIONS, JSON.stringify(sessions));
    } catch (error) {
      console.warn('Failed to save chat sessions to localStorage:', error);
    }
  },

  /**
   * Get active session ID
   */
  getActiveSessionId: () => {
    try {
      return localStorage.getItem(STORAGE_KEYS.ACTIVE_SESSION_ID) || null;
    } catch (error) {
      console.warn('Failed to get active session ID:', error);
      return null;
    }
  },

  /**
   * Save active session ID
   */
  saveActiveSessionId: (sessionId) => {
    try {
      if (sessionId) {
        localStorage.setItem(STORAGE_KEYS.ACTIVE_SESSION_ID, sessionId);
      } else {
        localStorage.removeItem(STORAGE_KEYS.ACTIVE_SESSION_ID);
      }
    } catch (error) {
      console.warn('Failed to save active session ID:', error);
    }
  },

  /**
   * Get UI view mode ('closed' | 'mini' | 'fullscreen')
   */
  getViewMode: () => {
    try {
      const mode = localStorage.getItem(STORAGE_KEYS.VIEW_MODE);
      return Object.values(VIEW_MODES).includes(mode) ? mode : VIEW_MODES.CLOSED;
    } catch (error) {
      return VIEW_MODES.CLOSED;
    }
  },

  /**
   * Save UI view mode
   */
  saveViewMode: (mode) => {
    try {
      localStorage.setItem(STORAGE_KEYS.VIEW_MODE, mode);
    } catch (error) {
      console.warn('Failed to save view mode:', error);
    }
  },

  /**
   * Get unread badge count
   */
  getUnreadCount: () => {
    try {
      const val = localStorage.getItem(STORAGE_KEYS.UNREAD_COUNT);
      return val ? parseInt(val, 10) : 0;
    } catch (error) {
      return 0;
    }
  },

  /**
   * Save unread count
   */
  saveUnreadCount: (count) => {
    try {
      localStorage.setItem(STORAGE_KEYS.UNREAD_COUNT, count.toString());
    } catch (error) {
      console.warn('Failed to save unread count:', error);
    }
  },

  /**
   * Get suggestion layout ('horizontal' | 'vertical')
   */
  getSuggestionLayout: () => {
    try {
      const layout = localStorage.getItem(STORAGE_KEYS.SUGGESTION_LAYOUT);
      if (layout === 'horizontal' || layout === 'vertical') {
        return layout;
      }
      return null;
    } catch (error) {
      return null;
    }
  },

  /**
   * Save suggestion layout preference
   */
  saveSuggestionLayout: (layout) => {
    try {
      if (layout) {
        localStorage.setItem(STORAGE_KEYS.SUGGESTION_LAYOUT, layout);
      }
    } catch (error) {
      console.warn('Failed to save suggestion layout preference:', error);
    }
  },

  /**
   * Extract username from localStorage("userInfo") JSON, fallback to "Test User"
   */
  getStoredUsername: () => {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.USER_INFO);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.username === 'string' && parsed.username.trim()) {
          return parsed.username.trim();
        }
      }
    } catch (error) {
      console.warn('Failed to parse userInfo for username:', error);
    }
    return 'Test User';
  },

  /**
   * Extract authentication token from localStorage
   */
  getAuthToken: () => {
    try {
      // 1. Check inside userInfo JSON
      const rawUser = localStorage.getItem(STORAGE_KEYS.USER_INFO);
      if (rawUser) {
        try {
          const parsed = JSON.parse(rawUser);
          if (parsed && (parsed.token || parsed.accessToken || parsed.authToken || parsed.jwt)) {
            return parsed.token || parsed.accessToken || parsed.authToken || parsed.jwt;
          }
        } catch {
          // not JSON or no token field
        }
      }

      // 2. Direct token keys fallback
      return (
        localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN) ||
        localStorage.getItem('authToken') ||
        localStorage.getItem('accessToken') ||
        localStorage.getItem('jwt') ||
        'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJETF9ST0xFOCIsInVzZXJOYW1lIjoiIiwidXNlclJvbGUiOiI4IiwiZGVwdElkIjoiQWxsIiwiZGlzdElkIjoiQWxsIiwicGFzc3dvcmRzdGF0dXMiOiIxIiwianRpIjoiM0FGOEE5QzMtRjAzRi00MjNELTg2NEYtMUVGRjgiLCJleHAiOjE3ODgyNDgyOTEsImlzcyI6IllvdXJJc3N1ZXIiLCJhdWQiOiJZb3VyQXVkaWVuY2UifQ.-ZU92XAwtjsTYQVwgUGhlqKtU5CTqG_4mxjZ9rHepnI'
      );
    } catch (error) {
      console.warn('Failed to read auth token from storage:', error);
      return '';
    }
  },

  /**
   * Clear all chatbot storage data
   */
  clearAll: () => {
    try {
      Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key));
    } catch (error) {
      console.warn('Failed to clear chatbot localStorage:', error);
    }
  },
};
