/**
 * IndexedDB Storage Helper for Chatbot Suggestions & High-Dimensional Vectors
 * 
 * Stores suggestion objects containing 768-dimensional float embeddings
 * without stringification overhead or localStorage quota limits (up to hundreds of MBs).
 */

const DB_NAME = 'ChatbotSuggestionsDB';
const DB_VERSION = 1;
const STORE_NAME = 'suggestions_store';
const META_STORE = 'meta_store';

const openDB = () => {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      reject(new Error('IndexedDB not supported'));
      return;
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains(META_STORE)) {
        db.createObjectStore(META_STORE, { keyPath: 'key' });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
};

export const indexedDbService = {
  /**
   * Save array of suggestions (including 768-dim float embeddings)
   * @param {Array<Object>} suggestions
   * @param {string} updatedAt
   */
  saveSuggestions: async (suggestions, updatedAt) => {
    try {
      const db = await openDB();
      const tx = db.transaction([STORE_NAME, META_STORE], 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const metaStore = tx.objectStore(META_STORE);

      // Clear existing records before saving new dataset
      store.clear();

      suggestions.forEach((item) => {
        store.put(item);
      });

      if (updatedAt) {
        metaStore.put({ key: 'updated_at', value: updatedAt });
      }

      return new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => reject(tx.error);
      });
    } catch (err) {
      console.warn('IndexedDB saveSuggestions failed:', err);
      return false;
    }
  },

  /**
   * Retrieve all suggestions with vector embeddings
   * @returns {Promise<Array<Object>>}
   */
  getAllSuggestions: async () => {
    try {
      const db = await openDB();
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const request = store.getAll();

      return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result || []);
        request.onerror = () => reject(request.error);
      });
    } catch (err) {
      console.warn('IndexedDB getAllSuggestions failed:', err);
      return [];
    }
  },

  /**
   * Get cached updated_at timestamp from metadata store
   * @returns {Promise<string|null>}
   */
  getUpdatedAt: async () => {
    try {
      const db = await openDB();
      const tx = db.transaction(META_STORE, 'readonly');
      const metaStore = tx.objectStore(META_STORE);
      const request = metaStore.get('updated_at');

      return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result?.value || null);
        request.onerror = () => reject(request.error);
      });
    } catch (err) {
      return null;
    }
  }
};
