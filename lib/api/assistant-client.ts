// Phase 6: focused transport layer for karenseir-assistant. Every UI
// component talks to the Assistant through this file only -- no raw
// fetch() calls scattered across components. Mechanically this rides on
// the existing KarenSeirApi (base URL, correlation id, error shape); this
// file only adds Assistant's own response shape and its small amount of
// non-secret, bounded, deterministic resume state.
//
// What is deliberately NOT here: no token. The bearer token lives only in
// KarenSeirApi's session (sessionStorage), attached per-request by
// postOptionalAuth. Nothing in this file ever reads, stores, or forwards
// it directly.
import { ApiError, KarenSeirApi } from './karenseir-client';

export type AssistantEntity = {
  entity_id: string;
  title?: string | null;
  provider_count?: number;
  best_offer?: { offer_id: string; final_price: number; currency: string } | null;
  display_index?: number;
  price?: number | null;
  currency?: string | null;
  vertical?: string;
  reservation?: { id?: string; status?: string; [key: string]: unknown } | null;
  [key: string]: unknown;
};

export type AssistantReadiness = { ready: boolean; missing: string[]; warnings?: string[] };

export type AssistantReplyData = {
  type?: string;
  total?: number;
  result?: { pagination: { total: number }; entities: AssistantEntity[]; plan?: Record<string, unknown> };
  selected?: AssistantEntity;
  item?: AssistantEntity;
  readiness?: AssistantReadiness;
  plan_id?: string;
  pending_approval_id?: string;
  requires_approval?: boolean;
  operation_fingerprint?: string;
  execution_guard?: { allowed: boolean; reason: string | null };
  reservation_result?: { status: string; error_code: string | null; reservation_id?: string; [key: string]: unknown };
  release_result?: { status: string; error_code: string | null };
  revalidation?: { available: boolean; changed: boolean; old_price?: number; new_price?: number };
  escalation?: { customer_visible_status: string; [key: string]: unknown };
  refined?: boolean;
  [key: string]: unknown;
};

export type AssistantTurnResponse = {
  conversation_id: string;
  correlation_id: string;
  turn_id: string;
  action: string;
  intent: string;
  refined: boolean;
  trip_state_id: string | null;
  trip_state_status: string | null;
  message: { role: 'assistant'; text: string; data: AssistantReplyData };
  actions: Array<{ action_id: string; label: string; level: number; requires_approval: boolean }>;
  warnings: string[];
  missing_information: string[];
};

export type AssistantChatMessage = { role: 'user' | 'assistant'; text: string; data?: AssistantReplyData };

const CONV_KEY = 'karenseir-assistant-conversation-id';
const MSG_KEY = 'karenseir-assistant-messages';
const RESUME_KEY = 'karenseir-assistant-resume-pending';
const MAX_STORED_MESSAGES = 30;

// All of this is non-secret: a conversation id (a random UUID Assistant
// itself issued), the visible chat transcript, and a one-byte "we were
// mid-flow when we sent the user to Login" flag. No token, no server
// internals. Bounded to MAX_STORED_MESSAGES so it can never grow unbounded.
export function loadConversationId(): string | null {
  try { return sessionStorage.getItem(CONV_KEY); } catch { return null; }
}

export function saveConversationId(id: string): void {
  try { sessionStorage.setItem(CONV_KEY, id); } catch { /* private mode / storage blocked */ }
}

export function loadStoredMessages(): AssistantChatMessage[] {
  try {
    const raw = sessionStorage.getItem(MSG_KEY);
    return raw ? (JSON.parse(raw) as AssistantChatMessage[]) : [];
  } catch { return []; }
}

export function saveStoredMessages(messages: AssistantChatMessage[]): void {
  try { sessionStorage.setItem(MSG_KEY, JSON.stringify(messages.slice(-MAX_STORED_MESSAGES))); } catch { /* ignore */ }
}

export function markResumePending(): void {
  try { sessionStorage.setItem(RESUME_KEY, '1'); } catch { /* ignore */ }
}

export function consumeResumePending(): boolean {
  try {
    const pending = sessionStorage.getItem(RESUME_KEY) === '1';
    sessionStorage.removeItem(RESUME_KEY);
    return pending;
  } catch { return false; }
}

export function resetAssistantSession(): void {
  try {
    sessionStorage.removeItem(CONV_KEY);
    sessionStorage.removeItem(MSG_KEY);
    sessionStorage.removeItem(RESUME_KEY);
  } catch { /* ignore */ }
}

export async function sendAssistantMessage(api: KarenSeirApi, conversationId: string | null, text: string): Promise<AssistantTurnResponse> {
  return api.postOptionalAuth<AssistantTurnResponse>('/assistant/message', {
    conversation_id: conversationId,
    text,
    public: true,
  });
}

export function assistantErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503) return 'سرویس دستیار سفر موقتاً در دسترس نیست؛ لطفاً کمی بعد دوباره امتحان کنید.';
    return error.message || 'ارتباط با دستیار سفر برقرار نشد.';
  }
  return 'ارتباط با دستیار سفر برقرار نشد؛ اتصال اینترنت را بررسی کنید.';
}

// Ordinal words the Assistant's own classifier recognizes (1st-5th only --
// a real, existing backend limitation, not something introduced here).
export const ASSISTANT_ORDINAL_WORDS = ['اولی', 'دومی', 'سومی', 'چهارمی', 'پنجمی'];

export function selectResultPhrase(displayIndex: number): string | null {
  const word = ASSISTANT_ORDINAL_WORDS[displayIndex - 1];
  return word ? `${word} رو انتخاب کن` : null;
}
