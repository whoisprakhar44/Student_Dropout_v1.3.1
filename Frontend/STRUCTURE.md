# Chatbot Package Folder & File Structure (`STRUCTURE.md`)

This document details the clean, modular folder architecture and the exact purpose of every component, hook, service, utility, constant, and style file in the Chatbot package.

```
src/
 └── chatbot/
      ├── Chatbot.jsx
      ├── ChatbotProvider.jsx
      │
      ├── hooks/
      │    ├── useChatbot.js
      │    ├── useSpeechRecognition.js
      │    ├── useSuggestions.js
      │
      ├── components/
      │    ├── FloatingChatButton.jsx
      │    ├── MiniChatWindow.jsx
      │    ├── FullScreenChat.jsx
      │    ├── ChatHeader.jsx
      │    ├── ChatMessage.jsx
      │    ├── ChatInput.jsx
      │    ├── ChatSuggestions.jsx
      │    ├── ChatTable.jsx
      │    ├── ChatHistorySidebar.jsx
      │    ├── LoadingAnimation.jsx
      │
      ├── services/
      │    ├── chatbotApi.js
      │    ├── chatStorage.js
      │    ├── suggestionsService.js
      │    ├── indexedDbService.js
      │
      ├── utils/
      │    ├── vectorMath.js
      │
      ├── constants/
      │    ├── chatbotConstants.js
      │
      ├── styles/
           ├── chatbot.css
```

---

## File Breakdown & Module Documentation

### 1. Root Orchestrator
- **`src/chatbot/Chatbot.jsx`**
  - **Purpose**: Main entry point component for the chatbot widget package. Imports `chatbot.css` and conditionally renders `FloatingChatButton`, `MiniChatWindow` (when view mode is `'mini'`), or `FullScreenChat` (when view mode is `'fullscreen'`).

- **`src/chatbot/ChatbotProvider.jsx`**
  - **Purpose**: React Context Provider maintaining all global chatbot state (active sessions, current messages, view mode, unread count badge, loading states). Persists data automatically to `localStorage` and exposes context methods to the application.

---

### 2. Custom React Hooks (`hooks/`)
- **`src/chatbot/hooks/useChatbot.js`**
  - **Purpose**: Custom React hook exposing the `ChatbotContext`. Used by components to send messages, toggle view modes, clear history, or select active sessions.

- **`src/chatbot/hooks/useSpeechRecognition.js`**
  - **Purpose**: Custom hook interfacing with the browser Web Speech API (`window.SpeechRecognition` / `window.webkitSpeechRecognition`). Handles voice dictation, prevents word duplication, tracks browser support, and automatically stops recording after 3 seconds of user speech inactivity.

- **`src/chatbot/hooks/useSuggestions.js`**
  - **Purpose**: Custom hook for real-time question suggestions and hybrid ranking. Debounces typing for 2 seconds (`VITE_SUGGESTION_DEBOUNCE_MS`), enforces minimum 3 characters, and computes composite scores combining 768-dim Vector Cosine Similarity, prefix matching, substring matching, and token overlap.

---

### 3. UI Components (`components/`)
- **`src/chatbot/components/FloatingChatButton.jsx`**
  - **Purpose**: Circular action button fixed at the bottom-right of the viewport. Features scale hover transitions, unread message count badge, open/close toggle logic, and keyboard accessibility.

- **`src/chatbot/components/MiniChatWindow.jsx`**
  - **Purpose**: Compact floating chat panel (~380px width x 580px height). Renders header bar, scrollable message container with auto-scroll to bottom, loading indicator, and chat input.

- **`src/chatbot/components/FullScreenChat.jsx`**
  - **Purpose**: High-impact full screen overlay layout. Combines top header bar, left history sidebar (`ChatHistorySidebar`), main message stream, auto-scroll, and rounded bottom chat input.

- **`src/chatbot/components/ChatSuggestions.jsx`**
  - **Purpose**: Renders glassmorphic transparent bubble chips above the chat input. Supports Horizontal (carousel) or Vertical (stacked) layouts, chip click to edit in input field, quick direct send button (`ArrowUpRight`), and dismiss/disable controls.

- **`src/chatbot/components/ChatTable.jsx`**
  - **Purpose**: Structured tabular SQL execution results renderer. Supports client-side filtering, CSV export, Excel (`.xls`) export, copy to clipboard, and responsive scroll container.

- **`src/chatbot/components/ChatHeader.jsx`**
  - **Purpose**: Top bar component displaying bot avatar, online status indicator, bot title, clear chat button, fullscreen toggle button, and window close button.

- **`src/chatbot/components/ChatMessage.jsx`**
  - **Purpose**: Individual message bubble rendering. Formats alignment (User right, Assistant left), message content, tabular results, summaries, and timestamps.

- **`src/chatbot/components/ChatInput.jsx`**
  - **Purpose**: Multi-line rounded text area input (`24px` border radius). Embeds `ChatSuggestions`, handles keyboard events (`Enter` to submit, `Shift+Enter` for newline), disabled states while loading, and microphone dictation.

- **`src/chatbot/components/ChatHistorySidebar.jsx`**
  - **Purpose**: Fullscreen mode sidebar allowing users to search past conversations, create new chat sessions, view session titles, timestamps, message counts, select active sessions, or delete sessions. Includes a footer with version display (from `VITE_CHATBOT_VERSION`) and a Settings gear modal for switching suggestion layouts (Horizontal vs. Vertical) and clearing conversation data.

- **`src/chatbot/components/LoadingAnimation.jsx`**
  - **Purpose**: Animated 3-dot bouncing indicator rendered while the assistant response is generating, featuring an in-flight query cancellation button.

---

### 4. Service Layer (`services/`)
- **`src/chatbot/services/chatbotApi.js`**
  - **Purpose**: API service layer integrating with the unified `/ask` multiplexed backend endpoint according to `API_CONTRACT.md`. Sends mandatory `Authorization: Bearer <token>` headers, extracts dynamic usernames, and executes actions (`ask`, `cancel`, `history`, `history_session`, `delete_session`, `clear_history`).

- **`src/chatbot/services/chatStorage.js`**
  - **Purpose**: Safe `localStorage` utility for persisting sessions, active session ID, view mode, unread counts, suggestion layout preferences, auth token extraction, and username resolution from `localStorage('userInfo')`.

- **`src/chatbot/services/suggestionsService.js`**
  - **Purpose**: Manages question suggestions cache lifecycle: calls `GET /suggestions/meta`, verifies timestamps, loads from IndexedDB (0 KB download on hit), fetches `GET /suggestions?limit=-1` (or POST fallback) on miss, and fetches query vectors.

- **`src/chatbot/services/indexedDbService.js`**
  - **Purpose**: High-capacity IndexedDB storage for storing hundreds of 768-dimensional float embedding vectors alongside question metadata without hitting browser quota limits.

---

### 5. Utility Layer (`utils/`)
- **`src/chatbot/utils/vectorMath.js`**
  - **Purpose**: Vector mathematics engine. Computes Euclidean norms, vector normalization, 768-dim dot-product Cosine Similarity, and fallback semantic affinity scoring.

---

### 6. Constants & Configuration (`constants/`)
- **`src/chatbot/constants/chatbotConstants.js`**
  - **Purpose**: Central configuration tokens, storage keys (`SUGGESTIONS_CACHE`, `SUGGESTIONS_UPDATED_AT`, `SUGGESTIONS_DISABLED`, etc.), view modes, layouts, and default ranking weights.

---

### 7. Design & Styling (`styles/`)
- **`src/chatbot/styles/chatbot.css`**
  - **Purpose**: Central CSS stylesheet for the chatbot package. Strictly consumes parent CSS variables without hardcoded color values. Includes glassmorphic styles, keyframe pulse animations, horizontal & vertical suggestion list styles, custom scrollbars, and mobile responsive overrides.
