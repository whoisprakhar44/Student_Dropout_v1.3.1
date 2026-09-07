import React, { useState } from 'react';
import { ChatbotProvider } from './chatbot/ChatbotProvider';
import Chatbot from './chatbot/Chatbot';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div style={{
      minHeight: '100vh',
      background: 'radial-gradient(1000px circle at 50% -250px, rgba(59, 130, 246, 0.2), transparent 60%), linear-gradient(180deg, var(--background-color), #040913)',
      color: 'var(--text-color)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      padding: '30px',
      boxSizing: 'border-box'
    }}>
      {/* Header Bar */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingBottom: '20px',
        borderBottom: '1px solid var(--border-color)',
        marginBottom: '40px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: 'var(--primary-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            color: '#fff'
          }}>
            P
          </div>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>Production Enterprise Portal</h2>
        </div>

        <nav style={{ display: 'flex', gap: '12px' }}>
          {['dashboard', 'analytics', 'settings'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: '1px solid var(--border-color)',
                background: activeTab === tab ? 'var(--primary-color)' : 'var(--surface-color)',
                color: activeTab === tab ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                fontWeight: 600,
                textTransform: 'capitalize',
                transition: 'all 0.2s ease'
              }}
            >
              {tab}
            </button>
          ))}
        </nav>
      </header>

      {/* Main Page Area */}
      <main style={{ maxWidth: '1000px', margin: '0 auto', textAlign: 'center', paddingTop: '60px' }}>
        <div style={{
          background: 'var(--surface-color)',
          border: '1px solid var(--border-color)',
          borderRadius: '16px',
          padding: '48px',
          boxShadow: '0 15px 35px var(--shadow-color)'
        }}>
          <h1 style={{ fontSize: '28px', marginBottom: '16px', color: 'var(--text-color)' }}>
            Production application content goes here
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '15px', maxWidth: '600px', margin: '0 auto 24px auto', lineHeight: '1.6' }}>
            Simulate route navigation using the tabs above. Notice how the floating chatbot widget at the bottom right maintains its active conversation state and open window without resetting!
          </p>
          <div style={{
            display: 'inline-block',
            padding: '8px 16px',
            borderRadius: '999px',
            background: 'rgba(59, 130, 246, 0.15)',
            color: 'var(--primary-color)',
            fontWeight: 600,
            fontSize: '13px',
            border: '1px solid var(--border-color)'
          }}>
            Active Route: /{activeTab}
          </div>
        </div>
      </main>

      {/* Standalone Reusable Chatbot Widget Mount Point */}
      <ChatbotProvider>
        <Chatbot />
      </ChatbotProvider>
    </div>
  );
}

export default App;
