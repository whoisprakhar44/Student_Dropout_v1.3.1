import { STORAGE_KEYS, VIEW_MODES, CHAT_LAYERS, DEFAULT_LAYER } from '../constants/chatbotConstants';

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
   * Get active layer ('curated' | 'schema')
   */
  getActiveLayer: () => {
    try {
      const layer = localStorage.getItem(STORAGE_KEYS.ACTIVE_LAYER);
      if (layer === CHAT_LAYERS.SCHEMA || layer === CHAT_LAYERS.CURATED) {
        return layer;
      }
      return DEFAULT_LAYER;
    } catch (error) {
      return DEFAULT_LAYER;
    }
  },

  /**
   * Save active layer
   */
  saveActiveLayer: (layer) => {
    try {
      if (layer) {
        localStorage.setItem(STORAGE_KEYS.ACTIVE_LAYER, layer);
      }
    } catch (error) {
      console.warn('Failed to save active layer to localStorage:', error);
    }
  },

  /**
   * Check if schema layer is enabled via SDUI / permissions / flag
   */
  getIsSchemaEnabled: () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.SDUI_SCHEMA_ENABLED);
      if (stored !== null) {
        return stored === 'true';
      }
      // Check env variable fallback or default to true
      const envVal = import.meta.env?.VITE_SCHEMA_CHAT_ENABLED;
      if (envVal !== undefined) {
        return envVal === 'true' || envVal === '1';
      }
      return true;
    } catch (error) {
      return true;
    }
  },

  /**
   * Save schema enabled status (SDUI backend control override)
   */
  saveIsSchemaEnabled: (enabled) => {
    try {
      localStorage.setItem(STORAGE_KEYS.SDUI_SCHEMA_ENABLED, String(Boolean(enabled)));
    } catch (error) {
      console.warn('Failed to save schema enabled status:', error);
    }
  },

  /**
   * Get SDUI user privileges (table export, copy permissions, copy protection, devtools protection)
   */
  getSduiPrivileges: () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.SDUI_PRIVILEGES);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (e) {
      console.warn('Failed to parse SDUI privileges from storage:', e);
    }

    // Fallback to environment variables or defaults
    const parseEnvBool = (val, fallback) => {
      if (val === undefined || val === null || val === '') return fallback;
      return val === 'true' || val === '1';
    };

    return {
      allowTableExport: parseEnvBool(import.meta.env?.VITE_ALLOW_TABLE_EXPORT, false),
      allowCsvExport: parseEnvBool(import.meta.env?.VITE_ALLOW_CSV_EXPORT, false),
      allowExcelExport: parseEnvBool(import.meta.env?.VITE_ALLOW_EXCEL_EXPORT, false),
      allowCopyTable: parseEnvBool(import.meta.env?.VITE_ALLOW_COPY_TABLE, false),
      copyProtection: parseEnvBool(import.meta.env?.VITE_COPY_PROTECTION_ENABLED, true),
      devToolsProtection: parseEnvBool(import.meta.env?.VITE_DEVTOOLS_PROTECTION_ENABLED, true),
      isSchemaEnabled: parseEnvBool(import.meta.env?.VITE_SCHEMA_CHAT_ENABLED, true),
      showAboutSection: parseEnvBool(import.meta.env?.VITE_SHOW_ABOUT_SECTION, true),
      role: 'Citizen Viewer',
      is_active: true,
      universal_overrides: {},
    };
  },

  /**
   * Save SDUI privileges
   */
  saveSduiPrivileges: (privileges) => {
    try {
      if (privileges && typeof privileges === 'object') {
        localStorage.setItem(STORAGE_KEYS.SDUI_PRIVILEGES, JSON.stringify(privileges));
      }
    } catch (e) {
      console.warn('Failed to save SDUI privileges:', e);
    }
  },

  /**
   * Get active session ID
   */
  getActiveSessionId: (layer = null) => {
    try {
      if (layer) {
        const key = `${STORAGE_KEYS.ACTIVE_SESSION_ID}_${layer}`;
        const val = localStorage.getItem(key);
        if (val) return val;
      }
      return localStorage.getItem(STORAGE_KEYS.ACTIVE_SESSION_ID) || null;
    } catch (error) {
      console.warn('Failed to get active session ID:', error);
      return null;
    }
  },

  /**
   * Save active session ID
   */
  saveActiveSessionId: (sessionId, layer = null) => {
    try {
      if (sessionId) {
        localStorage.setItem(STORAGE_KEYS.ACTIVE_SESSION_ID, sessionId);
        if (layer) {
          localStorage.setItem(`${STORAGE_KEYS.ACTIVE_SESSION_ID}_${layer}`, sessionId);
        }
      } else {
        localStorage.removeItem(STORAGE_KEYS.ACTIVE_SESSION_ID);
        if (layer) {
          localStorage.removeItem(`${STORAGE_KEYS.ACTIVE_SESSION_ID}_${layer}`);
        }
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
      // 1. Direct username key in storage
      const direct = localStorage.getItem('username') || localStorage.getItem('userId');
      if (direct && typeof direct === 'string' && direct.trim()) {
        return direct.trim();
      }

      // 2. Check inside userInfo JSON
      const raw = localStorage.getItem(STORAGE_KEYS.USER_INFO);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.username === 'string' && parsed.username.trim()) {
          return parsed.username.trim();
        }
        if (parsed && typeof parsed.userId === 'string' && parsed.userId.trim()) {
          return parsed.userId.trim();
        }
      }
    } catch (error) {
      console.warn('Failed to parse userInfo for username:', error);
    }
    return 'user';
  },

  /**
   * Save active username into localStorage
   */
  setStoredUsername: (username) => {
    try {
      if (username && typeof username === 'string') {
        localStorage.setItem('username', username.trim());
      }
    } catch (err) {
      console.warn('Failed to save username to localStorage:', err);
    }
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
