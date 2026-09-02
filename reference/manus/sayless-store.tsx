import React, { createContext, useContext, useMemo, useState } from "react";
import type { AttendeeAllowance, AudioChunk, AuditEvent, CaptureSource, LibraryMeetingItem, LiveChatMessage, MeetingSession, Proposal, SessionState, SubscriberMicrophoneKit, WorkflowItem } from "@/shared/domain";
import { canBeginCapture, capturePolicy, subscriberKitRouting } from "../shared/policy";
import { applyAcknowledgement, canBufferLocalChunk, createLocalChunk, isChunkEligibleForEvidence, pendingChunks } from "../shared/chunk-protocol";

type BillingState = "pilot_eligible" | "demo_checkout" | "demo_payment_success" | "demo_payment_failed" | "demo_refunded" | "demo_chargeback" | "demo_entitlement_active" | "demo_entitlement_expired" | "demo_overage";
type GuestConsent = "pending" | "granted" | "declined" | "withdrawn";

type SayLessContextValue = {
  session: MeetingSession;
  micPermission: boolean;
  preflightReady: boolean;
  networkAvailable: boolean;
  isMinorOrUnverified: boolean;
  guestConsent: GuestConsent;
  guestQuestion: string;
  privateQuestions: string[];
  guestSaved: boolean;
  guestUpgradeStep: "none" | "create_account" | "install_app" | "complete";
  billingState: BillingState;
  landedCost: number;
  subscriberKit: SubscriberMicrophoneKit;
  libraryMeetings: LibraryMeetingItem[];
  setMicPermission: (value: boolean) => void;
  setPreflightReady: (value: boolean) => void;
  setNetworkAvailable: (value: boolean) => void;
  setMinorOrUnverified: (value: boolean) => void;
  markConsentReady: () => void;
  startCapture: () => boolean;
  pauseCapture: () => void;
  recordLocalChunk: (uri?: string | null) => void;
  stopCapture: () => void;
  simulateSync: (withGap?: boolean) => void;
  runSimulatedAi: () => void;
  confirmProposal: (id: string) => void;
  rejectProposal: (id: string) => void;
  disputeProposal: (id: string) => void;
  correctProposal: (id: string) => void;
  redactEvidence: (id: string) => void;
  simulateDelivery: () => void;
  addLiveNote: (text: string) => void;
  editLiveEntry: (id: string, nextText: string) => void;
  sendParticipantChat: (text: string, isPrivate?: boolean) => void;
  askMeetingAssistant: (question: string) => void;
  updateWorkflow: (id: string, patch: Partial<Pick<WorkflowItem, "title" | "owner" | "dueDate" | "status">>) => void;
  confirmWorkflow: (id: string) => void;
  simulatePurge: (shouldFail: boolean) => void;
  setGuestConsent: (value: GuestConsent) => void;
  setGuestQuestion: (value: string) => void;
  submitGuestQuestion: () => void;
  beginGuestSave: () => void;
  completeGuestAccount: () => void;
  completeGuestInstall: () => void;
  setBillingState: (value: BillingState) => void;
  setLandedCost: (value: number) => void;
  pairSubscriberKit: () => void;
  setKitChannelStatus: (channel: "speaker" | "audience", status: SubscriberMicrophoneKit["speakerChannel"]["status"]) => void;
  selectSubscriberKit: () => boolean;
  selectPhoneAmbient: () => void;
  selectBrowserMeeting: () => void;
  selectHybridMeeting: () => void;
  selectApprovedImport: () => void;
  createWorkflowFromChunk: (chunkId: string) => void;
  attendeeAllowance: AttendeeAllowance;
  addPersonalNote: (text: string, evidenceIds?: string[]) => boolean;
  selectAttendeePlan: (plan: AttendeeAllowance["plan"]) => void;
  resetDemo: () => void;
};

const now = () => new Date().toISOString();
const correlation = () => `rcpt_${Math.random().toString(36).slice(2, 9)}`;

function audit(type: string, actor: string, detail: string): AuditEvent {
  return { id: `aud_${Math.random().toString(36).slice(2, 9)}`, type, actor, detail, correlationId: correlation(), createdAt: now() };
}

function seedSession(): MeetingSession {
  const started = new Date(Date.now() - 6 * 60 * 1000).toISOString();
  return {
    id: "ses_demo_2026_0818",
    code: "SL-2026-0818",
    title: "Tuesday project handoff — Demo scenario",
    purpose: "Demo scenario: align delivery ownership, risks, and next actions for an upcoming release.",
    source: "phone_ambient",
    state: "consent_required",
    consentVersion: "notice-v2.0",
    privacyMode: "standard",
    retentionEndsAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    participants: [
      { id: "p_host", name: "Demo organizer", role: "host", consent: "granted", isMinor: false, joinedAt: started },
      { id: "p_speaker", name: "Demo contributor", role: "speaker", consent: "granted", isMinor: false, joinedAt: started },
      { id: "p_guest", name: "Guest participant", role: "guest", consent: "pending", isMinor: false },
    ],
    queue: [],
    evidence: [],
    liveEntries: [
      { id: "live_001", startedAt: started, originalText: "Demo organizer: We need a named owner for the release checklist.", currentText: "Demo organizer: We need a named owner for the release checklist.", confidence: 0.96, source: "speaker", editCount: 0, editHistory: [], gap: false },
      { id: "live_gap_001", startedAt: new Date(Date.now() - 4 * 60 * 1000).toISOString(), originalText: "[Audio gap: 00:22]", currentText: "[Audio gap: 00:22]", confidence: 0, source: "system", editCount: 0, editHistory: [], gap: true },
      { id: "live_002", startedAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(), originalText: "Demo contributor: I can prepare the checklist by Friday if the final copy is ready today.", currentText: "Demo contributor: I can prepare the checklist by Friday if the final copy is ready today.", confidence: 0.91, source: "speaker", editCount: 0, editHistory: [], gap: false },
    ],
    workflows: [
      { id: "wf_001", title: "Prepare release checklist", owner: "Demo contributor", dueDate: "Friday", status: "proposed", evidenceIds: ["live_002"], editCount: 0, editHistory: [] },
    ],
    chat: [
      { id: "chat_system", author: "Say Less", role: "system", text: "Meeting room opened. Responses are limited to permitted evidence and confirmed workflow state.", createdAt: started, evidenceIds: [], private: false, status: "sent" },
    ],
    proposals: [],
    audit: [audit("session_created", "Demo organizer", "Demo scenario created with Phone Ambient single-source capture selected.")],
  };
}

const SayLessContext = createContext<SayLessContextValue | null>(null);

export function SayLessProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<MeetingSession>(seedSession);
  const [micPermission, setMicPermission] = useState(false);
  const [preflightReady, setPreflightReady] = useState(false);
  const [networkAvailable, setNetworkAvailable] = useState(false);
  const [isMinorOrUnverified, setMinorRiskState] = useState(false);
  const [guestConsent, setGuestConsentState] = useState<GuestConsent>("pending");
  const [guestQuestion, setGuestQuestion] = useState("");
  const [privateQuestions, setPrivateQuestions] = useState<string[]>([]);
  const [guestSaved, setGuestSaved] = useState(false);
  const [guestUpgradeStep, setGuestUpgradeStep] = useState<SayLessContextValue["guestUpgradeStep"]>("none");
  const [billingState, setBillingState] = useState<BillingState>("pilot_eligible");
  const [landedCost, setLandedCost] = useState(7600);
  const [subscriberKit, setSubscriberKit] = useState<SubscriberMicrophoneKit>({ id: "kit_sl_00391", label: "Say Less Duo Kit", plan: "annual_prepaid", paired: false, batteryPercent: 78, speakerChannel: { label: "Channel A · Speaker", status: "unpaired", batteryPercent: 82 }, audienceChannel: { label: "Channel B · Audience", status: "unpaired", batteryPercent: 74 }, firmware: "2.4.1" });
  const [attendeeAllowance, setAttendeeAllowance] = useState<AttendeeAllowance>({ plan: "free", questionCreditsRemaining: 3, noteCreditsRemaining: 5, personalNotes: [] });
  const [savedMeetings, setSavedMeetings] = useState<LibraryMeetingItem[]>([
    { id: "mtg_browser_001", title: "New contributor briefing — Demo scenario", occurredAt: "2026-08-17T11:00:00.000Z", origin: "browser_handoff", accessRule: "Host shared outcome view", availability: "shared_outcome", summary: "Demo record: two confirmed decisions and one assigned follow-up.", retentionNote: "Raw browser capture was not used in this prototype." },
    { id: "mtg_import_001", title: "Product research conversation — Demo scenario", occurredAt: "2026-08-14T08:30:00.000Z", origin: "approved_import", accessRule: "Approved workspace import", availability: "available", summary: "Demo record: read-only meeting memory imported with permission.", retentionNote: "Imported source was approved by its workspace owner." },
    { id: "mtg_workspace_001", title: "Release readiness review — Demo scenario", occurredAt: "2026-08-10T09:00:00.000Z", origin: "workspace_share", accessRule: "Workspace owner granted access", availability: "available", summary: "Demo record: human-confirmed checklist and risks.", retentionNote: "Access can be removed by the workspace owner." },
  ]);

  const mutateSession = (transform: (previous: MeetingSession) => MeetingSession) => setSession(transform);
  const appendAudit = (event: AuditEvent) => mutateSession((previous) => ({ ...previous, audit: [event, ...previous.audit] }));

  const markConsentReady = () => {
    mutateSession((previous) => ({
      ...previous,
      state: "offline_ready",
      participants: previous.participants.map((participant) => participant.id === "p_guest" ? { ...participant, consent: "granted" } : participant),
      audit: [audit("consent_gate_passed", "Rhea Shah", "Required participant notice and consent are recorded for this demo session."), ...previous.audit],
    }));
  };

  const setMinorOrUnverified = (value: boolean) => {
    const policy = capturePolicy(value, "phone_ambient");
    setMinorRiskState(value);
    mutateSession((previous) => ({
      ...previous,
      source: policy.source,
      privacyMode: policy.privacyMode,
      audit: [audit("safety_mode_changed", "Rhea Shah", value ? "Minor or unverified classroom declared; Speaker Repeat Mode enforced and audience capture disabled." : "Standard privacy mode restored by the host."), ...previous.audit],
    }));
  };

  const pairSubscriberKit = () => {
    setSubscriberKit((previous) => ({ ...previous, paired: true, lastReceipt: correlation(), speakerChannel: { ...previous.speakerChannel, status: "ready" }, audienceChannel: { ...previous.audienceChannel, status: "ready" } }));
    appendAudit(audit("subscriber_kit_paired", "Rhea Shah", "Subscriber kit pairing receipt recorded for the demo. Hardware transport is simulated in Expo Go."));
  };

  const setKitChannelStatus = (channel: "speaker" | "audience", status: SubscriberMicrophoneKit["speakerChannel"]["status"]) => {
    setSubscriberKit((previous) => channel === "speaker" ? { ...previous, speakerChannel: { ...previous.speakerChannel, status } } : { ...previous, audienceChannel: { ...previous.audienceChannel, status } });
    appendAudit(audit("subscriber_kit_channel_changed", "Rhea Shah", `${channel === "speaker" ? "Speaker" : "Audience"} channel changed to ${status}.`));
  };

  const selectSubscriberKit = () => {
    const route = subscriberKitRouting({ minorOrUnverified: isMinorOrUnverified, speakerReady: subscriberKit.speakerChannel.status === "ready", audienceReady: subscriberKit.audienceChannel.status === "ready" });
    if (!route.allowed) {
      mutateSession((previous) => ({ ...previous, source: route.source, privacyMode: route.source === "speaker_repeat" ? "speaker_repeat" : "standard", audit: [audit("subscriber_kit_routing_blocked", "Say Less", route.reason), ...previous.audit] }));
      return false;
    }
    mutateSession((previous) => ({ ...previous, source: "kit_dual_channel", privacyMode: "standard", audit: [audit("subscriber_kit_routing_selected", "Rhea Shah", "Dual-channel kit routing selected. Channel A is Speaker; Channel B is Audience."), ...previous.audit] }));
    return true;
  };

  const selectPhoneAmbient = () => mutateSession((previous) => ({ ...previous, source: isMinorOrUnverified ? "speaker_repeat" : "phone_ambient", privacyMode: isMinorOrUnverified ? "speaker_repeat" : "standard", audit: [audit("phone_ambient_selected", "Rhea Shah", isMinorOrUnverified ? "Speaker Repeat Mode retained because the safety rule is active." : "Phone Ambient single-source capture selected."), ...previous.audit] }));

  const selectExternalSource = (selected: "browser_meeting" | "hybrid_meeting" | "approved_import") => mutateSession((previous) => {
    const route = capturePolicy(isMinorOrUnverified, selected);
    return { ...previous, source: route.source, privacyMode: route.privacyMode, audit: [audit("capture_source_selected", "Rhea Shah", route.source === "speaker_repeat" ? `${selected.replaceAll("_", " ")} was blocked by the safety rule; Speaker Repeat Mode remains active.` : `${selected.replaceAll("_", " ")} capture source selected. Its source label will remain visible in every receipt.`), ...previous.audit] };
  });
  const selectBrowserMeeting = () => selectExternalSource("browser_meeting");
  const selectHybridMeeting = () => selectExternalSource("hybrid_meeting");
  const selectApprovedImport = () => selectExternalSource("approved_import");

  const createWorkflowFromChunk = (chunkId: string) => mutateSession((previous) => {
    const chunk = previous.queue.find((item) => item.id === chunkId);
    if (!chunk || chunk.status !== "acknowledged") return { ...previous, audit: [audit("chunk_workflow_blocked", "Say Less", "A workflow cannot be drafted from a chunk until its authorized sync receipt is acknowledged."), ...previous.audit] };
    const item: WorkflowItem = { id: `wf_${chunk.id}`, title: `Review evidence from ${chunk.id}`, owner: "Unassigned", dueDate: "Choose date", status: "proposed", evidenceIds: [chunk.id], editCount: 0, editHistory: [] };
    return { ...previous, workflows: previous.workflows.some((workflow) => workflow.id === item.id) ? previous.workflows : [...previous.workflows, item], audit: [audit("chunk_workflow_drafted", "Rhea Shah", `Human workflow draft created from acknowledged chunk ${chunk.id}; confirmation is still required.`), ...previous.audit] };
  });

  const addPersonalNote = (text: string, evidenceIds: string[] = []) => {
    const trimmed = text.trim();
    if (!trimmed || attendeeAllowance.noteCreditsRemaining < 1) return false;
    setAttendeeAllowance((previous) => ({ ...previous, noteCreditsRemaining: previous.noteCreditsRemaining - 1, personalNotes: [{ id: `note_${Math.random().toString(36).slice(2, 8)}`, text: trimmed, createdAt: now(), evidenceIds }, ...previous.personalNotes] }));
    appendAudit(audit("attendee_note_created", "Guest participant", "A personal note was created from permitted meeting content."));
    return true;
  };

  const selectAttendeePlan = (plan: AttendeeAllowance["plan"]) => {
    const questionCredits = plan === "free" ? 3 : plan === "education" ? 60 : 40;
    const noteCredits = plan === "free" ? 5 : plan === "education" ? 100 : 80;
    setAttendeeAllowance((previous) => ({ ...previous, plan, questionCreditsRemaining: Math.max(previous.questionCreditsRemaining, questionCredits), noteCreditsRemaining: Math.max(previous.noteCreditsRemaining, noteCredits) }));
    appendAudit(audit("attendee_plan_simulated", "Guest participant", `Simulated attendee access plan changed to ${plan}; no payment was processed.`));
  };

  const startCapture = () => {
    if (!canBeginCapture({ microphoneGranted: micPermission, preflightReady, state: session.state })) return false;
    mutateSession((previous) => ({ ...previous, state: "capturing_offline", audit: [audit("capture_started", "Rhea Shah", "Explicit local capture started after consent and preflight."), ...previous.audit] }));
    return true;
  };

  const pauseCapture = () => mutateSession((previous) => ({ ...previous, state: "queued_locally", audit: [audit("capture_paused", "Rhea Shah", "Local capture paused; existing chunks remain queued on the device."), ...previous.audit] }));

  const recordLocalChunk = (uri?: string | null) => mutateSession((previous) => {
    if (!canBufferLocalChunk(previous.queue)) {
      return {
        ...previous,
        state: "sync_degraded",
        audit: [audit("queue_storage_limit", "Phone Ambient", "Local demo queue reached its bounded 36-chunk limit. Capture was not extended silently."), ...previous.audit],
      };
    }
    const startedAt = new Date(Date.now() - 5000).toISOString();
    const chunk: AudioChunk = createLocalChunk({ queue: previous.queue, source: previous.source, consentVersion: previous.consentVersion, startedAt, endedAt: now(), correlationId: correlation() });
    return { ...previous, state: "queued_locally", queue: [...previous.queue, chunk], audit: [audit("chunk_queued", previous.source.replaceAll("_", " "), `${chunk.id} captured locally${uri ? " from a microphone recording" : " in the demo queue"}.`), ...previous.audit] };
  });

  const stopCapture = () => mutateSession((previous) => ({ ...previous, state: previous.queue.length ? "queued_locally" : "offline_ready", audit: [audit("capture_stopped", "Rhea Shah", "Capture stopped; raw chunks are awaiting an acknowledged upload."), ...previous.audit] }));

  const simulateSync = (withGap = false) => {
    if (!networkAvailable) return;
    mutateSession((previous) => {
      const outstanding = pendingChunks(previous.queue);
      if (!outstanding.length) {
        return { ...previous, audit: [audit("sync_no_pending_chunks", "Sync service", "No queued, uploading, or retryable chunks were available for an acknowledgement attempt."), ...previous.audit] };
      }
      let queue = previous.queue;
      for (const [index, chunk] of outstanding.entries()) {
        const receipt = applyAcknowledgement(queue, { sequenceNo: chunk.sequenceNo, correlationId: chunk.correlationId, disposition: withGap && index === outstanding.length - 1 ? "gap" : "acknowledged" }, true);
        if (!receipt.accepted) {
          return { ...previous, state: "sync_degraded", audit: [audit("sync_receipt_rejected", "Sync service", `Receipt for sequence ${chunk.sequenceNo} was rejected as ${receipt.reason}; no later chunk was silently accepted.`), ...previous.audit] };
        }
        queue = receipt.queue;
      }
      return {
        ...previous,
        state: withGap ? "sync_degraded" : "synced_pending_ai",
        queue,
        audit: [audit(withGap ? "audio_gap_recorded" : "sync_acknowledged", "Sync service", withGap ? "An explicit terminal gap receipt was recorded in order. No transcript or workflow will be fabricated for that interval." : "Authorized chunks were acknowledged in ascending sequence order."), ...previous.audit],
      };
    });
  };

  const runSimulatedAi = () => mutateSession((previous) => {
    if (previous.state !== "synced_pending_ai") return previous;
    const acknowledged = previous.queue.filter((chunk) => isChunkEligibleForEvidence(chunk, previous.consentVersion));
    if (!acknowledged.length) {
      return { ...previous, state: "sync_degraded", audit: [audit("model_run_blocked", "AI simulation", "No acknowledged, consent-matching chunk is eligible for evidence. AI output was not fabricated."), ...previous.audit] };
    }
    const evidence = [{ id: "ev_001", chunkId: acknowledged[0].id, startedAt: acknowledged[0].startedAt, endedAt: acknowledged[0].endedAt, text: "The beta launch owner will publish the pilot readiness checklist by Friday.", confidence: 0.91, gap: false }];
    const proposal: Proposal = { id: "prop_001", kind: "commitment", text: "Publish the pilot readiness checklist by Friday.", confidence: 0.91, evidenceIds: evidence.map((item) => item.id), status: "proposed" };
    return { ...previous, state: "review", evidence, proposals: [proposal], audit: [audit("model_run_completed", "AI simulation", "Deepgram Nova-3 Multilingual → GPT-5.6 Luna → GPT-5.6 Terra route receipt created from acknowledged, consent-matching chunks. Output is advisory and awaiting human confirmation."), ...previous.audit] };
  });

  const updateProposal = (id: string, status: Proposal["status"], action: string) => mutateSession((previous) => ({ ...previous, proposals: previous.proposals.map((proposal) => proposal.id === id ? { ...proposal, status } : proposal), audit: [audit(action, "Rhea Shah", `Human ${status} proposal ${id}.`), ...previous.audit] }));

  const correctProposal = (id: string) => mutateSession((previous) => ({
    ...previous,
    proposals: previous.proposals.map((proposal) => proposal.id === id ? { ...proposal, text: `${proposal.text.replace(/ \(edited by human\)$/, "")} (edited by human)`, status: "proposed" } : proposal),
    audit: [audit("proposal_corrected", "Rhea Shah", `Human correction recorded for ${id}; the revised version requires confirmation again.`), ...previous.audit],
  }));

  const redactEvidence = (id: string) => mutateSession((previous) => ({
    ...previous,
    evidence: previous.evidence.map((evidence) => evidence.id === id ? { ...evidence, text: "[Redacted by authorized human]" } : evidence),
    audit: [audit("evidence_redacted", "Rhea Shah", `Human redaction applied to evidence ${id}.`), ...previous.audit],
  }));

  const simulateDelivery = () => appendAudit(audit("delivery_preview_created", "Rhea Shah", "Human-reviewed delivery preview created. No external email, chat, or calendar delivery was performed."));

  const addLiveNote = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    mutateSession((previous) => ({
      ...previous,
      liveEntries: [...previous.liveEntries, { id: `live_note_${Math.random().toString(36).slice(2, 8)}`, startedAt: now(), originalText: trimmed, currentText: trimmed, confidence: 1, source: "host_note", sourceMedium: previous.source, editCount: 0, editHistory: [], gap: false }],
      audit: [audit("live_note_added", "Rhea Shah", "Host added a live meeting note to the evidence timeline."), ...previous.audit],
    }));
  };

  const editLiveEntry = (id: string, nextText: string) => {
    const trimmed = nextText.trim();
    if (!trimmed) return;
    mutateSession((previous) => ({
      ...previous,
      liveEntries: previous.liveEntries.map((entry) => entry.id === id ? { ...entry, currentText: trimmed, editCount: entry.editCount + 1, editHistory: [...entry.editHistory, { editedAt: now(), editedBy: "Rhea Shah", previousText: entry.currentText, nextText: trimmed }] } : entry),
      audit: [audit("live_entry_edited", "Rhea Shah", `Human edit recorded for live entry ${id}; original evidence remains preserved.`), ...previous.audit],
    }));
  };

  const sendParticipantChat = (text: string, isPrivate = false) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const message: LiveChatMessage = { id: `chat_${Math.random().toString(36).slice(2, 8)}`, author: isPrivate ? "Guest participant" : "Rhea Shah", role: "participant", text: trimmed, createdAt: now(), evidenceIds: [], private: isPrivate, status: "sent" };
    mutateSession((previous) => ({ ...previous, chat: [...previous.chat, message], audit: [audit(isPrivate ? "private_question_sent" : "meeting_chat_sent", message.author, "Participant communication added to the live meeting room."), ...previous.audit] }));
  };

  const askMeetingAssistant = (question: string) => {
    const trimmed = question.trim();
    if (!trimmed) return;
    if (attendeeAllowance.questionCreditsRemaining < 1) {
      appendAudit(audit("attendee_question_blocked", "Guest participant", "The simulated free question allowance has been used. No assistant response was generated."));
      return;
    }
    setAttendeeAllowance((previous) => ({ ...previous, questionCreditsRemaining: previous.questionCreditsRemaining - 1 }));
    const userMessage: LiveChatMessage = { id: `chat_q_${Math.random().toString(36).slice(2, 8)}`, author: "Rhea Shah", role: "participant", text: trimmed, createdAt: now(), evidenceIds: [], private: false, status: "sent" };
    mutateSession((previous) => {
      const permitted = previous.liveEntries.filter((entry) => !entry.gap && entry.currentText !== "[Redacted by authorized human]");
      const latest = permitted[permitted.length - 1];
      const confirmed = previous.workflows.filter((workflow) => workflow.status === "confirmed" || workflow.status === "in_progress" || workflow.status === "done");
      const answer = latest
        ? `Based on the permitted live evidence: ${latest.currentText}${confirmed.length ? ` Confirmed workflow items: ${confirmed.map((item) => item.title).join("; ")}.` : " No workflow item has been human-confirmed yet."}`
        : "I do not have permitted evidence to answer that. The meeting contains an audio gap or no confirmed evidence for this question.";
      const assistantMessage: LiveChatMessage = { id: `chat_a_${Math.random().toString(36).slice(2, 8)}`, author: "Say Less", role: "assistant", text: answer, createdAt: now(), evidenceIds: latest ? [latest.id] : [], private: false, status: latest ? "sent" : "uncertain" };
      return { ...previous, chat: [...previous.chat, userMessage, assistantMessage], audit: [audit("evidence_bounded_assistant_answer", "Say Less", latest ? "Assistant answer returned with a live-evidence reference." : "Assistant answer blocked from inventing an unsupported response."), ...previous.audit] };
    });
  };

  const updateWorkflow = (id: string, patch: Partial<Pick<WorkflowItem, "title" | "owner" | "dueDate" | "status">>) => mutateSession((previous) => ({
    ...previous,
    workflows: previous.workflows.map((workflow) => workflow.id === id ? { ...workflow, ...patch, editCount: workflow.editCount + 1, editHistory: [...workflow.editHistory, { editedAt: now(), editedBy: "Rhea Shah", changedFields: Object.keys(patch) }] } : workflow),
    audit: [audit("workflow_edited", "Rhea Shah", `Human edited workflow ${id}; previous workflow values remain available in the audit history.`), ...previous.audit],
  }));

  const confirmWorkflow = (id: string) => updateWorkflow(id, { status: "confirmed" });

  const simulatePurge = (shouldFail: boolean) => mutateSession((previous) => ({ ...previous, state: shouldFail ? "purge_failed" : "purged", audit: [audit(shouldFail ? "purge_verification_failed" : "purge_verified", "Lifecycle service", shouldFail ? "Critical: deletion could not be verified; no success receipt was issued." : "Simulated raw-audio purge verified; non-audio audit receipts remain."), ...previous.audit] }));

  const setGuestConsent = (value: GuestConsent) => {
    setGuestConsentState(value);
    mutateSession((previous) => ({ ...previous, participants: previous.participants.map((participant) => participant.id === "p_guest" ? { ...participant, consent: value === "granted" ? "granted" : value === "withdrawn" ? "withdrawn" : "declined" } : participant), audit: [audit(`guest_consent_${value}`, "Guest participant", `Guest website consent state changed to ${value}.`), ...previous.audit] }));
  };

  const resetDemo = () => {
    setSession(seedSession());
    setMicPermission(false); setPreflightReady(false); setNetworkAvailable(false); setMinorRiskState(false); setGuestConsentState("pending"); setGuestQuestion(""); setPrivateQuestions([]); setGuestSaved(false); setGuestUpgradeStep("none"); setBillingState("pilot_eligible"); setLandedCost(7600); setSavedMeetings((items) => items.filter((item) => item.id !== "mtg_guest_001"));
  };

  const liveLibraryItem: LibraryMeetingItem = {
    id: session.id,
    title: session.title,
    occurredAt: session.audit[0]?.createdAt ?? now(),
    origin: "phone_capture",
    accessRule: "Your local capture and workspace policy",
    availability: session.state === "capturing_offline" ? "recording" : session.state === "review" ? "review_ready" : "available",
    summary: session.state === "review" ? "Evidence and human review are available." : "Capture and consent status are available.",
    retentionNote: session.state === "purged" ? "Raw audio purged; receipt remains." : "Raw audio follows the visible retention countdown.",
  };
  const libraryMeetings = [liveLibraryItem, ...savedMeetings].sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime());

  const value = useMemo<SayLessContextValue>(() => ({
    session, micPermission, preflightReady, networkAvailable, isMinorOrUnverified, guestConsent, guestQuestion, privateQuestions, guestSaved, guestUpgradeStep, billingState, landedCost, subscriberKit, attendeeAllowance, libraryMeetings,
    setMicPermission, setPreflightReady, setNetworkAvailable, setMinorOrUnverified, markConsentReady, startCapture, pauseCapture, recordLocalChunk, stopCapture, simulateSync, runSimulatedAi,
    confirmProposal: (id) => updateProposal(id, "confirmed", "proposal_confirmed"), rejectProposal: (id) => updateProposal(id, "rejected", "proposal_rejected"), disputeProposal: (id) => updateProposal(id, "disputed", "proposal_disputed"), correctProposal, redactEvidence, simulateDelivery, addLiveNote, editLiveEntry, sendParticipantChat, askMeetingAssistant, updateWorkflow, confirmWorkflow, simulatePurge, setGuestConsent, setGuestQuestion, submitGuestQuestion: () => { if (guestQuestion.trim()) { setPrivateQuestions((previous) => [guestQuestion.trim(), ...previous]); appendAudit(audit("guest_private_question", "Guest participant", "Guest submitted a private question through the website.")); setGuestQuestion(""); } },
    beginGuestSave: () => setGuestUpgradeStep("create_account"), completeGuestAccount: () => setGuestUpgradeStep("install_app"), completeGuestInstall: () => { setGuestUpgradeStep("complete"); setGuestSaved(true); setSavedMeetings((items) => items.some((item) => item.id === "mtg_guest_001") ? items : [{ id: "mtg_guest_001", title: session.title, occurredAt: now(), origin: "qr_guest_save", accessRule: "Guest accepted a host-permitted save", availability: "shared_outcome", summary: "This guest account can access the meeting outcome view and its own participation receipts.", retentionNote: "The host controls shared content and may remove access." }, ...items]); }, setBillingState, setLandedCost, pairSubscriberKit, setKitChannelStatus, selectSubscriberKit, selectPhoneAmbient, selectBrowserMeeting, selectHybridMeeting, selectApprovedImport, createWorkflowFromChunk, addPersonalNote, selectAttendeePlan, resetDemo,
  }), [session, micPermission, preflightReady, networkAvailable, isMinorOrUnverified, guestConsent, guestQuestion, privateQuestions, guestSaved, guestUpgradeStep, billingState, landedCost, subscriberKit, attendeeAllowance, libraryMeetings]);

  return <SayLessContext.Provider value={value}>{children}</SayLessContext.Provider>;
}

export function useSayLess() {
  const value = useContext(SayLessContext);
  if (!value) throw new Error("useSayLess must be used within SayLessProvider");
  return value;
}
