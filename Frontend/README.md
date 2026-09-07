# Standalone Reusable React Chatbot Widget

A production-ready, highly customizable, reusable React Chatbot Widget package designed to be mounted once in a React application's root layout, `App` component, or global wrapper. The chatbot floats above all pages/routes, maintaining its state across navigation and browser reloads.

---

## Features

- **Backend API Integration (`POST /ask`)**: Seamless integration with the unified `/ask` multiplexed endpoint according to [`API_CONTRACT.md`](./API_CONTRACT.md).
- **Mandatory Bearer Authentication**: Passes `Authorization: Bearer <token>` with every backend request, resolved automatically from `localStorage("userInfo")` or token storage keys.
- **Dynamic Username Resolution**: Automatically reads username from `JSON.parse(localStorage.getItem("userInfo")).username` (defaulting to `"Test User"`).
- **Server-Driven Chat Sessions & History**: Synchronizes conversations directly from the backend on mount (`action: "history"`, `action: "history_session"`), with session deletion (`action: "delete_session"`) and clearing (`action: "clear_history"`).
- **Query Request Cancellation**: Supports aborting in-flight NL-to-SQL generation and sends cancellation signal to the backend (`action: "cancel"`).
- **Sidebar Footer & Version Info**: Displays live version tag (`VITE_CHATBOT_VERSION`) at the bottom of the conversation history.
- **Settings Modal (Gear Icon)**: Provides a settings control in the sidebar footer enabling users to switch between **Horizontal** pills carousel and **Vertical** stacked list suggestion layouts, with persistent local preferences.
- **Floating Action Button**: Always visible bottom-right icon with unread message badge and smooth micro-animations.
- **Mini Chat Panel**: Compact floating window (width: ~380px, height: ~580px) with header status indicator, scrollable messages, auto-scroll, and loading state.
- **Full Screen Overlay Mode**: High-impact overlay with session history sidebar, instant session search, date timestamps, message counts, and chat session management.
- **Client-Side Suggestions & Fewshots Cache**:
  - Automatic `GET /suggestions/meta` timestamp check on mount.
  - Zero-download instant loading from `IndexedDB` / `localStorage` when server cache timestamp matches.
  - Fast synchronization when cache is missing or outdated.
- **Real-Time Vector Semantic & Hybrid Ranking**:
  - Automatically triggers ranking when the user pauses typing for **2 seconds** (`VITE_SUGGESTION_DEBOUNCE_MS=2000`) with at least **3 characters** (`VITE_SUGGESTION_MIN_CHARS=3`).
  - Computes composite scores combining **768-dimensional Vector Cosine Similarity**, sentence/word **Prefix matching**, **Substring matching**, and **Token overlap**.
  - Highly configurable ranking weights via `.env` variables (e.g. 80% semantic + 20% prefix).
- **Interactive Suggestion Bubbles (Horizontal / Vertical)**:
  - Supports configurable **Horizontal** pill carousel or **Vertical** stacked list layout via `VITE_SUGGESTION_LAYOUT` and live in-app Settings switcher.
  - Glassmorphic transparent bubbles strictly consuming parent CSS variables.
  - **Fill & Edit**: Clicking a suggestion bubble fills the input field and focuses the textarea.
  - **Quick Send**: Direct 1-click execution via top-right arrow button on each chip.
  - **Dismiss / Disable Controls**: Small cross (`X`) and disable (`EyeOff`) buttons with hover tooltips.
- **SQL Tabular Data & Multi-Query Tuples**: Automatically detects and renders tabular query results with scrollable views, sticky headers, and row search filters.
- **Download CSV & Excel**: Provides one-click **Download CSV** and **Download Excel** (`.xls`) file export buttons at the bottom of tabular chat responses.
- **Inline Plain-Text Summaries**: Displays text summaries naturally within the chat bubble response without callout card borders.
- **Speech Inactivity Auto-Stop**: Automatically turns off microphone recording and active pulse animation after **3 seconds** of speech inactivity.
- **Graceful Browser Fallback**: Automatically hides the microphone button in browsers that do not support Web Speech API.
- **State Persistence**: React Context Provider + `localStorage` and `IndexedDB` preserves active session, vector embeddings, view mode, message history, and unread counts.
- **Pure CSS Variable Theme**: Styled exclusively using CSS custom properties (`var(--primary-color)`, `var(--background-color)`, etc.) without hardcoded colors.

---

## Quick Start & Mount Instructions

### 1. Package Installation

#### Option A: Install All Project Dependencies (Recommended)
If setting up the repository:
```bash
npm install
```

#### Option B: Direct Package Installation Commands

Install all required production runtime packages:
```bash
npm install react react-dom lucide-react recharts html2canvas
```

Install development dependencies:
```bash
npm install -D vite @vitejs/plugin-react @types/react @types/react-dom
```

#### Package Breakdown & Usage

| Package | Type | Command | Purpose in Project |
|---|---|---|---|
| **`react`** | Runtime | `npm install react` | Core React library for components, state, context, and hooks. |
| **`react-dom`** | Runtime | `npm install react-dom` | React DOM rendering engine to mount the widget. |
| **`lucide-react`** | Runtime | `npm install lucide-react` | Modern icon library used for buttons, sidebar, microphone, search, table actions, and suggestions. |
| **`recharts`** | Runtime | `npm install recharts` | Dynamic charting library used in `ChatCharts.jsx` (Bar, Line, Pie, Area charts for query data). |
| **`html2canvas`** | Runtime | `npm install html2canvas` | Canvas snapshot generator used in `ChatCharts.jsx` for downloading charts as PNG images. |
| **`vite`** | Dev | `npm install -D vite` | Fast development server and production bundler. |
| **`@vitejs/plugin-react`** | Dev | `npm install -D @vitejs/plugin-react` | Vite plugin providing React Fast Refresh and JSX transformation. |
| **`@types/react`** | Dev | `npm install -D @types/react` | Type definitions and IDE autocompletion for React. |
| **`@types/react-dom`** | Dev | `npm install -D @types/react-dom` | Type definitions and IDE autocompletion for React DOM. |

---

### 2. Available Scripts

Run the project locally or build for production:

```bash
# Start local development server (http://localhost:5173)
npm run dev

# Build optimized production bundle to /dist
npm run build

# Preview production build locally
npm run preview
```

---

### 3. Mounting the Widget


Import `ChatbotProvider` and `Chatbot` into your main `App.jsx` or root layout wrapper:

```jsx
import React from 'react';
import { ChatbotProvider } from './chatbot/ChatbotProvider';
import Chatbot from './chatbot/Chatbot';

function App() {
  return (
    <div>
      {/* Your main application content */}
      <MainApplicationRoutes />

      {/* Standalone Chatbot Widget */}
      <ChatbotProvider>
        <Chatbot />
      </ChatbotProvider>
    </div>
  );
}

export default App;
```

---

## Environment Variables (`.env`)

Configure timeouts, suggestions API, layouts, and ranking weights via Vite environment variables:

```env
# Speech Recognition Inactivity Timeout in milliseconds (default: 3000ms = 3s)
VITE_SPEECH_INACTIVITY_TIMEOUT_MS=3000

# Fullscreen Chat Window Gap Percentage around screen edges (default: 3%)
VITE_FULLSCREEN_GAP_PERCENT=3

# Chatbot Backend API Base URL
VITE_CHATBOT_API_URL=http://localhost:8000

# Chatbot Version displayed in history sidebar footer
VITE_CHATBOT_VERSION=v1.0.0

# Suggestions API Configuration
VITE_SUGGESTIONS_API_BASE_URL=
VITE_SUGGESTION_LAYOUT=horizontal
VITE_SUGGESTION_DEBOUNCE_MS=2000
VITE_SUGGESTION_MIN_CHARS=3
VITE_SUGGESTION_MAX_ITEMS=5

# Suggestion Ranking Weights (Prefix, Substring, Token overlap, Semantic)
VITE_SUGGESTION_PREFIX_WEIGHT=3.0
VITE_SUGGESTION_SUBSTRING_WEIGHT=1.5
VITE_SUGGESTION_TOKEN_WEIGHT=1.0
VITE_SUGGESTION_SEMANTIC_WEIGHT=0.8
```

### Environment Variables Reference

| Variable | Type | Default | Description |
|---|---|---|---|
| `VITE_CHATBOT_API_URL` | `string` | `"http://localhost:8000"` | Base URL of the backend API server implementing `/ask`. |
| `VITE_CHATBOT_VERSION` | `string` | `"v1.0.0"` | Version tag displayed at the bottom of the chat history sidebar. |
| `VITE_SUGGESTIONS_API_BASE_URL` | `string` | `""` | Base API URL prefix for suggestions endpoints (e.g. `/api` or `http://localhost:8000`). |
| `VITE_SUGGESTION_LAYOUT` | `string` | `"horizontal"` | Suggestion bubbles orientation: `"horizontal"` (scrollable carousel) or `"vertical"` (stacked list). |
| `VITE_SUGGESTION_DEBOUNCE_MS` | `number` | `2000` | Milliseconds the user must pause typing before computing suggestion rankings. |
| `VITE_SUGGESTION_MIN_CHARS` | `number` | `3` | Minimum character length in input field to activate suggestion search. |
| `VITE_SUGGESTION_MAX_ITEMS` | `number` | `5` | Maximum number of ranked suggestion chips rendered in the UI. |
| `VITE_SUGGESTION_SEMANTIC_WEIGHT` | `number` | `0.8` | Weight multiplier for 768-dim vector Cosine Similarity score. |
| `VITE_SUGGESTION_PREFIX_WEIGHT` | `number` | `3.0` | Weight multiplier for sentence & word prefix matching. |
| `VITE_SUGGESTION_SUBSTRING_WEIGHT` | `number` | `1.5` | Weight multiplier for substring match proximity. |
| `VITE_SUGGESTION_TOKEN_WEIGHT` | `number` | `1.0` | Weight multiplier for token overlap (Jaccard similarity). |
| `VITE_SPEECH_INACTIVITY_TIMEOUT_MS`| `number`| `3000`| Dictation timeout before automatically stopping microphone recording. |
| `VITE_FULLSCREEN_GAP_PERCENT` | `number` | `3` | Margin padding percentage around fullscreen modal view. |

---

## Suggestions API Specification

The chatbot communicates with the following backend contracts:

### 1. Metadata Check (`GET /suggestions/meta`)
Called on app mount to check if the browser cache is current without downloading large vector payloads.
```json
{
  "status": "success",
  "count": 213,
  "updated_at": "2026-08-27T04:02:34.933785+00:00",
  "cache_file": "fewshot_suggestions_cache.json"
}
```

### 2. Full Suggestions Payload (`GET /suggestions?limit=-1` or `POST /suggestions`)
Called only on cache miss or when `updated_at` differs.
```json
{
  "status": "success",
  "count": 213,
  "updated_at": "2026-08-27T04:02:34.933785+00:00",
  "suggestions": [
    {
      "id": "school_dropout_001",
      "question": "Give me class 6 students in Anantapur who dropped out in 2025-26, including school and social category.",
      "intent": "student_risk_list",
      "topic": "dropout_tracking",
      "difficulty": "medium",
      "use_case": "school_dropout",
      "embedding": [-1.0204, -0.3955, -3.0922, "..."] 
    }
  ]
}
```

---

## Browser Back Button Interception

When the chatbot is in **Fullscreen mode**, pressing the browser back button (or swipe back on mobile) will **not** navigate away from the current page. Instead, the widget intercepts the history state and gracefully minimizes the chatbot into **Widget (Mini) mode**.

---

## Consuming the Chatbot Context Hook

You can access chatbot state and methods anywhere in your application tree using `useChatbot()`:

```jsx
import { useChatbot } from './chatbot/hooks/useChatbot';

function CustomHeaderComponent() {
  const {
    messages,
    sessions,
    sendMessage,
    loadSession,
    clearChat,
    isLoading,
    openChat,
    closeChat,
    toggleFullscreen
  } = useChatbot();

  return (
    <button onClick={() => openChat('fullscreen')}>
      Open Help Chat ({messages.length} messages)
    </button>
  );
}
```

---

## Customizing Theme & CSS Variables

The chatbot consumes CSS custom properties from `:root`. You can override these variables in your global CSS stylesheet:

```css
:root {
  --primary-color: #3b82f6;
  --primary-hover: #2563eb;
  --primary-text: #ffffff;
  --background-color: #06101e;
  --surface-color: #0d1c31;
  --surface-hover: #122540;
  --border-color: #244467;
  --text-color: #eef6ff;
  --text-muted: #91a6c5;
  --user-msg-bg: #2563eb;
  --user-msg-text: #ffffff;
  --bot-msg-bg: #102743;
  --bot-msg-text: #eef6ff;
  --input-bg: #071426;
  --status-online: #22c55e;
  --shadow-color: rgba(0, 0, 0, 0.4);
  --accent-glow: rgba(59, 130, 246, 0.35);
  --danger-color: #ef4444;
}
```

---

## Folder Architecture

Refer to [`STRUCTURE.md`](./STRUCTURE.md) for a detailed file-by-file breakdown.
