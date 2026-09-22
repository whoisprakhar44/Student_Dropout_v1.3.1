/**
 * Suggestions Service Layer
 *
 * Implements client-side caching & API communication for question suggestions & embeddings.
 */

import { STORAGE_KEYS } from '../constants/chatbotConstants';
import { indexedDbService } from './indexedDbService';

/**
 * Fallback Suggestions
 */
const FALLBACK_SUGGESTIONS = [
  {
    id: '001',
    question: 'How many male and female citizens are in the BC social category?',
    intent: 'equity_risk_slice',
    topic: 'social_category',
    degree: '1',
    tables: 'ap_citizen360.dim_person',
    embedding: new Array(768).fill(0).map((_, i) => Math.sin(i * 0.1))
  },
  {
    id: '002',
    question: 'What are the top 5 event types recorded in the event details table?',
    intent: 'event_summary',
    topic: 'event_analytics',
    degree: '1',
    tables: 'ap_citizen360.fact_event_details',
    embedding: new Array(768).fill(0).map((_, i) => Math.cos(i * 0.1))
  },
  {
    id: '003',
    question: 'Calculate the total disbursed amount to the SC category across all schemes.',
    intent: 'scheme_disbursement',
    topic: 'welfare_finance',
    degree: '1',
    tables: 'ap_citizen360.fact_scheme_disbursement',
    embedding: new Array(768).fill(0).map((_, i) => Math.sin(i * 0.2))
  },
  {
    id: '004',
    question: 'Find the number of citizens residing in each district.',
    intent: 'demographic_distribution',
    topic: 'district_demographics',
    degree: '2',
    tables: 'ap_citizen360.dim_person, ap_citizen360.dim_district',
    embedding: new Array(768).fill(0).map((_, i) => Math.cos(i * 0.2))
  },
  {
    id: '005',
    question: 'What is the total annual benefit for active enrollments grouped by scheme name?',
    intent: 'scheme_benefit_analysis',
    topic: 'entitlements',
    degree: '2',
    tables: 'ap_citizen360.fact_entitlement, ap_citizen360.dim_scheme',
    embedding: new Array(768).fill(0).map((_, i) => Math.sin(i * 0.3))
  }
];

/**
 * API URL
 */
const getApiBaseUrl = () => {
  if (import.meta.env.VITE_SUGGESTIONS_API_BASE_URL) {
    return import.meta.env.VITE_SUGGESTIONS_API_BASE_URL;
  }
  const apiBase = import.meta.env.VITE_CHATBOT_API_URL || 'http://localhost:8000';
  return `${apiBase}/suggestions`;
};

const DEFAULT_TOKEN =
  'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJETF9ST0xFOCIsInVzZXJOYW1lIjoiIiwidXNlclJvbGUiOiI4IiwiZGVwdElkIjoiQWxsIiwiZGlzdElkIjoiQWxsIiwicGFzc3dvcmRzdGF0dXMiOiIxIiwianRpIjoiNkYzRDBERUMtMzA3QS00NTNBLTlEOUItQTQ2MTYiLCJleHAiOjE3ODcyOTQ1MzAsImlzcyI6IllvdXJJc3N1ZXIiLCJhdWQiOiJZb3VyQXVkaWVuY2UifQ.ZI9FpY3N2z5qvol86rBCGQJNjfJ6ftrEISOhFr7dEQo';

/**
 * Dynamic headers
 */
const getHeaders = () => {
  const token =
    localStorage.getItem('token') ||
    localStorage.getItem('authToken') ||
    localStorage.getItem('accessToken') ||
    DEFAULT_TOKEN;

  return {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    Authorization: token.startsWith('Bearer ')
      ? token
      : `Bearer ${token}`
  };
};

/**
 * Memory Cache
 */
let inMemorySuggestionsCache = [];

export const suggestionsService = {
  getCachedSuggestions: async () => {
    if (inMemorySuggestionsCache.length > 0) {
      return inMemorySuggestionsCache;
    }

    try {
      const suggestions = await indexedDbService.getAllSuggestions();

      if (suggestions?.length) {
        inMemorySuggestionsCache = suggestions;
        return suggestions;
      }
    } catch (err) {
      console.warn('IndexedDB read failed:', err);
    }

    try {
      const raw = localStorage.getItem(
        STORAGE_KEYS.SUGGESTIONS_CACHE
      );

      if (raw) {
        const parsed = JSON.parse(raw);
        inMemorySuggestionsCache = parsed;
        return parsed;
      }
    } catch (err) {
      console.warn('localStorage read failed:', err);
    }

    return [];
  },

  getCachedUpdatedAt: async () => {
    try {
      const timestamp = await indexedDbService.getUpdatedAt();

      if (timestamp) {
        return timestamp;
      }
    } catch (err) {
      console.warn(err);
    }

    return (
      localStorage.getItem(
        STORAGE_KEYS.SUGGESTIONS_UPDATED_AT
      ) || null
    );
  },

  saveSuggestionsCache: async (
    suggestions,
    updatedAt
  ) => {
    try {
      const cleaned = suggestions
        .map((item, index) => ({
          id: item.id || `sug_${index}`,
          question:
            item.question ||
            item.text ||
            item.title ||
            '',
          intent: item.intent || '',
          topic: item.topic || '',
          use_case: item.use_case || '',
          difficulty: item.difficulty || '',
          embedding: Array.isArray(item.embedding)
            ? item.embedding
            : []
        }))
        .filter(
          item =>
            item.question &&
            item.question.trim().length > 0
        );

      inMemorySuggestionsCache = cleaned;

      await indexedDbService.saveSuggestions(
        cleaned,
        updatedAt
      );

      const textOnly = cleaned.map(
        ({ embedding, ...rest }) => rest
      );

      localStorage.setItem(
        STORAGE_KEYS.SUGGESTIONS_CACHE,
        JSON.stringify(textOnly)
      );

      if (updatedAt) {
        localStorage.setItem(
          STORAGE_KEYS.SUGGESTIONS_UPDATED_AT,
          updatedAt
        );
      }
    } catch (err) {
      console.warn(
        'Failed saving suggestions cache:',
        err
      );
    }
  },

  isSuggestionsDisabled: () => {
    return (
      localStorage.getItem(
        STORAGE_KEYS.SUGGESTIONS_DISABLED
      ) === 'true'
    );
  },

  setSuggestionsDisabled: disabled => {
    localStorage.setItem(
      STORAGE_KEYS.SUGGESTIONS_DISABLED,
      disabled ? 'true' : 'false'
    );
  },

  loadSuggestions: async () => {
    const baseUrl = getApiBaseUrl();

    const cachedItems =
      await suggestionsService.getCachedSuggestions();

    const cachedUpdatedAt =
      await suggestionsService.getCachedUpdatedAt();

    try {
      /**
       * STEP 1
       * CHECK UPDATED_AT
       */
      const metaRes = await fetch(baseUrl, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          action: 'suggestions_meta'
        })
      });

      if (!metaRes.ok) {
        throw new Error(
          `Meta API failed: ${metaRes.status}`
        );
      }

      const metaData = await metaRes.json();

      const serverUpdatedAt =
        metaData?.updated_at;

      /**
       * STEP 2
       * CACHE HIT
       */
      if (
        cachedItems.length > 0 &&
        cachedUpdatedAt &&
        cachedUpdatedAt === serverUpdatedAt
      ) {
        return cachedItems;
      }

      /**
       * STEP 3
       * FETCH FULL SUGGESTIONS
       */
      const fullRes = await fetch(baseUrl, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          action: 'suggestions',
          limit: -1
        })
      });

      if (!fullRes.ok) {
        throw new Error(
          `Suggestions API failed: ${fullRes.status}`
        );
      }

      const fullData =
        await fullRes.json();

      const items =
        fullData?.suggestions ||
        fullData?.fewshots ||
        fullData?.data ||
        fullData?.result ||
        [];

      if (
        Array.isArray(items) &&
        items.length > 0
      ) {
        await suggestionsService.saveSuggestionsCache(
          items,
          serverUpdatedAt ||
          fullData?.updated_at ||
          new Date().toISOString()
        );

        return await suggestionsService.getCachedSuggestions();
      }
    } catch (error) {
      console.error(
        'Suggestions API Error:',
        error
      );
    }

    /**
     * STEP 4
     * FALLBACK TO CACHE
     */
    if (cachedItems.length > 0) {
      return cachedItems;
    }

    /**
     * STEP 5
     * FALLBACK MOCK DATA
     */
    await suggestionsService.saveSuggestionsCache(
      FALLBACK_SUGGESTIONS,
      new Date().toISOString()
    );

    return FALLBACK_SUGGESTIONS;
  }
};

export default suggestionsService;
