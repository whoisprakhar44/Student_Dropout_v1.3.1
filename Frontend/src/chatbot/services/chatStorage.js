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
   * Parse and decode JSON Web Token (JWT) payload
   * Supports Bearer prefix and base64url encoding
   */
  parseJwtPayload: (token) => {
    if (!token || typeof token !== 'string') return null;
    try {
      const raw = token.replace(/^Bearer\s+/i, '').trim();
      const parts = raw.split('.');
      if (parts.length !== 3) return null;
      let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      while (base64.length % 4) {
        base64 += '=';
      }
      const jsonStr = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonStr);
    } catch {
      try {
        const raw = token.replace(/^Bearer\s+/i, '').trim();
        return JSON.parse(atob(raw.split('.')[1]));
      } catch {
        return null;
      }
    }
  },

  /**
   * Extract decoded JWT user claims from localStorage
   */
  getUserPayloadFromJwt: () => {
    try {
      const isCandidatePayload = (p) => {
        if (!p || typeof p !== 'object') return false;
        return Boolean(
          p.preferred_username ||
          p.userId ||
          p.sub ||
          p.cfms_id ||
          p.role ||
          p.userRole ||
          p.department ||
          p.dept_id ||
          p.userName !== undefined
        );
      };

      // 1. Check known token storage keys
      const candidateKeys = [
        'token',
        'jwt',
        'authToken',
        'accessToken',
        'auth_token',
        'bearer_token',
        STORAGE_KEYS.AUTH_TOKEN,
      ];

      for (const key of candidateKeys) {
        const val = localStorage.getItem(key);
        if (val && typeof val === 'string') {
          const payload = chatStorage.parseJwtPayload(val);
          if (payload && isCandidatePayload(payload)) {
            return payload;
          }
          try {
            const parsed = JSON.parse(val);
            if (parsed && typeof parsed === 'object') {
              if (isCandidatePayload(parsed)) {
                return parsed;
              }
              const innerToken = parsed.token || parsed.accessToken || parsed.authToken || parsed.jwt;
              if (innerToken) {
                const innerPayload = chatStorage.parseJwtPayload(innerToken);
                if (innerPayload && isCandidatePayload(innerPayload)) return innerPayload;
              }
            }
          } catch {}
        }
      }

      // 2. Check userInfo JSON object
      const userKeys = [STORAGE_KEYS.USER_INFO, 'user', 'currentUser', 'authUser', 'session'];
      for (const uk of userKeys) {
        const raw = localStorage.getItem(uk);
        if (raw) {
          const payload = chatStorage.parseJwtPayload(raw);
          if (payload && isCandidatePayload(payload)) return payload;

          try {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
              const innerTok = parsed.token || parsed.accessToken || parsed.authToken || parsed.jwt;
              if (innerTok) {
                const innerPayload = chatStorage.parseJwtPayload(innerTok);
                if (innerPayload && isCandidatePayload(innerPayload)) return innerPayload;
              }
              if (isCandidatePayload(parsed)) {
                return parsed;
              }
            }
          } catch {}
        }
      }

      // 3. Scan all keys in localStorage for any JWT string
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        const val = localStorage.getItem(k);
        if (val && typeof val === 'string' && val.includes('.')) {
          const payload = chatStorage.parseJwtPayload(val);
          if (payload && isCandidatePayload(payload)) {
            return payload;
          }
        }
      }

      // 4. Also scan sessionStorage if available
      if (typeof sessionStorage !== 'undefined') {
        for (let i = 0; i < sessionStorage.length; i++) {
          const k = sessionStorage.key(i);
          const val = sessionStorage.getItem(k);
          if (val && typeof val === 'string' && val.includes('.')) {
            const payload = chatStorage.parseJwtPayload(val);
            if (payload && isCandidatePayload(payload)) {
              return payload;
            }
          }
        }
      }

      // 5. Fallback to active auth token
      const fallbackTok = chatStorage.getAuthToken();
      if (fallbackTok) {
        const p = chatStorage.parseJwtPayload(fallbackTok);
        if (p && isCandidatePayload(p)) return p;
      }
    } catch (err) {
      console.warn('Failed to extract user payload from JWT:', err);
    }
    return null;
  },

  /**
   * Extract username from JWT payload saved in localStorage to use for backend APIs
   * Prioritizes preferred_username (prod token structure) -> userId -> cfms_id -> sub
   */
  getStoredUsername: () => {
    try {
      const payload = chatStorage.getUserPayloadFromJwt();
      if (payload) {
        // 1. Prod token structure: preferred_username is the username
        if (payload.preferred_username && typeof payload.preferred_username === 'string' && payload.preferred_username.trim()) {
          return payload.preferred_username.trim();
        }
        // 2. Dev/SSO structure: userId
        if (payload.userId && typeof payload.userId === 'string' && payload.userId.trim()) {
          return payload.userId.trim();
        }
        // 3. CFMS ID
        if (payload.cfms_id && typeof payload.cfms_id === 'string' && payload.cfms_id.trim()) {
          return payload.cfms_id.trim();
        }
        // 4. JWT sub
        if (payload.sub && typeof payload.sub === 'string' && payload.sub.trim() && payload.sub !== 'user') {
          return payload.sub.trim();
        }
      }

      // Direct storage keys
      const directPref = localStorage.getItem('preferred_username');
      if (directPref && typeof directPref === 'string' && directPref.trim()) {
        return directPref.trim();
      }

      const directId = localStorage.getItem('userId');
      if (directId && typeof directId === 'string' && directId.trim()) {
        return directId.trim();
      }

      const directUser = localStorage.getItem('username');
      if (directUser && typeof directUser === 'string' && directUser.trim() && directUser !== 'user') {
        return directUser.trim();
      }

      // Check inside userInfo JSON
      const raw = localStorage.getItem(STORAGE_KEYS.USER_INFO);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.preferred_username && typeof parsed.preferred_username === 'string' && parsed.preferred_username.trim()) {
          return parsed.preferred_username.trim();
        }
        if (parsed?.userId && typeof parsed.userId === 'string' && parsed.userId.trim()) {
          return parsed.userId.trim();
        }
        if (parsed?.username && typeof parsed.username === 'string' && parsed.username.trim() && parsed.username !== 'user') {
          return parsed.username.trim();
        }
      }

      // Fallback: userName if available
      if (payload && payload.userName && typeof payload.userName === 'string' && payload.userName.trim()) {
        return payload.userName.trim();
      }
    } catch (error) {
      console.warn('Failed to parse JWT for username:', error);
    }
    return 'user';
  },

  /**
   * Alias for getStoredUsername to explicitly denote userId retrieval
   */
  getUserId: () => {
    return chatStorage.getStoredUsername();
  },

  /**
   * Extract user display Name from JWT token:
   * Prioritizes preferred_username / userName -> userId / cfms_id
   */
  getUserDisplayName: () => {
    try {
      const payload = chatStorage.getUserPayloadFromJwt();
      if (payload) {
        if (payload.preferred_username && typeof payload.preferred_username === 'string' && payload.preferred_username.trim()) {
          return payload.preferred_username.trim();
        }
        if (payload.userName && typeof payload.userName === 'string' && payload.userName.trim()) {
          return payload.userName.trim();
        }
        if (payload.name && typeof payload.name === 'string' && payload.name.trim()) {
          return payload.name.trim();
        }
        if (payload.userId && typeof payload.userId === 'string' && payload.userId.trim()) {
          return payload.userId.trim();
        }
        if (payload.cfms_id && typeof payload.cfms_id === 'string' && payload.cfms_id.trim()) {
          return payload.cfms_id.trim();
        }
        if (payload.sub && typeof payload.sub === 'string' && payload.sub.trim() && payload.sub !== 'user') {
          return payload.sub.trim();
        }
      }

      const directName = localStorage.getItem('preferred_username') || localStorage.getItem('userName') || localStorage.getItem('name');
      if (directName && typeof directName === 'string' && directName.trim()) {
        return directName.trim();
      }

      const uid = chatStorage.getStoredUsername();
      if (uid && uid !== 'user') {
        return uid;
      }
    } catch (err) {
      console.warn('Failed to get user display name from JWT:', err);
    }
    return 'User';
  },

  /**
   * Extract user role from JWT token (supports 'role' in prod token or 'userRole')
   */
  getUserRole: () => {
    try {
      const payload = chatStorage.getUserPayloadFromJwt();
      if (payload) {
        if (payload.role !== undefined && payload.role !== null && String(payload.role).trim()) {
          return String(payload.role).trim();
        }
        if (payload.userRole !== undefined && payload.userRole !== null && String(payload.userRole).trim()) {
          return String(payload.userRole).trim();
        }
      }
    } catch {}
    return null;
  },

  /**
   * Extract user department from JWT token (supports 'department', 'dept_id', 'deptId')
   */
  getUserDepartment: () => {
    try {
      const payload = chatStorage.getUserPayloadFromJwt();
      if (payload) {
        return payload.department || payload.dept_id || payload.deptId || null;
      }
    } catch {}
    return null;
  },

  /**
   * Extract CFMS ID from JWT token
   */
  getCfmsId: () => {
    try {
      const payload = chatStorage.getUserPayloadFromJwt();
      if (payload) {
        return payload.cfms_id || null;
      }
    } catch {}
    return null;
  },

  /**
   * Save active username into localStorage
   */
  setStoredUsername: (username) => {
    try {
      if (username && typeof username === 'string') {
        localStorage.setItem('username', username.trim());
        localStorage.setItem('userId', username.trim());
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
        localStorage.getItem('token') ||
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
