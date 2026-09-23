import React from 'react';
import { Sparkles, ArrowUpRight, Compass, Database, ShieldCheck } from 'lucide-react';
import { WELCOME_FAQ_QUESTIONS } from '../constants/chatbotConstants';

/**
 * WelcomeScreen Component
 * 
 * Displayed in the center of the chat screen when a new conversation is started.
 * Disappears automatically as soon as the user sends a message.
 * 
 * Features:
 * - Animated glowing bot avatar with pulse waves & floating motion
 * - Sleek typography & AP Citizen 360 branding
 * - Quick stats / capabilities tags
 * - Smooth infinite scrolling marquee of frequently asked questions with faded edge masks
 * - Interactive pills: clicking any prompt immediately triggers the query
 */
export const WelcomeScreen = ({ onSend, onSelect }) => {
  const handleQueryClick = (question) => {
    if (onSend) {
      onSend(question);
    } else if (onSelect) {
      onSelect(question);
    }
  };

  // Duplicate list to create a seamless infinite marquee loop
  const marqueeItems = [...WELCOME_FAQ_QUESTIONS, ...WELCOME_FAQ_QUESTIONS];

  return (
    <div className="cb-welcome-screen" role="region" aria-label="Welcome screen">
      {/* Background ambient glowing orbs */}
      <div className="cb-welcome-ambient-glow" aria-hidden="true" />
      <div className="cb-welcome-ambient-glow-secondary" aria-hidden="true" />

      <div className="cb-welcome-content">
        {/* Animated Bot Centerpiece */}
        <div className="cb-welcome-bot-container">
          <div className="cb-welcome-radar-ring ring-1" />
          <div className="cb-welcome-radar-ring ring-2" />
          <div className="cb-welcome-radar-ring ring-3" />

          <div className="cb-welcome-bot-circle">
            <svg
              className="cb-welcome-bot-svg"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 64 64"
              width="54"
              height="54"
            >
              <defs>
                <linearGradient id="botGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="50%" stopColor="#0284c7" />
                  <stop offset="100%" stopColor="#0b2545" />
                </linearGradient>
                <filter id="glowFilter" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Antenna */}
              <circle cx="32" cy="8" r="3.5" fill="#38bdf8" filter="url(#glowFilter)" className="cb-bot-antenna-beacon" />
              <line x1="32" y1="11" x2="32" y2="18" stroke="#60a5fa" strokeWidth="2.5" strokeLinecap="round" />

              {/* Head Shell */}
              <rect x="13" y="18" width="38" height="30" rx="15" fill="url(#botGrad)" stroke="#60a5fa" strokeWidth="1.5" />

              {/* Ear Pods */}
              <rect x="8" y="27" width="5" height="12" rx="2.5" fill="#0284c7" />
              <rect x="51" y="27" width="5" height="12" rx="2.5" fill="#0284c7" />

              {/* Visor Screen */}
              <rect x="18" y="24" width="28" height="16" rx="8" fill="#051329" />

              {/* Glowing Eyes */}
              <circle cx="26" cy="32" r="3.5" fill="#38bdf8" filter="url(#glowFilter)" className="cb-bot-eye" />
              <circle cx="38" cy="32" r="3.5" fill="#38bdf8" filter="url(#glowFilter)" className="cb-bot-eye" />

              {/* Friendly Smile Indicator */}
              <path
                d="M 27 41 Q 32 44 37 41"
                fill="none"
                stroke="#38bdf8"
                strokeWidth="1.8"
                strokeLinecap="round"
                className="cb-bot-smile"
              />

              {/* Collar Accent */}
              <path d="M 23 48 L 41 48" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" opacity="0.6" />
            </svg>
          </div>
          <div className="cb-welcome-online-badge">
            <span className="cb-online-pulse-dot" />
            <span>AI Ready</span>
          </div>
        </div>

        {/* Text Greeting */}
        <div className="cb-welcome-text-wrap">
          <div className="cb-welcome-pill-tag">
            <Sparkles size={14} className="cb-welcome-sparkle-icon" />
            <span>AP Citizen 360 AI Assistant</span>
          </div>
          <h2 className="cb-welcome-title">How can I assist you today?</h2>
          <p className="cb-welcome-desc">
            Ask queries regarding citizen demographics, welfare scheme disbursements,
            and policy intelligence in Andhra Pradesh.
          </p>
        </div>

        {/* Capabilities Chips */}
        <div className="cb-welcome-features">
          <div className="cb-welcome-feature-item">
            <Database size={13} className="cb-feature-icon" />
            <span>Real-time Data Lake</span>
          </div>
          <div className="cb-welcome-feature-item">
            <Compass size={13} className="cb-feature-icon" />
            <span>Natural Language to SQL</span>
          </div>
          <div className="cb-welcome-feature-item">
            <ShieldCheck size={13} className="cb-feature-icon" />
            <span>Policy Guardrails</span>
          </div>
        </div>

        {/* Frequently Asked Queries Carousel */}
        <div className="cb-welcome-faq-section">
          <div className="cb-welcome-faq-header">
            <span className="cb-welcome-faq-indicator">FREQUENTLY ASKED QUERIES</span>
            <span className="cb-welcome-faq-hint">Click any query to ask directly</span>
          </div>

          <div className="cb-welcome-marquee-wrapper">
            <div className="cb-welcome-marquee-track scroll-left">
              {marqueeItems.map((question, index) => (
                <button
                  key={`q1-${index}`}
                  type="button"
                  className="cb-welcome-faq-chip"
                  onClick={() => handleQueryClick(question)}
                  title={`Ask: "${question}"`}
                >
                  <span className="cb-welcome-chip-bullet">💬</span>
                  <span className="cb-welcome-chip-text">{question}</span>
                  <ArrowUpRight size={14} className="cb-welcome-chip-arrow" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;
