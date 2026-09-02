import { describe, expect, it } from "vitest";
import { authorizedSyncStatus, canBeginCapture, canGuestSaveMeeting, capturePolicy, resolveAnnualKitPricing, subscriberKitRouting } from "../shared/policy";
import { applyAcknowledgement, canBufferLocalChunk, createLocalChunk, isChunkEligibleForEvidence, nextChunkSequenceNo } from "../shared/chunk-protocol";

const baseChunk = (sequenceNo: number, status: "queued" | "acknowledged" | "gap" = "queued") => ({
  id: `chk_${String(sequenceNo).padStart(4, "0")}`,
  sequenceNo,
  source: "phone_ambient" as const,
  startedAt: "2026-08-18T10:00:00.000Z",
  endedAt: "2026-08-18T10:00:05.000Z",
  sha256: `sim_sha256_${sequenceNo}`,
  consentVersion: "notice-v2.0",
  status,
  correlationId: `rcpt_${sequenceNo}`,
});

describe("Say Less product-policy gates", () => {
  it("enforces Speaker Repeat Mode for a minor or unverified classroom", () => {
    const policy = capturePolicy(true, "phone_ambient");
    expect(policy.source).toBe("speaker_repeat");
    expect(policy.audienceCaptureEnabled).toBe(false);
    expect(policy.privacyMode).toBe("speaker_repeat");
  });

  it("does not permit capture before microphone permission, preflight, and consent-ready state", () => {
    expect(canBeginCapture({ microphoneGranted: false, preflightReady: true, state: "offline_ready" })).toBe(false);
    expect(canBeginCapture({ microphoneGranted: true, preflightReady: false, state: "offline_ready" })).toBe(false);
    expect(canBeginCapture({ microphoneGranted: true, preflightReady: true, state: "consent_required" })).toBe(false);
    expect(canBeginCapture({ microphoneGranted: true, preflightReady: true, state: "offline_ready" })).toBe(true);
  });

  it("never turns an explicit requested gap into acknowledged audio", () => {
    expect(authorizedSyncStatus(false, false)).toBe("queued");
    expect(authorizedSyncStatus(true, true)).toBe("gap");
    expect(authorizedSyncStatus(true, false)).toBe("acknowledged");
  });

  it("keeps phone ambient, Speaker Repeat, and subscriber dual-channel routing distinct", () => {
    expect(capturePolicy(false, "phone_ambient")).toMatchObject({ source: "phone_ambient", audienceCaptureEnabled: true });
    expect(subscriberKitRouting({ minorOrUnverified: false, speakerReady: false, audienceReady: true })).toMatchObject({ allowed: false, source: "phone_ambient" });
    expect(subscriberKitRouting({ minorOrUnverified: true, speakerReady: true, audienceReady: true })).toMatchObject({ allowed: false, source: "speaker_repeat" });
    expect(subscriberKitRouting({ minorOrUnverified: false, speakerReady: true, audienceReady: true })).toMatchObject({ allowed: true, source: "kit_dual_channel" });
  });

  it("only permits guest meeting saving after consent and host permission", () => {
    expect(canGuestSaveMeeting({ consent: "pending", hostAllowsSave: true })).toBe(false);
    expect(canGuestSaveMeeting({ consent: "withdrawn", hostAllowsSave: true })).toBe(false);
    expect(canGuestSaveMeeting({ consent: "granted", hostAllowsSave: false })).toBe(false);
    expect(canGuestSaveMeeting({ consent: "granted", hostAllowsSave: true })).toBe(true);
  });

  it("keeps hardware annual-only and raises the gate when landed cost misses the target", () => {
    expect(resolveAnnualKitPricing(8000)).toMatchObject({ annualOnly: true, priceInr: 24999, pricingGateRaised: false });
    expect(resolveAnnualKitPricing(8001)).toMatchObject({ annualOnly: true, priceInr: 27999, pricingGateRaised: true });
  });

  it("assigns monotonically increasing sequence numbers and preserves acknowledged receipts outside the bounded local buffer", () => {
    const receipt = baseChunk(1, "acknowledged");
    const queued = createLocalChunk({ queue: [receipt], source: "phone_ambient", consentVersion: "notice-v2.0", startedAt: "2026-08-18T10:00:05.000Z", endedAt: "2026-08-18T10:00:10.000Z", correlationId: "rcpt_2" });
    expect(queued.sequenceNo).toBe(2);
    expect(queued.sha256).toMatch(/^sim_sha256_/);
    expect(nextChunkSequenceNo([receipt, queued])).toBe(3);
    expect(canBufferLocalChunk([receipt], 1)).toBe(true);
    expect(canBufferLocalChunk([receipt, queued], 1)).toBe(false);
  });

  it("accepts acknowledgements only in ascending outstanding-sequence order and rejects duplicates", () => {
    const first = baseChunk(1);
    const second = baseChunk(2);
    const outOfOrder = applyAcknowledgement([first, second], { sequenceNo: 2, correlationId: "rcpt_2", disposition: "acknowledged" }, true);
    expect(outOfOrder).toMatchObject({ accepted: false, reason: "out_of_order" });
    const acknowledged = applyAcknowledgement([first, second], { sequenceNo: 1, correlationId: "rcpt_1", disposition: "acknowledged" }, true);
    expect(acknowledged.accepted).toBe(true);
    const duplicate = applyAcknowledgement(acknowledged.queue, { sequenceNo: 1, correlationId: "rcpt_1", disposition: "acknowledged" }, true);
    expect(duplicate).toMatchObject({ accepted: false, reason: "duplicate" });
  });

  it("keeps explicit gaps and consent-mismatched chunks out of evidence eligibility", () => {
    const gap = baseChunk(1, "gap");
    const acknowledged = baseChunk(2, "acknowledged");
    expect(isChunkEligibleForEvidence(gap, "notice-v2.0")).toBe(false);
    expect(isChunkEligibleForEvidence(acknowledged, "notice-v2.1")).toBe(false);
    expect(isChunkEligibleForEvidence(acknowledged, "notice-v2.0")).toBe(true);
  });
});
