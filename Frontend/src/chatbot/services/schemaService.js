/**
 * Canonical Schema Service Layer
 *
 * Implements client-side caching & API communication for the AP Citizen 360
 * canonical data model reference. Verifies server DB version metadata before
 * fetching to minimize network payloads and caches data in localStorage.
 */

import { STORAGE_KEYS } from '../constants/chatbotConstants';
import { chatStorage } from './chatStorage';

const getApiBaseUrl = () => {
  let url = (
    import.meta.env.VITE_CHATBOT_API_URL ||
    import.meta.env.VITE_SUGGESTIONS_API_BASE_URL ||
    'http://localhost:8000'
  ).trim();
  url = url.replace(/\/+$/, '');
  return url;
};

const getAskEndpoint = () => {
  const base = getApiBaseUrl();
  if (base.endsWith('/ask')) {
    return base;
  }
  return `${base}/ask`;
};

const DEFAULT_TOKEN =
  'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJETF9ST0xFOCIsInVzZXJOYW1lIjoiIiwidXNlclJvbGUiOiI4IiwiZGVwdElkIjoiQWxsIiwicGFzc3dvcmRzdGF0dXMiOiIxIiwianRpIjoiNkYzRDBERUMtMzA3QS00NTNBLTlEOUItQTQ2MTYiLCJleHAiOjE3ODcyOTQ1MzAsImlzcyI6IllvdXJJc3N1ZXIiLCJhdWQiOiJZb3VyQXVkaWVuY2UifQ.ZI9FpY3N2z5qvol86rBCGQJNjfJ6ftrEISOhFr7dEQo';

const getHeaders = () => {
  const token =
    localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN) ||
    localStorage.getItem('authToken') ||
    localStorage.getItem('accessToken') ||
    DEFAULT_TOKEN;

  return {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    Authorization: token.startsWith('Bearer ') ? token : `Bearer ${token}`
  };
};

// In-memory cache singleton
let inMemorySchema = null;

export const schemaService = {
  /**
   * Get cached schema from localStorage or memory if available
   */
  getLocalCachedSchema: () => {
    if (inMemorySchema) return inMemorySchema;

    try {
      const raw = localStorage.getItem(STORAGE_KEYS.SCHEMA_CACHE);
      if (raw) {
        const parsed = JSON.parse(raw);
        inMemorySchema = parsed;
        return parsed;
      }
    } catch (e) {
      console.warn('Failed to parse cached schema from localStorage:', e);
    }
    return null;
  },

  /**
   * Fetch latest schema metadata from server (version, updated_at, counts)
   */
  fetchServerMetadata: async () => {
    const askUrl = getAskEndpoint();
    const username = (chatStorage.getStoredUsername() || 'user').trim();
    try {
      const res = await fetch(askUrl, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ action: 'schema_meta', username })
      });

      if (res.ok) {
        return await res.json();
      }
      if (res.status === 403) {
        return { restricted: true };
      }
    } catch (err) {
      console.warn('POST /ask (schema_meta) failed, trying GET /api/schema/meta:', err);
    }

    // Fallback: dedicated GET endpoint
    try {
      const base = getApiBaseUrl().replace(/\/ask\/?$/, '');
      const res = await fetch(`${base}/api/schema/meta?username=${encodeURIComponent(username)}`, {
        method: 'GET',
        headers: getHeaders()
      });
      if (res.ok) {
        return await res.json();
      }
      if (res.status === 403) {
        return { restricted: true };
      }
    } catch (err) {
      console.warn('GET /api/schema/meta fallback failed:', err);
    }

    return null;
  },

  /**
   * Fetch full sanitized canonical schema definition from server
   */
  fetchServerSchema: async () => {
    const askUrl = getAskEndpoint();
    const username = (chatStorage.getStoredUsername() || 'user').trim();
    try {
      const res = await fetch(askUrl, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ action: 'canonical_schema', username })
      });

      if (res.ok) {
        const data = await res.json();
        return data;
      }
      if (res.status === 403) {
        return { restricted: true };
      }
    } catch (err) {
      console.warn('POST /ask (canonical_schema) failed, trying GET /api/schema:', err);
    }

    // Fallback: dedicated GET endpoint
    try {
      const base = getApiBaseUrl().replace(/\/ask\/?$/, '');
      const res = await fetch(`${base}/api/schema?username=${encodeURIComponent(username)}`, {
        method: 'GET',
        headers: getHeaders()
      });
      if (res.ok) {
        return await res.json();
      }
      if (res.status === 403) {
        return { restricted: true };
      }
    } catch (err) {
      console.error('GET /api/schema fallback failed:', err);
    }

    return null;
  },

  /**
   * Main entry: Retrieves canonical schema with intelligent version checking and local storage caching.
   * If local version matches server version, skips downloading full payload.
   */
  getOrUpdateCanonicalSchema: async (forceRefresh = false) => {
    const localCached = schemaService.getLocalCachedSchema();
    const localVersion = localStorage.getItem(STORAGE_KEYS.SCHEMA_VERSION);
    const localUpdatedAt = localStorage.getItem(STORAGE_KEYS.SCHEMA_UPDATED_AT);

    // If user's role does not allow About section according to SDUI, do not fetch
    const privs = chatStorage.getSduiPrivileges();
    if (privs?.showAboutSection === false) {
      return null;
    }

    // If we have cached schema and not forcing refresh, we can check server metadata
    try {
      const serverMeta = await schemaService.fetchServerMetadata();

      if (serverMeta?.restricted) {
        return null;
      }

      if (serverMeta && serverMeta.version) {
        const isUpToDate =
          !forceRefresh &&
          localCached &&
          localVersion === serverMeta.version &&
          (!serverMeta.updated_at || localUpdatedAt === serverMeta.updated_at);

        if (isUpToDate) {
          return localCached;
        }

        // Server version differs or no local cache -> fetch full sanitized schema
        const freshSchema = await schemaService.fetchServerSchema();
        if (freshSchema && freshSchema.groups) {
          inMemorySchema = freshSchema;
          try {
            localStorage.setItem(STORAGE_KEYS.SCHEMA_CACHE, JSON.stringify(freshSchema));
            localStorage.setItem(STORAGE_KEYS.SCHEMA_VERSION, serverMeta.version || freshSchema.version || '3.0.0');
            localStorage.setItem(
              STORAGE_KEYS.SCHEMA_UPDATED_AT,
              serverMeta.updated_at || freshSchema.effectiveDate || new Date().toISOString()
            );
          } catch (storageErr) {
            console.warn('Could not save schema to localStorage (quota exceeded?):', storageErr);
          }
          return freshSchema;
        }
      }
    } catch (err) {
      console.warn('Network error while checking schema metadata, using local cache if available:', err);
    }

    // If server check failed but we have local cache, return it
    if (localCached) {
      return localCached;
    }

    // Direct attempt to fetch full schema if metadata check was skipped/failed
    const fallbackFresh = await schemaService.fetchServerSchema();
    if (fallbackFresh) {
      inMemorySchema = fallbackFresh;
      try {
        localStorage.setItem(STORAGE_KEYS.SCHEMA_CACHE, JSON.stringify(fallbackFresh));
        if (fallbackFresh.version) {
          localStorage.setItem(STORAGE_KEYS.SCHEMA_VERSION, fallbackFresh.version);
        }
      } catch (e) {
        // ignore storage errors
      }
      return fallbackFresh;
    }

    return null;
  },

  /**
   * Clear local schema cache
   */
  clearCache: () => {
    inMemorySchema = null;
    localStorage.removeItem(STORAGE_KEYS.SCHEMA_CACHE);
    localStorage.removeItem(STORAGE_KEYS.SCHEMA_VERSION);
    localStorage.removeItem(STORAGE_KEYS.SCHEMA_UPDATED_AT);
  }
};

export default schemaService;
