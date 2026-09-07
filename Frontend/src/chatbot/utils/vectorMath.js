/**
 * Vector Mathematics & Semantic Similarity Utilities
 * 
 * Provides high-performance vector operations for calculating cosine similarity
 * between query embeddings and pre-computed question embeddings in the browser.
 */

/**
 * Calculates Euclidean (L2) norm of a vector
 * @param {Array<number>|Float32Array} vec 
 * @returns {number}
 */
export const vectorNorm = (vec) => {
  if (!vec || !vec.length) return 0;
  let sum = 0;
  for (let i = 0; i < vec.length; i++) {
    sum += vec[i] * vec[i];
  }
  return Math.sqrt(sum);
};

/**
 * Normalizes vector to unit length (L2 norm = 1.0)
 * @param {Array<number>|Float32Array} vec 
 * @returns {Float32Array}
 */
export const normalizeVector = (vec) => {
  if (!vec || !vec.length) return new Float32Array(0);
  const norm = vectorNorm(vec);
  const result = new Float32Array(vec.length);
  if (norm === 0) return result;
  for (let i = 0; i < vec.length; i++) {
    result[i] = vec[i] / norm;
  }
  return result;
};

/**
 * Computes Cosine Similarity between two vectors:
 * cos(u, v) = (u . v) / (||u|| * ||v||)
 * 
 * @param {Array<number>|Float32Array} vecA 
 * @param {Array<number>|Float32Array} vecB 
 * @returns {number} Value between -1.0 and 1.0 (clamped to 0..1 for similarity)
 */
export const cosineSimilarity = (vecA, vecB) => {
  if (!vecA || !vecB || vecA.length !== vecB.length || vecA.length === 0) {
    return 0;
  }

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < vecA.length; i++) {
    const a = vecA[i];
    const b = vecB[i];
    dotProduct += a * b;
    normA += a * a;
    normB += b * b;
  }

  if (normA === 0 || normB === 0) return 0;
  const sim = dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  return Math.max(0, Math.min(1, sim)); // clamp to [0, 1]
};

/**
 * Computes semantic similarity between user query and candidate item.
 * 
 * If a query embedding is available (e.g. from backend or client embedder),
 * computes exact 768-dim Cosine Similarity against the candidate's embedding.
 * 
 * If query embedding is pending / unavailable, computes an approximate semantic 
 * affinity using vocabulary overlap and topic/intent semantic clustering.
 * 
 * @param {string} queryText 
 * @param {Array<number>|Float32Array|null} queryEmbedding 
 * @param {Object} candidateItem 
 * @returns {number} Semantic score between 0.0 and 1.0
 */
export const computeSemanticSimilarity = (queryText, queryEmbedding, candidateItem) => {
  // 1. Direct 768-dim Vector Cosine Similarity
  if (queryEmbedding && Array.isArray(candidateItem.embedding) && candidateItem.embedding.length > 0) {
    return cosineSimilarity(queryEmbedding, candidateItem.embedding);
  }

  // 2. Fallback semantic overlap estimator (topic, intent, and semantic n-grams)
  const qTokens = (queryText || '').toLowerCase().split(/\s+/).filter(Boolean);
  const targetTokens = (candidateItem.question || '').toLowerCase().split(/\s+/).filter(Boolean);
  const intentTokens = (candidateItem.intent || '').toLowerCase().split(/[_-\s]+/).filter(Boolean);
  const topicTokens = (candidateItem.topic || '').toLowerCase().split(/[_-\s]+/).filter(Boolean);

  if (qTokens.length === 0 || targetTokens.length === 0) return 0;

  let semanticMatches = 0;
  qTokens.forEach((qToken) => {
    // Check against question tokens, intent, and topic
    const inTarget = targetTokens.some((t) => t.includes(qToken) || qToken.includes(t));
    const inIntent = intentTokens.some((t) => t.includes(qToken) || qToken.includes(t));
    const inTopic = topicTokens.some((t) => t.includes(qToken) || qToken.includes(t));

    if (inTarget) semanticMatches += 1.0;
    else if (inIntent) semanticMatches += 0.85;
    else if (inTopic) semanticMatches += 0.75;
  });

  return Math.min(1.0, semanticMatches / qTokens.length);
};
