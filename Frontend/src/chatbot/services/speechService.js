/**
 * Cross-Browser Speech Synthesis (TTS) Service Layer
 * Powered by EasySpeech (https://leaonline.github.io/easy-speech/)
 *
 * Provides cross-browser speech synthesis, voice pack discovery,
 * speed/rate controls, auto-play summary triggers, and state management.
 */

import EasySpeech from 'easy-speech';
import { STORAGE_KEYS } from '../constants/chatbotConstants';

// Helper to sanitize markdown and formatting tokens for natural speech
export const cleanTextForSpeech = (rawText = '') => {
  if (!rawText || typeof rawText !== 'string') return '';

  return rawText
    // Remove fenced code blocks ```sql ... ```
    .replace(/```[\s\S]*?```/g, ' ')
    // Remove inline code backticks `code`
    .replace(/`([^`]+)`/g, '$1')
    // Remove markdown links [text](url) -> text
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
    // Remove bold/italic asterisks: **text** or *text* -> text
    .replace(/\*{1,3}(.*?)\*{1,3}/g, '$1')
    // Remove bold/italic underscores: __text__ or _text_ -> text
    .replace(/_{1,3}(.*?)_{1,3}/g, '$1')
    // Remove strikethrough ~~text~~
    .replace(/~~(.*?)~~/g, '$1')
    // Remove headers (#, ##, ###)
    .replace(/^#{1,6}\s+/gm, '')
    // Remove list markers (*, -, •, 1.)
    .replace(/^[\*\-•]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    // Remove blockquotes (>)
    .replace(/^>\s+/gm, '')
    // Replace multiple spaces and newlines
    .replace(/\s+/g, ' ')
    .trim();
};

class SpeechService {
  constructor() {
    this.initialized = false;
    this.supported = false;
    this.voices = [];
    this.speakingMessageId = null;
    this.isSpeaking = false;
    this.listeners = new Set();

    // Default settings with env and localStorage persistence
    const defaultAutoPlayEnv =
      import.meta.env.VITE_TTS_AUTO_PLAY === 'true';
    const defaultRateEnv =
      Number(import.meta.env.VITE_TTS_DEFAULT_RATE) || 1.0;

    this.autoPlay =
      localStorage.getItem(STORAGE_KEYS.TTS_AUTO_PLAY) !== null
        ? localStorage.getItem(STORAGE_KEYS.TTS_AUTO_PLAY) === 'true'
        : defaultAutoPlayEnv;

    this.rate =
      Number(localStorage.getItem(STORAGE_KEYS.TTS_RATE)) || defaultRateEnv;

    this.selectedVoiceURI =
      localStorage.getItem(STORAGE_KEYS.TTS_VOICE) || null;

    // Trigger async initialization
    this.init();
  }

  async init() {
    if (this.initialized) return this.supported;

    try {
      if (typeof window === 'undefined') {
        this.supported = false;
        return false;
      }

      // Initialize EasySpeech engine with timeout and interval
      const initSuccess = await EasySpeech.init({
        maxTimeout: 5000,
        interval: 200
      });

      if (initSuccess) {
        this.supported = true;
        this.voices = EasySpeech.voices() || [];
        this.initialized = true;

        // Auto-select preferred voice if none selected
        if (!this.selectedVoiceURI && this.voices.length > 0) {
          // Prefer English (en-US / en-IN / en-GB) if available
          const preferred =
            this.voices.find((v) => v.lang?.startsWith('en-IN')) ||
            this.voices.find((v) => v.lang?.startsWith('en-US')) ||
            this.voices.find((v) => v.lang?.startsWith('en')) ||
            this.voices[0];
          if (preferred) {
            this.selectedVoiceURI = preferred.voiceURI || preferred.name;
          }
        }

        // Listen for async voice list updates from browser
        if (typeof window.speechSynthesis !== 'undefined') {
          window.speechSynthesis.onvoiceschanged = () => {
            this.voices = EasySpeech.voices() || [];
            this.notifyListeners();
          };
        }
      } else {
        this.supported = false;
      }
    } catch (err) {
      console.warn('EasySpeech initialization skipped or failed:', err);
      this.supported = false;
    }

    this.notifyListeners();
    return this.supported;
  }

  // Subscribe to voice or speaking state changes
  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notifyListeners() {
    this.listeners.forEach((cb) => {
      try {
        cb(this.getState());
      } catch (e) {
        console.error(e);
      }
    });
  }

  getState() {
    return {
      supported: this.supported && this.voices.length > 0,
      initialized: this.initialized,
      voices: this.voices,
      selectedVoiceURI: this.selectedVoiceURI,
      rate: this.rate,
      autoPlay: this.autoPlay,
      speakingMessageId: this.speakingMessageId,
      isSpeaking: this.isSpeaking
    };
  }

  isAvailable() {
    return Boolean(this.supported && this.voices && this.voices.length > 0);
  }

  getVoices() {
    return this.voices || [];
  }

  getSelectedVoice() {
    if (!this.voices || this.voices.length === 0) return null;
    if (this.selectedVoiceURI) {
      return (
        this.voices.find(
          (v) => (v.voiceURI || v.name) === this.selectedVoiceURI
        ) || this.voices[0]
      );
    }
    return this.voices[0];
  }

  setVoice(voiceURI) {
    this.selectedVoiceURI = voiceURI;
    if (voiceURI) {
      localStorage.setItem(STORAGE_KEYS.TTS_VOICE, voiceURI);
    } else {
      localStorage.removeItem(STORAGE_KEYS.TTS_VOICE);
    }
    this.notifyListeners();
  }

  setRate(rate) {
    const validRate = Math.max(0.5, Math.min(2.0, Number(rate) || 1.0));
    this.rate = validRate;
    localStorage.setItem(STORAGE_KEYS.TTS_RATE, String(validRate));
    this.notifyListeners();
  }

  setAutoPlay(enabled) {
    const val = Boolean(enabled);
    this.autoPlay = val;
    localStorage.setItem(STORAGE_KEYS.TTS_AUTO_PLAY, String(val));
    this.notifyListeners();
  }

  async speak(text, messageId = null) {
    if (!text || !this.isAvailable()) return;

    // Toggle stop if already speaking this message
    if (this.isSpeaking && this.speakingMessageId === messageId) {
      this.stop();
      return;
    }

    // Stop any ongoing playback
    this.stop();

    const cleanText = cleanTextForSpeech(text);
    if (!cleanText) return;

    const voice = this.getSelectedVoice();
    this.speakingMessageId = messageId;
    this.isSpeaking = true;
    this.notifyListeners();

    try {
      await EasySpeech.speak({
        text: cleanText,
        voice: voice || undefined,
        rate: this.rate,
        pitch: 1.0,
        volume: 1.0,
        end: () => {
          this.isSpeaking = false;
          this.speakingMessageId = null;
          this.notifyListeners();
        },
        error: (err) => {
          console.warn('Speech synthesis error:', err);
          this.isSpeaking = false;
          this.speakingMessageId = null;
          this.notifyListeners();
        }
      });
    } catch (err) {
      console.warn('EasySpeech.speak execution error:', err);
      this.isSpeaking = false;
      this.speakingMessageId = null;
      this.notifyListeners();
    }
  }

  stop() {
    try {
      EasySpeech.cancel();
    } catch (err) {
      // ignore
    }
    this.isSpeaking = false;
    this.speakingMessageId = null;
    this.notifyListeners();
  }

  // Handle auto-play for newly received messages containing a summary
  handleAutoPlayNewMessage(message) {
    if (!this.autoPlay || !message || message.role === 'user') return;
    const summaryText = message.summary || message.content;
    if (summaryText && summaryText.trim().length > 0) {
      this.speak(summaryText, message.id || `msg_${Date.now()}`);
    }
  }
}

export const speechService = new SpeechService();
export default speechService;
