import React, { useState } from 'react';
import { ChatbotProvider } from './chatbot/ChatbotProvider';
import Chatbot from './chatbot/Chatbot';
import { useChatbot } from './chatbot/hooks/useChatbot';
import { CHAT_LAYERS, VIEW_MODES } from './chatbot/constants/chatbotConstants';
import AccessKeyGate, { useAccessKey } from './components/AccessKeyGate';
import {
  Sparkles,
  Database,
  Layers,
  Sliders,
  Shield,
  Eye,
  EyeOff,
  Maximize2,
  MessageSquare,
  Activity,
  Server,
  Code2,
  CheckCircle2,
  ExternalLink,
  TableProperties,
  Download,
  Copy,
  Lock,
  Unlock,
  ShieldAlert,
  FileSpreadsheet,
  Clock,
  RotateCcw
} from 'lucide-react';

/**
 * Inner Dashboard Component that interacts directly with Chatbot Context
 */
function PortalDashboard({ activeTab, setActiveTab }) {
  const {
    activeLayer,
    setActiveLayer,
    isSchemaEnabled,
    setIsSchemaEnabled,
    sduiPrivileges,
    updateSduiPrivileges,
    showSecurityToast,
    sessions,
    openChat,
    toggleFullscreen,
    viewMode,
    connectionStatus,
    canAccessChatbot,
    isChatDisabledBySecurity,
    resetSecurityLock
  } = useChatbot();

  const [sduiRole, setSduiRole] = useState('admin');

  // Compute metrics per layer
  const curatedSessionsCount = sessions.filter(
    (s) => (s.layer || CHAT_LAYERS.CURATED) === CHAT_LAYERS.CURATED
  ).length;

  const schemaSessionsCount = sessions.filter(
    (s) => (s.layer || CHAT_LAYERS.CURATED) === CHAT_LAYERS.SCHEMA
  ).length;

  // Mock SDUI backend config payload
  const sduiConfigPayload = {
    version: '2.5.0',
    user: {
      role: sduiRole,
      permissions: sduiRole === 'admin'
        ? ['chat.curated', 'chat.schema', 'table.export.csv', 'table.export.excel', 'table.copy', 'sql.execute']
        : ['chat.curated'],
    },
    sdui_components: {
      sidebar_tabs: {
        curated_mode: {
          enabled: true,
          label: 'Curated',
          description: 'Domain & Policy Intelligence',
          default: true
        },
        schema_mode: {
          enabled: isSchemaEnabled,
          label: 'Schema',
          description: 'Relational DB Schema Query',
          badge: 'Beta',
          requires_permission: 'chat.schema',
          param_layer: 'schema'
        }
      },
      table_actions: {
        allow_export: sduiPrivileges?.allowTableExport ?? false,
        allow_csv: sduiPrivileges?.allowCsvExport ?? false,
        allow_excel: sduiPrivileges?.allowExcelExport ?? false,
        allow_copy: sduiPrivileges?.allowCopyTable ?? false,
      },
      security_policy: {
        copy_protection: sduiPrivileges?.copyProtection ?? true,
        devtools_protection: sduiPrivileges?.devToolsProtection ?? true,
        anti_screenshot_alert: true,
      },
      chatbot_access: {
        privilege_granted: sduiPrivileges?.canAccessChatbot !== false,
        toggle_icon_visible: sduiPrivileges?.canAccessChatbot !== false,
        queries_permitted: sduiPrivileges?.canAccessChatbot !== false && !isChatDisabledBySecurity,
      },
      access_key_security: {
        enabled: true,
        validity_minutes: 30,
        verification_method: 'SHA-256'
      },
      transport: {
        primary: 'websocket',
        fallback: 'http_post',
        endpoint_param: 'layer'
      }
    }
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(15, 23, 42, 0.8) 100%)',
        border: '1px solid rgba(59, 130, 246, 0.25)',
        borderRadius: '16px',
        padding: '24px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.3)'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
            <span style={{
              background: 'rgba(59, 130, 246, 0.2)',
              color: '#60a5fa',
              padding: '2px 8px',
              borderRadius: '999px',
              fontSize: '11px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              SDUI Controlled Chatbot
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>•</span>
            <span style={{ color: '#10b981', fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
              Active Layer: {activeLayer.toUpperCase()}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>•</span>
            <span style={{
              color: sduiPrivileges?.canAccessChatbot !== false ? '#34d399' : '#f87171',
              fontSize: '12px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <MessageSquare size={12} />
              Chatbot Privilege: {sduiPrivileges?.canAccessChatbot !== false ? 'GRANTED' : 'REVOKED'}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>•</span>
            <span style={{
              color: sduiPrivileges?.copyProtection ? '#f87171' : '#a3e635',
              fontSize: '12px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <Lock size={12} />
              Copy Protection: {sduiPrivileges?.copyProtection ? 'ACTIVE' : 'OFF'}
            </span>
            {isChatDisabledBySecurity && (
              <>
                <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>•</span>
                <span style={{
                  color: '#ef4444',
                  fontSize: '12px',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  padding: '1px 6px',
                  borderRadius: '6px'
                }}>
                  <ShieldAlert size={12} />
                  DEVTOOLS LOCKED
                </span>
              </>
            )}
          </div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: 'var(--text-color)' }}>
            Chatbot SDUI & Privileges Control Center
          </h1>
          <p style={{ margin: '6px 0 0 0', color: 'var(--text-muted)', fontSize: '14px' }}>
            Manage schema tab visibility, table download privileges, chatbot icon visibility, and security rules dynamically.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => {
              if (canAccessChatbot === false) {
                showSecurityToast('🔒 Chatbot access privilege is revoked.');
                return;
              }
              if (isChatDisabledBySecurity) {
                showSecurityToast('🔒 Chat option is disabled due to DevTools security violation.');
                return;
              }
              setActiveLayer(CHAT_LAYERS.CURATED);
              openChat(VIEW_MODES.FULLSCREEN);
            }}
            disabled={canAccessChatbot === false || isChatDisabledBySecurity}
            style={{
              padding: '10px 18px',
              background: activeLayer === CHAT_LAYERS.CURATED ? 'var(--primary-color)' : 'rgba(255, 255, 255, 0.08)',
              color: '#fff',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: '10px',
              cursor: (canAccessChatbot === false || isChatDisabledBySecurity) ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              opacity: (canAccessChatbot === false || isChatDisabledBySecurity) ? 0.5 : 1,
              transition: 'all 0.2s ease'
            }}
          >
            <Sparkles size={15} />
            {canAccessChatbot === false ? 'Curated Chat (Revoked)' : (isChatDisabledBySecurity ? 'Curated Chat (Locked)' : 'Open Curated Chat')}
          </button>

          <button
            onClick={() => {
              if (canAccessChatbot === false) {
                showSecurityToast('🔒 Chatbot access privilege is revoked.');
                return;
              }
              if (isChatDisabledBySecurity) {
                showSecurityToast('🔒 Chat option is disabled due to DevTools security violation.');
                return;
              }
              if (!isSchemaEnabled) setIsSchemaEnabled(true);
              setActiveLayer(CHAT_LAYERS.SCHEMA);
              openChat(VIEW_MODES.FULLSCREEN);
            }}
            disabled={canAccessChatbot === false || isChatDisabledBySecurity}
            style={{
              padding: '10px 18px',
              background: activeLayer === CHAT_LAYERS.SCHEMA ? 'linear-gradient(135deg, #7c3aed, #9333ea)' : 'rgba(139, 92, 246, 0.15)',
              color: activeLayer === CHAT_LAYERS.SCHEMA ? '#fff' : '#c084fc',
              border: '1px solid rgba(139, 92, 246, 0.4)',
              borderRadius: '10px',
              cursor: (canAccessChatbot === false || isChatDisabledBySecurity) ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              opacity: (canAccessChatbot === false || isChatDisabledBySecurity) ? 0.5 : 1,
              transition: 'all 0.2s ease'
            }}
          >
            <Database size={15} />
            {canAccessChatbot === false ? 'Schema Chat (Revoked)' : (isChatDisabledBySecurity ? 'Schema Chat (Locked)' : 'Open Schema Chat')}
          </button>
        </div>
      </div>

      {/* DevTools Security Violation Alert Banner */}
      {isChatDisabledBySecurity && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.12)',
          border: '1px solid rgba(239, 68, 68, 0.45)',
          borderRadius: '14px',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          boxShadow: '0 4px 20px rgba(239, 68, 68, 0.15)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'rgba(239, 68, 68, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#f87171'
            }}>
              <ShieldAlert size={20} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '14px', color: '#fca5a5' }}>
                DevTools Inspection Active — Chatbot Interface Disabled
              </div>
              <div style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '2px' }}>
                Developer tools or restricted shortcut keys were triggered while DevTools protection was active. The chatbot has been locked out from UI.
              </div>
            </div>
          </div>
          <button
            onClick={() => {
              resetSecurityLock();
              showSecurityToast('🔓 Security lock reset by administrator.');
            }}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: 'none',
              background: '#ef4444',
              color: '#ffffff',
              fontWeight: 600,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 2px 8px rgba(239, 68, 68, 0.4)',
              transition: 'all 0.2s ease'
            }}
          >
            <RotateCcw size={13} />
            Reset Security Lock
          </button>
        </div>
      )}

      {/* Grid: 3 Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {/* Curated Mode Card */}
        <div style={{
          background: 'var(--surface-color)',
          border: `1px solid ${activeLayer === CHAT_LAYERS.CURATED ? 'var(--primary-color)' : 'var(--border-color)'}`,
          borderRadius: '14px',
          padding: '20px',
          boxShadow: '0 4px 20px var(--shadow-color)',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <span style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase' }}>
                Mode 1 (Default)
              </span>
              <h3 style={{ margin: '4px 0', fontSize: '18px', fontWeight: 700, color: 'var(--text-color)' }}>
                Curated Chat Layer
              </h3>
            </div>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'rgba(59, 130, 246, 0.15)',
              color: 'var(--primary-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Sparkles size={18} />
            </div>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '8px 0 16px 0', lineHeight: '1.4' }}>
            Domain-verified questions, AP Citizen 360 policies, schemes & welfare data intelligence.
          </p>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Saved Conversations: <strong style={{ color: 'var(--text-color)' }}>{curatedSessionsCount}</strong>
            </span>
            <button
              onClick={() => setActiveLayer(CHAT_LAYERS.CURATED)}
              style={{
                padding: '5px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                border: 'none',
                background: activeLayer === CHAT_LAYERS.CURATED ? 'var(--primary-color)' : 'rgba(255, 255, 255, 0.06)',
                color: activeLayer === CHAT_LAYERS.CURATED ? '#fff' : 'var(--text-color)',
                cursor: 'pointer'
              }}
            >
              {activeLayer === CHAT_LAYERS.CURATED ? 'Active Mode' : 'Select'}
            </button>
          </div>
        </div>

        {/* Schema Mode Card */}
        <div style={{
          background: 'var(--surface-color)',
          border: `1px solid ${activeLayer === CHAT_LAYERS.SCHEMA ? '#8b5cf6' : 'var(--border-color)'}`,
          borderRadius: '14px',
          padding: '20px',
          boxShadow: '0 4px 20px var(--shadow-color)',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase' }}>
                  Mode 2 (New)
                </span>
                <span style={{
                  fontSize: '9px',
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: '999px',
                  background: 'rgba(139, 92, 246, 0.25)',
                  color: '#c084fc',
                  border: '1px solid rgba(139, 92, 246, 0.4)'
                }}>
                  SDUI Controlled
                </span>
              </div>
              <h3 style={{ margin: '4px 0', fontSize: '18px', fontWeight: 700, color: 'var(--text-color)' }}>
                Schema Chat Layer
              </h3>
            </div>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'rgba(139, 92, 246, 0.15)',
              color: '#a855f7',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Database size={18} />
            </div>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '8px 0 16px 0', lineHeight: '1.4' }}>
            Direct queries for relational tables, column metadata, schemas, and catalog definitions.
          </p>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Saved Conversations: <strong style={{ color: '#c084fc' }}>{schemaSessionsCount}</strong>
            </span>
            <button
              onClick={() => setActiveLayer(CHAT_LAYERS.SCHEMA)}
              style={{
                padding: '5px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                border: 'none',
                background: activeLayer === CHAT_LAYERS.SCHEMA ? 'linear-gradient(135deg, #7c3aed, #9333ea)' : 'rgba(255, 255, 255, 0.06)',
                color: activeLayer === CHAT_LAYERS.SCHEMA ? '#fff' : 'var(--text-color)',
                cursor: 'pointer'
              }}
            >
              {activeLayer === CHAT_LAYERS.SCHEMA ? 'Active Mode' : 'Select'}
            </button>
          </div>
        </div>

        {/* SDUI Schema Visibility Card */}
        <div style={{
          background: 'var(--surface-color)',
          border: '1px solid var(--border-color)',
          borderRadius: '14px',
          padding: '20px',
          boxShadow: '0 4px 20px var(--shadow-color)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <span style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase' }}>
                Backend SDUI Visibility
              </span>
              <h3 style={{ margin: '4px 0', fontSize: '18px', fontWeight: 700, color: 'var(--text-color)' }}>
                Schema Tab Switcher
              </h3>
            </div>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: isSchemaEnabled ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: isSchemaEnabled ? '#10b981' : '#ef4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {isSchemaEnabled ? <Eye size={18} /> : <EyeOff size={18} />}
            </div>
          </div>

          <div style={{ margin: '12px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-color)', fontWeight: 500 }}>
              Schema Mode Visibility
            </span>
            <button
              onClick={() => setIsSchemaEnabled(!isSchemaEnabled)}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                border: '1px solid var(--border-color)',
                background: isSchemaEnabled ? '#10b981' : '#ef4444',
                color: '#fff',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              {isSchemaEnabled ? 'Enabled (Visible)' : 'Disabled (Hidden)'}
            </button>
          </div>

          <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px', fontSize: '12px', color: 'var(--text-muted)' }}>
            Controls whether the Schema tab is rendered in the left sidebar above the New Chat button.
          </div>
        </div>
      </div>

      {/* SDUI Privileges & Security Rules Control Bar */}
      <div style={{
        background: 'var(--surface-color)',
        border: '1px solid var(--border-color)',
        borderRadius: '14px',
        padding: '24px',
        boxShadow: '0 4px 20px var(--shadow-color)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Shield size={18} color="var(--primary-color)" />
              <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700, color: 'var(--text-color)' }}>
                User Privileges & Security Governance (SDUI Settings)
              </h3>
            </div>
            <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)', fontSize: '13px' }}>
              Live toggle table export actions and content copy protection rules to test frontend responses.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => {
                updateSduiPrivileges({
                  allowTableExport: true,
                  allowCsvExport: true,
                  allowExcelExport: true,
                  allowCopyTable: true,
                  canAccessChatbot: true,
                  allowChatbotAccess: true,
                  copyProtection: false,
                  devToolsProtection: false
                });
                resetSecurityLock();
                showSecurityToast('✅ Granted all privileges (including Chatbot toggle & access).');
              }}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                background: 'rgba(255, 255, 255, 0.05)',
                color: 'var(--text-color)',
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              Grant All Privileges
            </button>
            <button
              onClick={() => {
                updateSduiPrivileges({
                  allowTableExport: false,
                  allowCsvExport: false,
                  allowExcelExport: false,
                  allowCopyTable: false,
                  canAccessChatbot: false,
                  allowChatbotAccess: false,
                  copyProtection: true,
                  devToolsProtection: true
                });
                showSecurityToast('🔒 Restricted all: Chatbot toggle hidden & queries blocked.');
              }}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                background: 'rgba(239, 68, 68, 0.1)',
                color: '#f87171',
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              Restrict All (Locked Mode)
            </button>
          </div>
        </div>

        {/* Privileges Toggle Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
          {/* Chatbot Access & Toggle Icon Privilege */}
          <div style={{
            background: 'var(--background-color)',
            border: `1px solid ${sduiPrivileges?.canAccessChatbot !== false ? 'rgba(59, 130, 246, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
            padding: '12px 14px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600, color: 'var(--text-color)' }}>
                <MessageSquare size={14} color={sduiPrivileges?.canAccessChatbot !== false ? '#3b82f6' : '#ef4444'} />
                <span>Chatbot Toggle & Access</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Show toggle icon & allow queries</span>
            </div>
            <button
              onClick={() => {
                const nextVal = sduiPrivileges?.canAccessChatbot === false ? true : false;
                updateSduiPrivileges({
                  canAccessChatbot: nextVal,
                  allowChatbotAccess: nextVal
                });
                if (!nextVal) {
                  showSecurityToast('🔒 Chatbot access privilege revoked: icon hidden & queries blocked.');
                } else {
                  showSecurityToast('✅ Chatbot access privilege granted.');
                }
              }}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                background: sduiPrivileges?.canAccessChatbot !== false ? '#10b981' : '#ef4444',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              {sduiPrivileges?.canAccessChatbot !== false ? 'Granted' : 'Revoked'}
            </button>
          </div>

          {/* Table Export Toggle */}
          <div style={{
            background: 'var(--background-color)',
            border: '1px solid var(--border-color)',
            padding: '12px 14px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600, color: 'var(--text-color)' }}>
                <Download size={14} color="var(--primary-color)" />
                <span>Allow Table Exports</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Show CSV/Excel action bar</span>
            </div>
            <button
              onClick={() => updateSduiPrivileges({
                allowTableExport: !sduiPrivileges?.allowTableExport,
                allowCsvExport: !sduiPrivileges?.allowTableExport,
                allowExcelExport: !sduiPrivileges?.allowTableExport,
              })}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                background: sduiPrivileges?.allowTableExport ? '#10b981' : '#64748b',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              {sduiPrivileges?.allowTableExport ? 'Enabled' : 'Disabled'}
            </button>
          </div>

          {/* Table Copy Toggle */}
          <div style={{
            background: 'var(--background-color)',
            border: '1px solid var(--border-color)',
            padding: '12px 14px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600, color: 'var(--text-color)' }}>
                <Copy size={14} color="#60a5fa" />
                <span>Allow Table Copy</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Show Copy button on tables</span>
            </div>
            <button
              onClick={() => updateSduiPrivileges({ allowCopyTable: !sduiPrivileges?.allowCopyTable })}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                background: sduiPrivileges?.allowCopyTable ? '#10b981' : '#64748b',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              {sduiPrivileges?.allowCopyTable ? 'Enabled' : 'Disabled'}
            </button>
          </div>

          {/* Content Copy Protection Toggle */}
          <div style={{
            background: 'var(--background-color)',
            border: `1px solid ${sduiPrivileges?.copyProtection ? 'rgba(239, 68, 68, 0.4)' : 'var(--border-color)'}`,
            padding: '12px 14px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600, color: 'var(--text-color)' }}>
                <Lock size={14} color="#f87171" />
                <span>Copy Protection</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Block text select, Ctrl+C & menus</span>
            </div>
            <button
              onClick={() => {
                const nextVal = !sduiPrivileges?.copyProtection;
                updateSduiPrivileges({ copyProtection: nextVal });
                if (nextVal) showSecurityToast('🔒 Content copy protection has been activated.');
              }}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                background: sduiPrivileges?.copyProtection ? '#ef4444' : '#64748b',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              {sduiPrivileges?.copyProtection ? 'Active' : 'Off'}
            </button>
          </div>

          {/* DevTools Protection Toggle */}
          <div style={{
            background: 'var(--background-color)',
            border: '1px solid var(--border-color)',
            padding: '12px 14px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', fontWeight: 600, color: 'var(--text-color)' }}>
                <ShieldAlert size={14} color="#f59e0b" />
                <span>DevTools Protection</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>F12 restriction & watermark</span>
            </div>
            <button
              onClick={() => {
                const nextVal = !sduiPrivileges?.devToolsProtection;
                updateSduiPrivileges({ devToolsProtection: nextVal });
                if (!nextVal) {
                  resetSecurityLock();
                }
              }}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                border: 'none',
                background: sduiPrivileges?.devToolsProtection ? '#f59e0b' : '#64748b',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              {sduiPrivileges?.devToolsProtection ? 'Active' : 'Off'}
            </button>
          </div>
        </div>
      </div>

      {/* Two-Column Section: SDUI Payload Contract & Architecture */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '20px' }}>
        {/* SDUI Config JSON Viewer */}
        <div style={{
          background: 'var(--surface-color)',
          border: '1px solid var(--border-color)',
          borderRadius: '14px',
          padding: '20px',
          boxShadow: '0 4px 20px var(--shadow-color)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Code2 size={16} color="var(--primary-color)" />
              <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--text-color)' }}>
                Live Backend SDUI Configuration JSON
              </h4>
            </div>
            <select
              value={sduiRole}
              onChange={(e) => {
                setSduiRole(e.target.value);
                if (e.target.value === 'citizen') {
                  setIsSchemaEnabled(false);
                  updateSduiPrivileges({
                    allowTableExport: false,
                    allowCsvExport: false,
                    allowExcelExport: false,
                    allowCopyTable: false,
                    copyProtection: true,
                  });
                } else {
                  setIsSchemaEnabled(true);
                  updateSduiPrivileges({
                    allowTableExport: true,
                    allowCsvExport: true,
                    allowExcelExport: true,
                    allowCopyTable: true,
                    copyProtection: true,
                  });
                }
              }}
              style={{
                padding: '4px 8px',
                borderRadius: '6px',
                background: 'var(--input-bg)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-color)',
                fontSize: '12px',
                outline: 'none'
              }}
            >
              <option value="admin">Role: Admin (All Tabs + Exports)</option>
              <option value="citizen">Role: Citizen (Curated + Restricted)</option>
            </select>
          </div>

          <pre style={{
            background: '#030712',
            color: '#a7f3d0',
            padding: '16px',
            borderRadius: '10px',
            fontSize: '12px',
            lineHeight: '1.5',
            overflowX: 'auto',
            margin: 0,
            border: '1px solid rgba(255, 255, 255, 0.08)'
          }}>
            {JSON.stringify(sduiConfigPayload, null, 2)}
          </pre>
        </div>

        {/* Feature Highlights & API Request Contract */}
        <div style={{
          background: 'var(--surface-color)',
          border: '1px solid var(--border-color)',
          borderRadius: '14px',
          padding: '20px',
          boxShadow: '0 4px 20px var(--shadow-color)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={16} color="#c084fc" />
            <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--text-color)' }}>
              Backend Layer API Contract Details
            </h4>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <strong style={{ color: 'var(--primary-color)' }}>1. Curated vs Schema Layer Tabs:</strong>
              <div style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                Positioned cleanly above the chat history search & New Chat button on the left sidebar.
              </div>
            </div>

            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <strong style={{ color: '#10b981' }}>2. Table Export & Copy Gating:</strong>
              <div style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                Download CSV, Excel, and Copy buttons below tables only appear if the user role has export permissions in SDUI configuration.
              </div>
            </div>

            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <strong style={{ color: '#f87171' }}>3. Content Copy & DevTools Protection:</strong>
              <div style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                Prevents text selection, intercepts copy shortcuts (Ctrl+C), context menus, F12, and displays screenshot & security warnings.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PortalApp() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const { lockApp, remainingFormatted } = useAccessKey();

  return (
    <ChatbotProvider>
      <div style={{
        minHeight: '100vh',
        background: 'radial-gradient(1000px circle at 50% -250px, rgba(59, 130, 246, 0.2), transparent 60%), linear-gradient(180deg, var(--background-color), #040913)',
        color: 'var(--text-color)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        padding: '24px 32px',
        boxSizing: 'border-box'
      }}>
        {/* Top Header Bar */}
        <header style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingBottom: '20px',
          borderBottom: '1px solid var(--border-color)',
          marginBottom: '28px',
          maxWidth: '1200px',
          margin: '0 auto 28px auto',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, var(--primary-color), #6366f1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              color: '#fff',
              fontSize: '18px',
              boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
            }}>
              P
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Production Enterprise Portal</h2>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>AP Citizen 360 Knowledge & Analytics</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {/* 30-min Access Key Session Monitor & Lock Button */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              borderRadius: '8px',
              background: 'rgba(30, 58, 138, 0.25)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              fontSize: '12px',
              color: '#93c5fd'
            }}>
              <Clock size={13} color="#60a5fa" />
              <span>Session: <strong>{remainingFormatted}</strong></span>
              <button
                onClick={lockApp}
                title="Lock Portal (Requires Access Key)"
                style={{
                  background: 'rgba(239, 68, 68, 0.2)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  color: '#fca5a5',
                  borderRadius: '5px',
                  padding: '2px 7px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'all 0.2s ease'
                }}
              >
                <Lock size={10} />
                Lock
              </button>
            </div>

            <nav style={{ display: 'flex', gap: '8px' }}>
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
                    fontSize: '13px',
                    textTransform: 'capitalize',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {tab}
                </button>
              ))}
            </nav>
          </div>
        </header>

        {/* Main Dashboard / Route View */}
        <main>
          <PortalDashboard activeTab={activeTab} setActiveTab={setActiveTab} />
        </main>

        {/* Standalone Chatbot Widget */}
        <Chatbot />
      </div>
    </ChatbotProvider>
  );
}

function App() {
  return (
    <AccessKeyGate>
      <PortalApp />
    </AccessKeyGate>
  );
}

export default App;
