import type { CaptureSource, QueueStatus, SessionState } from "./domain";

export function capturePolicy(minorOrUnverified: boolean, selected: CaptureSource = "phone_ambient") {
  if (minorOrUnverified) {
    return {
      source: "speaker_repeat" as const,
      audienceCaptureEnabled: false,
      privacyMode: "speaker_repeat" as const,
      reason: "Minor or unverified classroom safety rule requires Speaker Repeat Mode.",
    };
  }
  return {
    source: selected,
    audienceCaptureEnabled: selected !== "speaker_repeat",
    privacyMode: "standard" as const,
    reason: "Standard explicit-consent mode.",
  };
}

export function subscriberKitRouting(input: { minorOrUnverified: boolean; speakerReady: boolean; audienceReady: boolean }) {
  if (input.minorOrUnverified) return { allowed: false, source: "speaker_repeat" as const, reason: "Speaker Repeat Mode is required; audience capture is disabled." };
  if (!input.speakerReady || !input.audienceReady) return { allowed: false, source: "phone_ambient" as const, reason: "Both subscriber kit channels must be ready before dual-channel capture can begin." };
  return { allowed: true, source: "kit_dual_channel" as const, reason: "Speaker and audience channels are independently ready." };
}

export function canBeginCapture(input: { microphoneGranted: boolean; preflightReady: boolean; state: SessionState }) {
  return input.microphoneGranted && input.preflightReady && input.state === "offline_ready";
}

export function resolveAnnualKitPricing(landedCostInr: number) {
  return {
    landedCostInr,
    annualOnly: true,
    priceInr: landedCostInr <= 8000 ? 24999 : 27999,
    pricingGateRaised: landedCostInr > 8000,
  };
}

export function canGuestSaveMeeting(input: { consent: "pending" | "granted" | "declined" | "withdrawn"; hostAllowsSave: boolean }) {
  return input.consent === "granted" && input.hostAllowsSave;
}

export function authorizedSyncStatus(networkAvailable: boolean, requestedGap: boolean): QueueStatus {
  if (!networkAvailable) return "queued";
  return requestedGap ? "gap" : "acknowledged";
}
