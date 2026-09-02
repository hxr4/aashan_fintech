export type CaptureSource = "phone_ambient" | "kit_dual_channel" | "browser_meeting" | "hybrid_meeting" | "approved_import" | "speaker_repeat";

export type MicrophoneChannelStatus = "unpaired" | "pairing" | "ready" | "degraded" | "disconnected" | "disabled";

export interface SubscriberMicrophoneKit {
  id: string;
  label: string;
  plan: "annual_prepaid";
  paired: boolean;
  batteryPercent: number;
  speakerChannel: { label: string; status: MicrophoneChannelStatus; batteryPercent: number };
  audienceChannel: { label: string; status: MicrophoneChannelStatus; batteryPercent: number };
  firmware: string;
  lastReceipt?: string;
}

export type SessionState =
  | "draft"
  | "consent_required"
  | "offline_ready"
  | "capturing_offline"
  | "queued_locally"
  | "syncing"
  | "sync_degraded"
  | "synced_pending_ai"
  | "review"
  | "purge_pending"
  | "purged"
  | "purge_failed";

export type ConsentStatus = "pending" | "granted" | "declined" | "withdrawn";

export type QueueStatus = "queued" | "uploading" | "acknowledged" | "failed" | "gap";

export interface GuestScope {
  token: string;
  sessionCode: string;
  expiresAt: string;
  actions: Array<"read_notice" | "consent" | "withdraw" | "private_question" | "view_shared_outcomes" | "save_to_list">;
}

export interface Participant {
  id: string;
  name: string;
  role: "host" | "speaker" | "audience" | "guest";
  consent: ConsentStatus;
  isMinor: boolean;
  joinedAt?: string;
}

export interface AudioChunk {
  id: string;
  sequenceNo: number;
  source: CaptureSource;
  startedAt: string;
  endedAt: string;
  sha256: string;
  consentVersion: string;
  status: QueueStatus;
  correlationId?: string;
  receiptLabel?: string;
}

export interface EvidenceSegment {
  id: string;
  chunkId: string;
  startedAt: string;
  endedAt: string;
  text: string;
  confidence: number;
  gap: boolean;
}

export interface LiveEventEntry {
  id: string;
  evidenceId?: string;
  chunkId?: string;
  startedAt: string;
  endedAt?: string;
  originalText: string;
  currentText: string;
  confidence: number;
  source: "speaker" | "audience" | "host_note" | "system";
  sourceMedium?: CaptureSource;
  editCount: number;
  editHistory: Array<{ editedAt: string; editedBy: string; previousText: string; nextText: string }>;
  gap: boolean;
}

export interface WorkflowItem {
  id: string;
  proposalId?: string;
  title: string;
  owner: string;
  dueDate: string;
  status: "proposed" | "confirmed" | "in_progress" | "done" | "blocked";
  evidenceIds: string[];
  editCount: number;
  editHistory: Array<{ editedAt: string; editedBy: string; changedFields: string[] }>;
}

export interface LiveChatMessage {
  id: string;
  author: string;
  role: "participant" | "host" | "assistant" | "system";
  text: string;
  createdAt: string;
  evidenceIds: string[];
  private: boolean;
  status: "sent" | "uncertain" | "blocked";
}

export interface Proposal {
  id: string;
  kind: "decision" | "commitment" | "risk" | "memory";
  text: string;
  confidence: number;
  evidenceIds: string[];
  status: "proposed" | "confirmed" | "rejected" | "disputed" | "redacted";
}

export interface AuditEvent {
  id: string;
  type: string;
  createdAt: string;
  actor: string;
  correlationId: string;
  detail: string;
}

export interface MeetingSession {
  id: string;
  code: string;
  title: string;
  purpose: string;
  source: CaptureSource;
  state: SessionState;
  consentVersion: string;
  privacyMode: "standard" | "speaker_repeat";
  retentionEndsAt: string;
  participants: Participant[];
  queue: AudioChunk[];
  evidence: EvidenceSegment[];
  liveEntries: LiveEventEntry[];
  workflows: WorkflowItem[];
  chat: LiveChatMessage[];
  proposals: Proposal[];
  audit: AuditEvent[];
}

export interface AttendeeAllowance {
  plan: "free" | "personal" | "education";
  questionCreditsRemaining: number;
  noteCreditsRemaining: number;
  personalNotes: Array<{ id: string; text: string; createdAt: string; evidenceIds: string[] }>;
}

export type MeetingOrigin = "phone_capture" | "qr_guest_save" | "browser_handoff" | "approved_import" | "workspace_share";

export interface LibraryMeetingItem {
  id: string;
  title: string;
  occurredAt: string;
  origin: MeetingOrigin;
  accessRule: string;
  availability: "recording" | "review_ready" | "shared_outcome" | "available" | "removed";
  summary: string;
  retentionNote: string;
}
