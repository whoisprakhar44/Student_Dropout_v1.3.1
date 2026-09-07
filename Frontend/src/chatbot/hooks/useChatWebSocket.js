import { useState, useEffect, useCallback, useRef } from 'react';
import { chatWebSocketService } from '../services/chatWebSocketService';
import { WS_CONNECTION_STATUS } from '../constants/chatbotConstants';

/**
 * React hook for consuming Chat WebSocket connection and streaming state
 */
export function useChatWebSocket() {
  const [connectionStatus, setConnectionStatus] = useState(chatWebSocketService.status);
  const [currentStep, setCurrentStep] = useState(null);
  const activeRequestIdRef = useRef(null);

  useEffect(() => {
    // 1. Subscribe to status changes
    const unsubStatus = chatWebSocketService.onStatusChange((status) => {
      setConnectionStatus(status);
    });

    // 2. Subscribe to progress events
    const unsubProgress = chatWebSocketService.onPlannerProgress((event) => {
      setCurrentStep(event);
    });

    // 3. Auto connect on mount
    chatWebSocketService.connect();

    return () => {
      unsubStatus();
      unsubProgress();
    };
  }, []);

  const isConnected = connectionStatus === WS_CONNECTION_STATUS.CONNECTED;

  const ask = useCallback(async ({ question, sessionId, username, requestId, onProgress, signal }) => {
    activeRequestIdRef.current = requestId;
    try {
      const response = await chatWebSocketService.ask({
        question,
        sessionId,
        username,
        requestId,
        onProgress: (prog) => {
          setCurrentStep(prog);
          if (onProgress) onProgress(prog);
        },
        signal,
      });
      return response;
    } finally {
      setCurrentStep(null);
      activeRequestIdRef.current = null;
    }
  }, []);

  const cancelQuery = useCallback(async (targetRequestId) => {
    const reqId = targetRequestId || activeRequestIdRef.current;
    if (!reqId) return null;
    return await chatWebSocketService.cancel(reqId);
  }, []);

  const fetchHistory = useCallback((username) => {
    return chatWebSocketService.getHistory(username);
  }, []);

  const fetchSession = useCallback((sessionId, username) => {
    return chatWebSocketService.getSessionHistory(sessionId, username);
  }, []);

  const deleteSession = useCallback((sessionId, username) => {
    return chatWebSocketService.deleteSession(sessionId, username);
  }, []);

  const clearAllHistory = useCallback((username) => {
    return chatWebSocketService.clearAllHistory(username);
  }, []);

  const fetchSuggestions = useCallback((limit = 50) => {
    return chatWebSocketService.getSuggestions(limit);
  }, []);

  const renderChart = useCallback((chartType, data) => {
    return chatWebSocketService.renderChart(chartType, data);
  }, []);

  return {
    connectionStatus,
    isConnected,
    currentStep,
    connect: () => chatWebSocketService.connect(),
    disconnect: () => chatWebSocketService.disconnect(),
    ask,
    cancelQuery,
    fetchHistory,
    fetchSession,
    deleteSession,
    clearAllHistory,
    fetchSuggestions,
    renderChart,
  };
}

export default useChatWebSocket;
