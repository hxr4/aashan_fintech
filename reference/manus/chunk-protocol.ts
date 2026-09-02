import type { AudioChunk, CaptureSource, QueueStatus } from "./domain";

export const LOCAL_CHUNK_LIMIT = 36;

type PendingStatus = Extract<QueueStatus, "queued" | "uploading" | "failed">;
export type AcknowledgementDisposition = Extract<QueueStatus, "acknowledged" | "gap">;

export type ChunkAcknowledgement = {
  sequenceNo: number;
  correlationId?: string;
  disposition: AcknowledgementDisposition;
};

export type AcknowledgementResult = {
  accepted: boolean;
  reason: "acknowledged" | "gap_recorded" | "offline" | "unknown_sequence" | "duplicate" | "out_of_order" | "receipt_mismatch" | "no_pending_chunk";
  queue: AudioChunk[];
  affectedChunkId?: string;
};

const pendingStatuses: PendingStatus[] = ["queued", "uploading", "failed"];

export function isTerminalChunkStatus(status: QueueStatus) {
  return status === "acknowledged" || status === "gap";
}

export function pendingChunks(queue: AudioChunk[]) {
  return queue.filter((chunk) => pendingStatuses.includes(chunk.status as PendingStatus)).sort((left, right) => left.sequenceNo - right.sequenceNo);
}

export function pendingChunkCount(queue: AudioChunk[]) {
  return pendingChunks(queue).length;
}

export function canBufferLocalChunk(queue: AudioChunk[], limit = LOCAL_CHUNK_LIMIT) {
  return pendingChunkCount(queue) < limit;
}

export function nextChunkSequenceNo(queue: AudioChunk[]) {
  return queue.reduce((highest, chunk) => Math.max(highest, chunk.sequenceNo), 0) + 1;
}

/**
 * A deterministic development-only receipt token. It is deliberately labelled
 * `sim_sha256` because it is not a cryptographic SHA-256 implementation.
 */
export function simulatedIntegrityToken(seed: string) {
  let first = 2166136261;
  let second = 5381;
  for (let index = 0; index < seed.length; index += 1) {
    const code = seed.charCodeAt(index);
    first = Math.imul(first ^ code, 16777619);
    second = Math.imul((second << 5) + second, code);
  }
  return `sim_sha256_${(first >>> 0).toString(16).padStart(8, "0")}${(second >>> 0).toString(16).padStart(8, "0")}`;
}

export function isChunkEligibleForEvidence(chunk: AudioChunk | undefined, activeConsentVersion: string) {
  return Boolean(chunk && chunk.status === "acknowledged" && chunk.consentVersion === activeConsentVersion);
}

export function createLocalChunk(input: {
  queue: AudioChunk[];
  source: CaptureSource;
  consentVersion: string;
  startedAt: string;
  endedAt: string;
  correlationId: string;
}) {
  const sequenceNo = nextChunkSequenceNo(input.queue);
  const id = `chk_${String(sequenceNo).padStart(4, "0")}`;
  const integritySeed = [id, input.source, input.consentVersion, input.startedAt, input.endedAt, input.correlationId].join("|");
  return {
    id,
    sequenceNo,
    source: input.source,
    startedAt: input.startedAt,
    endedAt: input.endedAt,
    sha256: simulatedIntegrityToken(integritySeed),
    consentVersion: input.consentVersion,
    status: "queued" as const,
    correlationId: input.correlationId,
    receiptLabel: `${input.source.replaceAll("_", " ")} · local receipt`,
  } satisfies AudioChunk;
}

/**
 * Accepts only the earliest outstanding sequence. This prevents a later receipt
 * from silently making an earlier missing chunk look processed. A gap is a
 * terminal receipt, never evidence-bearing audio.
 */
export function applyAcknowledgement(queue: AudioChunk[], acknowledgement: ChunkAcknowledgement, networkAvailable: boolean): AcknowledgementResult {
  if (!networkAvailable) return { accepted: false, reason: "offline", queue };

  const target = queue.find((chunk) => chunk.sequenceNo === acknowledgement.sequenceNo);
  if (!target) return { accepted: false, reason: "unknown_sequence", queue };
  if (isTerminalChunkStatus(target.status)) return { accepted: false, reason: "duplicate", queue, affectedChunkId: target.id };
  if (acknowledgement.correlationId && target.correlationId && acknowledgement.correlationId !== target.correlationId) {
    return { accepted: false, reason: "receipt_mismatch", queue, affectedChunkId: target.id };
  }

  const [nextPending] = pendingChunks(queue);
  if (!nextPending) return { accepted: false, reason: "no_pending_chunk", queue };
  if (nextPending.sequenceNo !== acknowledgement.sequenceNo) {
    return { accepted: false, reason: "out_of_order", queue, affectedChunkId: target.id };
  }

  const queueWithReceipt = queue.map((chunk) => chunk.sequenceNo === acknowledgement.sequenceNo
    ? {
      ...chunk,
      status: acknowledgement.disposition,
      receiptLabel: acknowledgement.disposition === "gap"
        ? `${chunk.source.replaceAll("_", " ")} · explicit audio-gap receipt`
        : `${chunk.source.replaceAll("_", " ")} · acknowledged receipt`,
    }
    : chunk,
  );

  return {
    accepted: true,
    reason: acknowledgement.disposition === "gap" ? "gap_recorded" : "acknowledged",
    queue: queueWithReceipt,
    affectedChunkId: target.id,
  };
}
