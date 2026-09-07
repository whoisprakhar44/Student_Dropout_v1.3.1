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
    id: 'school_dropout_001',
    question:
      'Give me class 6 students in Anantapur who dropped out in 2025-26, including school and social category.',
    intent: 'student_risk_list',
    topic: 'dropout_tracking',
    embedding: new Array(768).fill(0).map((_, i) => Math.sin(i * 0.1))
  },
  {
    id: 'school_attendance_002',
    question:
      'Show monthly student attendance percentage by district for secondary schools.',
    intent: 'attendance_summary',
    topic: 'attendance_analytics',
    embedding: new Array(768).fill(0).map((_, i) => Math.cos(i * 0.1))
  },
  {
    id: 'teacher_pupil_ratio_003',
    question:
      'List government high schools with student-to-teacher ratio greater than 40:1.',
    intent: 'school_infrastructure',
    topic: 'staffing_analysis',
    embedding: new Array(768).fill(0).map((_, i) => Math.sin(i * 0.2))
  },
  {
    id: 'infra_drinking_water_004',
    question:
      'Which schools in Chittoor district lack functional drinking water facilities?',
    intent: 'infrastructure_audit',
    topic: 'school_facilities',
    embedding: new Array(768).fill(0).map((_, i) => Math.cos(i * 0.2))
  },
  {
    id: 'exam_pass_percentage_005',
    question:
      'Compare SSC board exam pass rates between rural and urban districts over the last 3 years.',
    intent: 'academic_performance',
    topic: 'examination_reports',
    embedding: new Array(768).fill(0).map((_, i) => Math.sin(i * 0.3))
  }
];

/**
 * API URL
 */
const getApiBaseUrl = () => {
  return import.meta.env.VITE_SUGGESTIONS_API_BASE_URL;
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
