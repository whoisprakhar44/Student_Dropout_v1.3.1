import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  Lock,
  Unlock,
  KeyRound,
  ShieldCheck,
  AlertCircle,
  Eye,
  EyeOff,
  Clock,
  ArrowRight,
  ShieldAlert,
  Sparkles
} from 'lucide-react';

export const AccessKeyContext = createContext(null);

export const useAccessKey = () => {
  const context = useContext(AccessKeyContext);
  if (!context) {
    return {
      isUnlocked: true,
      remainingMinutes: 30,
      remainingFormatted: '30:00',
      lockApp: () => {},
      expiresAt: null
    };
  }
  return context;
};

const STORAGE_SESSION_KEY = 'app_access_key_session';
const DEFAULT_HASH = 'aaa065eb6460b9d4d1e824de3422738595646507678efad38d20f52f20bb5272'; // SHA-256 for 'DevTest'
const DEFAULT_VALIDITY_MINUTES = 30;

/**
 * Compute SHA-256 hash using native browser Web Crypto API
 */
async function computeSha256(text) {
  const buffer = new TextEncoder().encode(text);
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

export const AccessKeyGate = ({ children }) => {
  const targetHash = (
    import.meta.env?.VITE_APP_ACCESS_KEY_HASH || DEFAULT_HASH
  ).toLowerCase().trim();

  const validityMinutes = Number(
    import.meta.env?.VITE_APP_ACCESS_KEY_VALIDITY_MINUTES || DEFAULT_VALIDITY_MINUTES
  );

  // Check stored session
  const [isUnlocked, setIsUnlocked] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_SESSION_KEY);
      if (raw) {
        const session = JSON.parse(raw);
        if (session.authenticated && session.expiresAt && Date.now() < session.expiresAt) {
          return true;
        }
      }
    } catch {
      // fallback to locked
    }
    return false;
  });

  const [inputKey, setInputKey] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [shake, setShake] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // Auto-expire timer check and countdown
  useEffect(() => {
    if (!isUnlocked) return;

    const checkExpiration = () => {
      try {
        const raw = localStorage.getItem(STORAGE_SESSION_KEY);
        if (!raw) {
          setIsUnlocked(false);
          return;
        }
        const session = JSON.parse(raw);
        const now = Date.now();
        if (!session.authenticated || !session.expiresAt || now >= session.expiresAt) {
          localStorage.removeItem(STORAGE_SESSION_KEY);
          setIsUnlocked(false);
          setErrorMsg('Session expired after 30 minutes. Please re-enter your access key.');
          return;
        }
        setRemainingSeconds(Math.max(0, Math.floor((session.expiresAt - now) / 1000)));
      } catch {
        setIsUnlocked(false);
      }
    };

    checkExpiration();
    const interval = setInterval(checkExpiration, 1000);
    return () => clearInterval(interval);
  }, [isUnlocked]);

  const lockApp = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_SESSION_KEY);
    } catch {}
    setIsUnlocked(false);
    setInputKey('');
    setErrorMsg('');
  }, []);

  const handleUnlock = async (e) => {
    e?.preventDefault();
    const trimmed = inputKey.trim();
    if (!trimmed) {
      setErrorMsg('Please enter the access key.');
      setShake(true);
      setTimeout(() => setShake(false), 500);
      return;
    }

    setIsVerifying(true);
    setErrorMsg('');

    try {
      const inputHash = await computeSha256(trimmed);
      if (inputHash === targetHash) {
        const expiresAt = Date.now() + validityMinutes * 60 * 1000;
        const sessionData = {
          authenticated: true,
          expiresAt,
          unlockedAt: Date.now()
        };
        localStorage.setItem(STORAGE_SESSION_KEY, JSON.stringify(sessionData));
        setRemainingSeconds(validityMinutes * 60);
        setIsUnlocked(true);
        setInputKey('');
        setErrorMsg('');
      } else {
        setErrorMsg('Invalid Access Key. Please verify credentials and try again.');
        setShake(true);
        setTimeout(() => setShake(false), 500);
      }
    } catch (err) {
      setErrorMsg('Cryptographic verification error. Please try again.');
    } finally {
      setIsVerifying(false);
    }
  };

  const minutesLeft = Math.floor(remainingSeconds / 60);
  const secondsLeft = remainingSeconds % 60;
  const remainingFormatted = `${minutesLeft.toString().padStart(2, '0')}:${secondsLeft.toString().padStart(2, '0')}`;

  const contextValue = {
    isUnlocked,
    remainingSeconds,
    remainingMinutes: minutesLeft,
    remainingFormatted,
    lockApp,
    validityMinutes
  };

  // If authenticated, render application wrapped with context
  if (isUnlocked) {
    return (
      <AccessKeyContext.Provider value={contextValue}>
        {children}
      </AccessKeyContext.Provider>
    );
  }

  // Access Key Challenge Screen
  return (
    <AccessKeyContext.Provider value={contextValue}>
      <div style={{
        minHeight: '100vh',
        width: '100vw',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'radial-gradient(1200px circle at 50% 25%, rgba(30, 58, 138, 0.45) 0%, rgba(15, 23, 42, 0.95) 70%, #030712 100%)',
        color: '#f8fafc',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        padding: '20px',
        boxSizing: 'border-box'
      }}>
        {/* Glow ambient background element */}
        <div style={{
          position: 'fixed',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.15) 0%, transparent 70%)',
          pointerEvents: 'none',
          top: '20%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 0
        }} />

        <div style={{
          position: 'relative',
          zIndex: 1,
          width: '100%',
          maxWidth: '440px',
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: '20px',
          padding: '36px 32px',
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.7), 0 0 35px rgba(59, 130, 246, 0.15)',
          transform: shake ? 'translateX(-8px)' : 'none',
          transition: 'transform 0.1s ease',
          animation: shake ? 'cbShake 0.4s ease' : 'none'
        }}>
          {/* Top Security Icon Badge */}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.3) 0%, rgba(59, 130, 246, 0.1) 100%)',
              border: '1px solid rgba(59, 130, 246, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#60a5fa',
              boxShadow: '0 8px 24px rgba(37, 99, 235, 0.25)'
            }}>
              <KeyRound size={30} />
            </div>
          </div>

          {/* Heading */}
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: '999px',
              background: 'rgba(59, 130, 246, 0.15)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              color: '#93c5fd',
              fontSize: '11px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.6px',
              marginBottom: '10px'
            }}>
              <ShieldCheck size={13} />
              Portal Access Verification
            </div>
            <h1 style={{ margin: '0 0 8px 0', fontSize: '22px', fontWeight: 700, color: '#f8fafc' }}>
              AP Citizen 360 Portal
            </h1>
            <p style={{ margin: 0, fontSize: '13px', color: '#94a3b8', lineHeight: '1.5' }}>
              This enterprise portal is protected. Please enter your authorized access key to proceed.
            </p>
          </div>

          {/* Error Banner */}
          {errorMsg && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              color: '#fca5a5',
              padding: '10px 14px',
              borderRadius: '10px',
              fontSize: '12px',
              marginBottom: '18px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleUnlock}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#cbd5e1',
                marginBottom: '8px',
                letterSpacing: '0.3px'
              }}>
                Access Key Password
              </label>

              <div style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center'
              }}>
                <div style={{
                  position: 'absolute',
                  left: '14px',
                  color: '#64748b',
                  display: 'flex',
                  alignItems: 'center',
                  pointerEvents: 'none'
                }}>
                  <Lock size={16} />
                </div>

                <input
                  type={showPassword ? 'text' : 'password'}
                  value={inputKey}
                  onChange={(e) => setInputKey(e.target.value)}
                  placeholder="Enter access key..."
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '12px 42px 12px 40px',
                    borderRadius: '10px',
                    background: 'rgba(15, 23, 42, 0.7)',
                    border: '1px solid rgba(59, 130, 246, 0.35)',
                    color: '#f8fafc',
                    fontSize: '14px',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'all 0.2s ease',
                    boxShadow: 'inset 0 2px 4px rgba(0, 0, 0, 0.4)'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#3b82f6';
                    e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.25)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'rgba(59, 130, 246, 0.35)';
                    e.target.style.boxShadow = 'inset 0 2px 4px rgba(0, 0, 0, 0.4)';
                  }}
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    background: 'transparent',
                    border: 'none',
                    color: '#64748b',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '4px',
                    borderRadius: '4px',
                    transition: 'color 0.2s ease'
                  }}
                  title={showPassword ? 'Hide password' : 'Show password'}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isVerifying}
              style={{
                width: '100%',
                padding: '13px 20px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                color: '#ffffff',
                border: 'none',
                fontSize: '14px',
                fontWeight: 600,
                cursor: isVerifying ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 4px 14px rgba(37, 99, 235, 0.4)',
                transition: 'all 0.2s ease',
                opacity: isVerifying ? 0.7 : 1
              }}
              onMouseEnter={(e) => {
                if (!isVerifying) e.currentTarget.style.background = 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)';
              }}
              onMouseLeave={(e) => {
                if (!isVerifying) e.currentTarget.style.background = 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)';
              }}
            >
              {isVerifying ? (
                <>Verifying cryptographic hash...</>
              ) : (
                <>
                  <span>Unlock Portal</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          {/* Footer Metadata */}
          <div style={{
            marginTop: '24px',
            paddingTop: '18px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            fontSize: '11px',
            color: '#64748b',
            textAlign: 'center'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              <Clock size={13} color="#94a3b8" />
              <span>Session Validity: <strong>{validityMinutes} Minutes</strong> from unlock</span>
            </div>
            <div>
              Protected by SHA-256 password hash in environment variables.
            </div>
          </div>
        </div>
      </div>
    </AccessKeyContext.Provider>
  );
};

export default AccessKeyGate;
