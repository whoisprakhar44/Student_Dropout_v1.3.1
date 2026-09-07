import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Speech Recognition Inactivity Timeout (ms)
 * Default: 3000ms (3 seconds). Overridable via VITE_SPEECH_INACTIVITY_TIMEOUT_MS env variable.
 */
const INACTIVITY_TIMEOUT_MS = Number(import.meta.env?.VITE_SPEECH_INACTIVITY_TIMEOUT_MS) || 3000;

/**
 * Custom hook to interface with Web Speech API for Speech Recognition.
 * Accurately transcribes audio into text without duplicate word repetitions.
 * Automatically stops recording after a period of user speech inactivity.
 */
export const useSpeechRecognition = () => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);

  const recognitionRef = useRef(null);
  const inactivityTimerRef = useRef(null);

  // Check Web Speech API browser availability
  const SpeechRecognition =
    typeof window !== 'undefined' &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);
  const isSupported = Boolean(SpeechRecognition);

  // Helper to clear speech inactivity timer
  const clearInactivityTimer = useCallback(() => {
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
  }, []);

  // Helper to reset and schedule inactivity timer
  const resetInactivityTimer = useCallback(() => {
    clearInactivityTimer();
    inactivityTimerRef.current = setTimeout(() => {
      stopListening();
    }, INACTIVITY_TIMEOUT_MS);
  }, [clearInactivityTimer]);

  const stopListening = useCallback(() => {
    clearInactivityTimer();
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (err) {
        console.warn('Failed to stop speech recognition:', err);
      }
    }
    setIsListening(false);
  }, [clearInactivityTimer]);

  useEffect(() => {
    if (!isSupported) return;

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsListening(true);
        setError(null);
        resetInactivityTimer();
      };

      recognition.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = 0; i < event.results.length; i++) {
          const text = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += text;
          } else {
            interimTranscript += text;
          }
        }

        const fullTranscript = (finalTranscript + interimTranscript).trim();
        setTranscript(fullTranscript);

        // Reset inactivity countdown timer on active speech results
        resetInactivityTimer();
      };

      recognition.onerror = (event) => {
        if (event.error !== 'no-speech') {
          console.warn('Speech recognition error:', event.error);
          setError(event.error);
        }
        clearInactivityTimer();
        setIsListening(false);
      };

      recognition.onend = () => {
        clearInactivityTimer();
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    } catch (e) {
      console.warn('Speech Recognition setup error:', e);
      setError('Initialization failed');
    }

    return () => {
      clearInactivityTimer();
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {
          // ignore cleanup errors
        }
      }
    };
  }, [isSupported, resetInactivityTimer, clearInactivityTimer]);

  const startListening = useCallback(() => {
    if (!isSupported) {
      setError('Speech recognition is not supported in this browser.');
      return;
    }

    setTranscript('');
    setError(null);

    try {
      if (recognitionRef.current) {
        recognitionRef.current.start();
      }
    } catch (err) {
      console.warn('Failed to start speech recognition:', err);
      setIsListening(false);
    }
  }, [isSupported]);

  const resetTranscript = useCallback(() => {
    setTranscript('');
  }, []);

  return {
    isListening,
    transcript,
    error,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
  };
};
