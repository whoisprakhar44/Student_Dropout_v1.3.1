/**
 * Chatbot Constants & Configuration
 */

export const STORAGE_KEYS = {
  SESSIONS: 'chatbot_widget_sessions',
  ACTIVE_SESSION_ID: 'chatbot_widget_active_session_id',
  VIEW_MODE: 'chatbot_widget_view_mode', // 'closed' | 'mini' | 'fullscreen'
  UNREAD_COUNT: 'chatbot_widget_unread_count',
  SUGGESTIONS_CACHE: 'chatbot_suggestions_cache',
  SUGGESTIONS_UPDATED_AT: 'chatbot_suggestions_updated_at',
  SUGGESTIONS_DISABLED: 'chatbot_suggestions_disabled',
  SUGGESTION_LAYOUT: 'chatbot_suggestion_layout',
  USER_INFO: 'userInfo',
  AUTH_TOKEN: 'token',
};

export const SUGGESTION_LAYOUTS = {
  HORIZONTAL: 'horizontal',
  VERTICAL: 'vertical',
};

export const SUGGESTION_DEFAULTS = {
  LAYOUT: 'horizontal',
  DEBOUNCE_MS: 2000,
  MIN_CHARS: 3,
  MAX_ITEMS: 5,
  PREFIX_WEIGHT: 3.0,
  SUBSTRING_WEIGHT: 1.5,
  TOKEN_WEIGHT: 1.0,
  SEMANTIC_WEIGHT: 0.8,
};

export const VIEW_MODES = {
  CLOSED: 'closed',
  MINI: 'mini',
  FULLSCREEN: 'fullscreen',
};

export const ROLES = {
  USER: 'user',
  ASSISTANT: 'assistant',
};

export const TRANSPORT_MODES = {
  AUTO: 'auto',
  WEBSOCKET: 'websocket',
  HTTP: 'http',
};

export const WS_CONNECTION_STATUS = {
  DISCONNECTED: 'disconnected',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  ERROR: 'error',
  FALLBACK_HTTP: 'fallback_http',
};

export const PLANNER_STEPS = {
  QUEUED: 'queued',
  WORKER_ASSIGNED: 'worker_assigned',
  GUARDRAIL_CHECK: 'guardrail_check',
  GENERATING_SQL: 'generating_sql',
  FORMATTING: 'formatting',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  BLOCKED: 'guardrail_blocked',
  FAILED: 'failed',
};

export const DEFAULT_BOT_INFO = {
  name: 'AP Citizen 360 AI Assistant',
  status: 'Online',
  subtitle: 'Always here to help you navigate',
};

export const INITIAL_WELCOME_MESSAGE = {
  id: 'msg_welcome_initial',
  role: ROLES.ASSISTANT,
  content: 'Hello! 👋 Welcome to AP Citizen 360 AI Assistant.\nPlease ask your question regarding the Citizen 360 database or policy documents in short.',
  timestamp: new Date().toISOString(),
};

