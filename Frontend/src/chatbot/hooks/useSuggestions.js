import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { suggestionsService } from '../services/suggestionsService';
import { computeSemanticSimilarity } from '../utils/vectorMath';
import { SUGGESTION_DEFAULTS, SUGGESTION_LAYOUTS } from '../constants/chatbotConstants';

/**
 * Custom hook for managing client-side suggestions:
 * - Loads / hydrates suggestions + vector embeddings from cache on mount
 * - 2-second debounce timer on user typing
 * - Minimum 3 characters to trigger scoring
 * - Weighted ranking giving importance to both semantics and lexical matching:
 *     Composite = (semanticScore * semanticWeight) + 
 *                 (prefixScore * prefixWeight) + 
 *                 (substringScore * substringWeight) + 
 *                 (tokenScore * tokenWeight)
 * - Supports horizontal & vertical layouts from env variables
 * - Supports toggling/disabling suggestions
 * 
 * @param {string} currentInput - Current text in the chat input
 * @returns {Object} suggestions state & control handlers
 */
export const useSuggestions = (currentInput = '', isGloballyDisabled = null) => {
  const [allSuggestions, setAllSuggestions] = useState([]);
  const [rankedSuggestions, setRankedSuggestions] = useState([]);
  const [isScoring, setIsScoring] = useState(false);
  const [isDisabled, setIsDisabled] = useState(() => {
    if (typeof isGloballyDisabled === 'boolean') {
      return isGloballyDisabled;
    }
    return suggestionsService.isSuggestionsDisabled();
  });
  const debounceTimerRef = useRef(null);

  // Synchronize immediately if isGloballyDisabled changes
  useEffect(() => {
    if (typeof isGloballyDisabled === 'boolean') {
      setIsDisabled(isGloballyDisabled);
      if (isGloballyDisabled) {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
        setRankedSuggestions([]);
        setIsScoring(false);
      }
    }
  }, [isGloballyDisabled]);

  // Read environment variable configurations with fallbacks
  const layout = (import.meta.env?.VITE_SUGGESTION_LAYOUT || SUGGESTION_DEFAULTS.LAYOUT).toLowerCase();
  const debounceMs = Number(import.meta.env?.VITE_SUGGESTION_DEBOUNCE_MS ?? SUGGESTION_DEFAULTS.DEBOUNCE_MS);
  const minChars = Number(import.meta.env?.VITE_SUGGESTION_MIN_CHARS ?? SUGGESTION_DEFAULTS.MIN_CHARS);
  const maxItems = Number(import.meta.env?.VITE_SUGGESTION_MAX_ITEMS ?? SUGGESTION_DEFAULTS.MAX_ITEMS);

  const prefixWeight = Number(import.meta.env?.VITE_SUGGESTION_PREFIX_WEIGHT ?? SUGGESTION_DEFAULTS.PREFIX_WEIGHT);
  const substringWeight = Number(import.meta.env?.VITE_SUGGESTION_SUBSTRING_WEIGHT ?? SUGGESTION_DEFAULTS.SUBSTRING_WEIGHT);
  const tokenWeight = Number(import.meta.env?.VITE_SUGGESTION_TOKEN_WEIGHT ?? SUGGESTION_DEFAULTS.TOKEN_WEIGHT);
  const semanticWeight = Number(import.meta.env?.VITE_SUGGESTION_SEMANTIC_WEIGHT ?? SUGGESTION_DEFAULTS.SEMANTIC_WEIGHT);

  // 1. Initial Load of suggestions + vector embeddings on mount
  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      const items = await suggestionsService.loadSuggestions();
      if (isMounted && Array.isArray(items)) {
        setAllSuggestions(items);
      }
    };
    init();
    return () => {
      isMounted = false;
    };
  }, []);

  /**
   * Scoring Algorithm:
   * Evaluates semantic similarity (using vector embeddings/semantic space)
   * alongside prefix, substring, and token overlap matches.
   */
  const scoreSuggestion = useCallback((query, suggestion, queryEmbedding = null) => {
    const rawQuestion = suggestion.question || '';
    const qLower = query.toLowerCase().trim();
    const sLower = rawQuestion.toLowerCase();

    if (!qLower || !sLower) return 0;

    // A. Vector Semantic Similarity (Cosine Similarity with 768-dim float vector)
    const semanticScore = computeSemanticSimilarity(qLower, queryEmbedding, suggestion);

    // B. Prefix Match (Sentence prefix or start of any word)
    let prefixScore = 0;
    if (sLower.startsWith(qLower)) {
      prefixScore = 1.0;
    } else {
      const words = sLower.split(/\s+/);
      const wordPrefixMatch = words.some(w => w.startsWith(qLower));
      if (wordPrefixMatch) {
        prefixScore = 0.75;
      }
    }

    // C. Substring Match
    let substringScore = 0;
    if (sLower.includes(qLower)) {
      const idx = sLower.indexOf(qLower);
      substringScore = Math.max(0.2, 1.0 - (idx / Math.max(sLower.length, 1)));
    }

    // D. Token Overlap
    let tokenScore = 0;
    const queryTokens = qLower.split(/\s+/).filter(t => t.length > 0);
    const suggestionTokens = sLower.split(/\s+/).filter(t => t.length > 0);

    if (queryTokens.length > 0) {
      let matchedTokens = 0;
      queryTokens.forEach(qToken => {
        if (suggestionTokens.some(sToken => sToken.includes(qToken) || qToken.includes(sToken))) {
          matchedTokens++;
        }
      });
      tokenScore = matchedTokens / queryTokens.length;
    }

    // Weighted composite score giving importance to semantics + lexical matching
    const compositeScore = 
      (semanticScore * semanticWeight) +
      (prefixScore * prefixWeight) +
      (substringScore * substringWeight) +
      (tokenScore * tokenWeight);

    return compositeScore;
  }, [semanticWeight, prefixWeight, substringWeight, tokenWeight]);

  // 2. Debounced Real-time Ranking on user input (pausing for 2s with >= 3 chars)
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    const trimmedInput = (currentInput || '').trim();

    if (isDisabled || trimmedInput.length < minChars || allSuggestions.length === 0) {
      setRankedSuggestions([]);
      setIsScoring(false);
      return;
    }

    setIsScoring(true);

    debounceTimerRef.current = setTimeout(async () => {
      // Check if backend can return an embedding vector for the query
      let queryEmbedding = null;
      try {
        queryEmbedding = await suggestionsService.fetchQueryEmbedding(trimmedInput);
      } catch {
        // Fallback to local semantic similarity estimator
      }

      // Compute composite scores including vector semantics
      const scored = allSuggestions
        .map(item => ({
          ...item,
          score: scoreSuggestion(trimmedInput, item, queryEmbedding),
        }))
        .filter(item => item.score > 0.25)
        .sort((a, b) => b.score - a.score)
        .slice(0, maxItems);

      setRankedSuggestions(scored);
      setIsScoring(false);
    }, debounceMs);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [currentInput, allSuggestions, isDisabled, minChars, maxItems, debounceMs, scoreSuggestion]);

  // Toggle suggestions visibility/disabled state
  const toggleDisabled = useCallback(() => {
    setIsDisabled(prev => {
      const next = !prev;
      suggestionsService.setSuggestionsDisabled(next);
      if (next) {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
        setRankedSuggestions([]);
        setIsScoring(false);
      }
      return next;
    });
  }, []);

  const hideSuggestions = useCallback(() => {
    setRankedSuggestions([]);
  }, []);

  return {
    suggestions: rankedSuggestions,
    allSuggestionsCount: allSuggestions.length,
    isScoring,
    isDisabled,
    layout: layout === SUGGESTION_LAYOUTS.VERTICAL ? SUGGESTION_LAYOUTS.VERTICAL : SUGGESTION_LAYOUTS.HORIZONTAL,
    toggleDisabled,
    hideSuggestions,
  };
};

export default useSuggestions;
