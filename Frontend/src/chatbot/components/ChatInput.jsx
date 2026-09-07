import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Mic, MicOff } from 'lucide-react';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { useSuggestions } from '../hooks/useSuggestions';
import { useChatbot } from '../hooks/useChatbot';
import ChatSuggestions from './ChatSuggestions';

export const ChatInput = ({ onSend, disabled = false, suggestionLayout, suggestionsDisabled: propSuggestionsDisabled }) => {
  let chatbotCtx = null;
  try {
    chatbotCtx = useChatbot();
  } catch {
    // Graceful fallback if rendered outside provider
  }

  const [localText, setLocalText] = useState('');
  const text = chatbotCtx?.inputText !== undefined ? chatbotCtx.inputText : localText;
  const setText = chatbotCtx?.setInputText || setLocalText;

  const textareaRef = useRef(null);
  const baseTextRef = useRef('');

  // Auto-resize textarea on mount and when text exists/changes
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      if (text) {
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
      }
    }
  }, [text]);

  const effectiveSuggestionsDisabled = typeof propSuggestionsDisabled === 'boolean'
    ? propSuggestionsDisabled
    : (chatbotCtx?.suggestionsDisabled ?? false);

  const {
    suggestions,
    layout: defaultLayout,
    isScoring,
    isDisabled: isSuggestionsDisabled,
    toggleDisabled: localToggleDisabled,
    hideSuggestions,
  } = useSuggestions(text, effectiveSuggestionsDisabled);

  const activeLayout = suggestionLayout || chatbotCtx?.suggestionLayout || defaultLayout;

  const handleToggleDisabled = useCallback(() => {
    if (chatbotCtx?.setSuggestionsDisabled) {
      chatbotCtx.setSuggestionsDisabled(!effectiveSuggestionsDisabled);
    } else {
      localToggleDisabled();
    }
  }, [chatbotCtx, effectiveSuggestionsDisabled, localToggleDisabled]);

  const {
    isListening,
    transcript,
    isSupported: isSpeechSupported,
    startListening,
    stopListening,
    resetTranscript
  } = useSpeechRecognition();

  // Populate accumulated transcript accurately without duplicating words
  useEffect(() => {
    if (isListening && transcript) {
      const base = baseTextRef.current;
      const prefix = base ? (base.endsWith(' ') ? base : base + ' ') : '';
      setText(prefix + transcript);
    }
  }, [transcript, isListening]);

  const handleTextChange = (e) => {
    setText(e.target.value);
  };

  const handleKeyDown = (e) => {
    // Enter sends message, Shift+Enter adds newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = (overrideText) => {
    const messageToSend = typeof overrideText === 'string' ? overrideText : text;
    const trimmed = messageToSend.trim();
    if (!trimmed || disabled) return;

    if (isListening) {
      stopListening();
    }

    onSend(trimmed);
    setText('');
    baseTextRef.current = '';
    resetTranscript();
    hideSuggestions();

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleMicClick = () => {
    if (!isSpeechSupported) return;

    if (isListening) {
      stopListening();
    } else {
      baseTextRef.current = text;
      resetTranscript();
      startListening();
    }
  };

  // Handle suggestion chip click: fills textarea & allows user to edit
  const handleSelectSuggestion = useCallback((suggestionText) => {
    setText(suggestionText);
    hideSuggestions();
    if (textareaRef.current) {
      textareaRef.current.focus();
      // Auto resize height
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
          textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
        }
      }, 0);
    }
  }, [hideSuggestions]);

  // Handle direct send from suggestion chip
  const handleSendSuggestionDirectly = useCallback((suggestionText) => {
    handleSubmit(suggestionText);
  }, [handleSubmit]);

  return (
    <div className="cb-input-wrapper-container">
      {/* Suggestions Bubble Carousel / Stack above input bar */}
      <ChatSuggestions
        suggestions={suggestions}
        layout={activeLayout}
        isScoring={isScoring}
        onSelect={handleSelectSuggestion}
        onSend={handleSendSuggestionDirectly}
        onDismiss={hideSuggestions}
        onToggleDisabled={handleToggleDisabled}
      />

      <div className="cb-input-container">
        <div className="cb-textarea-wrapper">
          <textarea
            ref={textareaRef}
            className="cb-textarea"
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? 'Listening to speech...' : 'Type a message...'}
            disabled={disabled}
            rows={1}
            aria-label="Chat input field"
          />

          {/* Render mic button ONLY if browser supports Web Speech API */}
          {isSpeechSupported && (
            <button
              type="button"
              className={`cb-mic-btn ${isListening ? 'active' : ''}`}
              onClick={handleMicClick}
              disabled={disabled}
              aria-label={isListening ? 'Stop voice recording' : 'Start voice dictation'}
              title={isListening ? 'Listening... Click to stop' : 'Click to speak'}
            >
              {isListening ? <MicOff size={22} /> : <Mic size={22} />}
            </button>
          )}
        </div>

        <button
          type="button"
          className="cb-send-btn"
          onClick={() => handleSubmit()}
          disabled={disabled || !text.trim()}
          aria-label="Send message"
          title="Send Message"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
};

export default ChatInput;

