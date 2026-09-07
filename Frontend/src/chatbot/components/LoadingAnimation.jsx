import React from 'react';
import { XCircle, Loader2, Database, ShieldCheck, Sparkles, ListOrdered, Cpu } from 'lucide-react';
import { useChatbot } from '../hooks/useChatbot';
import { PLANNER_STEPS } from '../constants/chatbotConstants';

export const LoadingAnimation = () => {
  const { cancelCurrentRequest, activeProgress } = useChatbot();

  const getStepDetails = (progress) => {
    if (!progress || !progress.step) {
      return {
        label: 'Generating response...',
        icon: Loader2,
        isSpinning: true,
      };
    }

    const step = progress.step;
    const msg = progress.message;

    switch (step) {
      case PLANNER_STEPS.QUEUED:
        return {
          label: progress.queuePosition ? `Enqueued (Position #${progress.queuePosition})` : (msg || 'Waiting in execution queue...'),
          icon: ListOrdered,
          isSpinning: false,
          badge: progress.queuePosition ? `#${progress.queuePosition}` : null,
        };
      case PLANNER_STEPS.WORKER_ASSIGNED:
        return {
          label: msg || 'Worker assigned, starting analysis...',
          icon: Cpu,
          isSpinning: true,
        };
      case PLANNER_STEPS.GUARDRAIL_CHECK:
        return {
          label: msg || 'Validating query policy & safety...',
          icon: ShieldCheck,
          isSpinning: false,
        };
      case PLANNER_STEPS.GENERATING_SQL:
        return {
          label: msg || 'Synthesizing SQL & reasoning...',
          icon: Database,
          isSpinning: true,
        };
      case PLANNER_STEPS.FORMATTING:
        return {
          label: msg || 'Formatting tabular results & summary...',
          icon: Sparkles,
          isSpinning: true,
        };
      default:
        return {
          label: msg || 'Processing query...',
          icon: Loader2,
          isSpinning: true,
        };
    }
  };

  const stepInfo = getStepDetails(activeProgress);
  const IconComponent = stepInfo.icon;

  return (
    <div className="cb-message-row assistant">
      <div className="cb-loading-container" aria-label="Assistant is processing query">
        {activeProgress ? (
          <div className="cb-planner-progress-wrap">
            <div className="cb-planner-step-icon">
              <IconComponent size={15} className={stepInfo.isSpinning ? 'cb-icon-spin' : ''} />
            </div>
            <span className="cb-planner-step-label">{stepInfo.label}</span>
          </div>
        ) : (
          <div className="cb-dots-wrap">
            <div className="cb-dot" />
            <div className="cb-dot" />
            <div className="cb-dot" />
          </div>
        )}

        {cancelCurrentRequest && (
          <button
            type="button"
            className="cb-cancel-request-btn"
            onClick={cancelCurrentRequest}
            title="Cancel this query"
            aria-label="Cancel request"
          >
            <XCircle size={14} />
            <span>Cancel</span>
          </button>
        )}
      </div>
    </div>
  );
};

export default LoadingAnimation;
