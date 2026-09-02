import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { useState } from "react";
import { FlatList, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Card, EmptyState, KeyValue, Notice, palette, PrimaryButton, ScreenTitle, StatusPill } from "@/components/sayless-ui";
import { useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";
import type { Proposal } from "@/shared/domain";

const proposalTone = (status: Proposal["status"]) => status === "confirmed" ? "good" : status === "rejected" || status === "redacted" ? "danger" : status === "disputed" ? "info" : "warn";

export default function WorkScreen() {
  const { addPersonalNote, confirmProposal, rejectProposal, disputeProposal, correctProposal, simulateDelivery } = useSayLess();
  const { role, isAuthenticated } = useRoleSession();
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [noteText, setNoteText] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const organizer = isAuthenticated && role === "organizer";
  const decisionOwner = isAuthenticated && role === "decision_owner";
  const participant = isAuthenticated && role === "attendee";

  const saveNote = () => {
    const saved = addPersonalNote(noteText);
    if (!saved) { setNoteError(noteText.trim() ? "Your note allowance is used. Change your simulated plan in Settings to continue." : "Write a note before saving it."); return; }
    setNoteText(""); setNoteError(null);
  };

  if (!organizer && !participant && !decisionOwner) return <RestrictedWork />;

  return <ScreenContainer className="px-5 pt-2">
    <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
      {organizer ? <OrganizerWork selectedProposal={selectedProposal} setSelectedProposal={setSelectedProposal} /> : null}
      {participant ? <ParticipantWork noteText={noteText} setNoteText={setNoteText} noteError={noteError} saveNote={saveNote} /> : null}
      {decisionOwner ? <DecisionOwnerWork /> : null}
    </ScrollView>
    <ProposalSheet proposal={selectedProposal} onClose={() => setSelectedProposal(null)} onConfirm={confirmProposal} onReject={rejectProposal} onDispute={disputeProposal} onCorrect={correctProposal} onDelivery={simulateDelivery} />
  </ScreenContainer>;
}

function OrganizerWork({ selectedProposal, setSelectedProposal }: { selectedProposal: Proposal | null; setSelectedProposal: (proposal: Proposal) => void }) {
  const { session, privateQuestions, redactEvidence } = useSayLess();
  const reviewReady = session.state === "review";

  return <>
    <ScreenTitle eyebrow="Organizer work" title="Review before it becomes memory" action={<StatusPill label={reviewReady ? "REVIEW READY" : "WAITING"} tone={reviewReady ? "good" : "warn"} />}/>
    <Notice tone="info">AI suggestions are advisory. Only an authorised human can confirm a decision, owner, due date, delivery, or memory change.</Notice>
    {!reviewReady ? <Card><EmptyState icon="pending-actions" title="Waiting for authorised evidence" body="Finish consent, capture, acknowledged sync, and the simulated model route. Any gap remains visible; it is never filled with guessed words." /></Card> : null}
    {session.evidence.length ? <>
      <Text style={styles.section}>EVIDENCE</Text>
      <FlatList scrollEnabled={false} data={session.evidence} keyExtractor={(item) => item.id} contentContainerStyle={styles.list} renderItem={({ item }) => <Card>
        <View style={styles.cardTop}><Text style={styles.cardTitle}>Evidence segment</Text><StatusPill label={item.gap ? "GAP" : `${Math.round(item.confidence * 100)}% CONF.`} tone={item.gap ? "danger" : "good"} /></View>
        <Text style={styles.quote}>{item.gap ? "Capture gap — no text was generated." : `“${item.text}”`}</Text>
        <KeyValue label="Source receipt" value={`${item.chunkId} · ${session.source.replaceAll("_", " ")}`} />
        <KeyValue label="Time range" value={`${new Date(item.startedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}–${new Date(item.endedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`} />
        <KeyValue label="Model route" value="Nova-3 → Luna → Terra · demo" />
        {item.text.startsWith("[Redacted") ? <Notice tone="danger">A human redaction receipt is recorded. Original evidence handling is retained in the audit model.</Notice> : <PrimaryButton label="Request evidence redaction" onPress={() => redactEvidence(item.id)} tone="outline" icon="visibility-off" />}
      </Card>} />
    </> : null}
    <Text style={styles.section}>PROPOSED WORK</Text>
    {session.proposals.length ? <FlatList scrollEnabled={false} data={session.proposals} keyExtractor={(item) => item.id} contentContainerStyle={styles.list} renderItem={({ item }) => <Pressable accessibilityRole="button" accessibilityLabel={`Open ${item.kind} proposal`} onPress={() => setSelectedProposal(item)} style={({ pressed }) => [styles.proposalPress, pressed ? styles.pressed : null]}><Card style={item.status === "confirmed" ? styles.confirmedCard : undefined}><View style={styles.cardTop}><View style={styles.cardCopy}><Text style={styles.cardTitle}>{item.kind.toUpperCase()}</Text><Text style={styles.proposalText}>{item.text}</Text></View><StatusPill label={item.status.toUpperCase()} tone={proposalTone(item.status)} /></View><Text style={styles.helper}>Evidence-linked confidence: {Math.round(item.confidence * 100)}%. Tap to review, correct, confirm, reject, or dispute.</Text></Card></Pressable>} /> : <Card><EmptyState icon="auto-awesome" title="No proposals yet" body="Proposals appear only after authorised chunks are acknowledged and processed by the visible demo route." /></Card>}
    <Text style={styles.section}>PRIVATE QUESTIONS</Text>
    {privateQuestions.length ? <FlatList scrollEnabled={false} data={privateQuestions} keyExtractor={(item, index) => `${item}-${index}`} contentContainerStyle={styles.list} renderItem={({ item }) => <Card><View style={styles.cardTop}><Text style={styles.cardTitle}>Guest participant</Text><StatusPill label="HOST ONLY" tone="info" /></View><Text style={styles.question}>{item}</Text></Card>} /> : <Card><Text style={styles.helper}>No private guest questions have been submitted in this demonstration.</Text></Card>}
  </>;
}

function ParticipantWork({ noteText, setNoteText, noteError, saveNote }: { noteText: string; setNoteText: (value: string) => void; noteError: string | null; saveNote: () => void }) {
  const { attendeeAllowance, session } = useSayLess();
  const shared = session.proposals.filter((proposal) => proposal.status === "confirmed");
  return <>
    <ScreenTitle eyebrow="Participant space" title="Notes and shared outcomes" action={<StatusPill label={`${attendeeAllowance.noteCreditsRemaining} NOTES LEFT`} tone={attendeeAllowance.noteCreditsRemaining ? "info" : "warn"} />}/>
    <Notice tone="info">Your notes stay personal in this prototype. You see only the confirmed outcomes a host has chosen to share, not raw capture or private questions.</Notice>
    <Card><Text style={styles.cardTitle}>Make a personal note</Text><TextInput value={noteText} onChangeText={setNoteText} placeholder="What do you want to remember?" placeholderTextColor={palette.muted} multiline textAlignVertical="top" style={styles.input} accessibilityLabel="Personal meeting note" /><PrimaryButton label="Save personal note" icon="bookmark-add" onPress={saveNote} disabled={!noteText.trim() || attendeeAllowance.noteCreditsRemaining < 1} />{noteError ? <Notice tone="warn">{noteError}</Notice> : null}</Card>
    <Text style={styles.section}>YOUR NOTES</Text>
    {attendeeAllowance.personalNotes.length ? <FlatList scrollEnabled={false} data={attendeeAllowance.personalNotes} keyExtractor={(item) => item.id} contentContainerStyle={styles.list} renderItem={({ item }) => <Card><View style={styles.cardTop}><Text style={styles.cardTitle}>Personal note</Text><StatusPill label="PRIVATE" tone="info" /></View><Text style={styles.question}>{item.text}</Text></Card>} /> : <Card><EmptyState icon="sticky-note-2" title="No personal notes yet" body="Save a note above. Your notes do not appear in the shared meeting room." /></Card>}
    <Text style={styles.section}>SHARED, CONFIRMED OUTCOMES</Text>
    {shared.length ? <FlatList scrollEnabled={false} data={shared} keyExtractor={(item) => item.id} contentContainerStyle={styles.list} renderItem={({ item }) => <Card><View style={styles.cardTop}><Text style={styles.cardTitle}>{item.kind.toUpperCase()}</Text><StatusPill label="CONFIRMED" tone="good" /></View><Text style={styles.proposalText}>{item.text}</Text><Text style={styles.helper}>This outcome was human-confirmed before it was shared.</Text></Card>} /> : <Card><EmptyState icon="visibility-off" title="Nothing shared yet" body="Proposed AI output stays private until an authorised person confirms and shares it." /></Card>}
  </>;
}

function DecisionOwnerWork() {
  const { session, updateWorkflow } = useSayLess();
  const assigned = session.workflows.filter((item) => ["confirmed", "in_progress", "blocked"].includes(item.status));
  return <>
    <ScreenTitle eyebrow="Decision owner" title="Move confirmed work forward" />
    <Notice tone="info">Status updates are a prototype action. The original evidence link and prior edits remain available in the meeting audit history.</Notice>
    {assigned.length ? <FlatList scrollEnabled={false} data={assigned} keyExtractor={(item) => item.id} contentContainerStyle={styles.list} renderItem={({ item }) => <Card><View style={styles.cardTop}><View style={styles.cardCopy}><Text style={styles.cardTitle}>{item.title}</Text><Text style={styles.helper}>Owner: {item.owner} · Due {item.dueDate}</Text></View><StatusPill label={item.status.replaceAll("_", " ").toUpperCase()} tone={item.status === "blocked" ? "danger" : item.status === "in_progress" ? "info" : "good"} /></View><View style={styles.actionRow}>{item.status === "confirmed" ? <PrimaryButton label="Start work" tone="outline" icon="play-arrow" onPress={() => updateWorkflow(item.id, { status: "in_progress" })} /> : null}{item.status === "in_progress" ? <PrimaryButton label="Mark done" icon="check" onPress={() => updateWorkflow(item.id, { status: "done" })} /> : null}{item.status !== "blocked" && item.status !== "done" ? <PrimaryButton label="Mark blocked" tone="outline" icon="block" onPress={() => updateWorkflow(item.id, { status: "blocked" })} /> : null}</View></Card>} /> : <Card><EmptyState icon="assignment" title="No confirmed work assigned" body="Proposed work is not actionable until an authorised person confirms it." /></Card>}
  </>;
}

function RestrictedWork() {
  const { role, isAuthenticated } = useRoleSession();
  return <ScreenContainer className="px-5 pt-2"><ScrollView contentContainerStyle={styles.content}><ScreenTitle eyebrow={isAuthenticated ? "Restricted role" : "Account required"} title="Work stays permission-scoped" /><Card><EmptyState icon="lock-outline" title={isAuthenticated ? "No work controls in this view" : "Sign in for personal work"} body={isAuthenticated ? `${role.replaceAll("_", " ")} access does not include proposal review or personal work controls.` : "Guests can participate through a QR meeting without an account. Sign in to save allowed outcomes or use a role-specific workspace view."} /></Card></ScrollView></ScreenContainer>;
}

function ProposalSheet({ proposal, onClose, onConfirm, onReject, onDispute, onCorrect, onDelivery }: { proposal: Proposal | null; onClose: () => void; onConfirm: (id: string) => void; onReject: (id: string) => void; onDispute: (id: string) => void; onCorrect: (id: string) => void; onDelivery: () => void }) {
  if (!proposal) return null;
  const final = proposal.status !== "proposed";
  const complete = (action: (id: string) => void) => { action(proposal.id); onClose(); };
  return <Modal visible transparent animationType="slide" onRequestClose={onClose}><Pressable style={styles.backdrop} onPress={onClose}><Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}><View style={styles.sheetHandle} /><View style={styles.cardTop}><Text style={styles.sheetTitle}>Review {proposal.kind}</Text><Pressable accessibilityRole="button" accessibilityLabel="Close proposal review" onPress={onClose} style={styles.close}><MaterialIcons name="close" color={palette.ink} size={20} /></Pressable></View><StatusPill label={proposal.status.toUpperCase()} tone={proposalTone(proposal.status)} /><Text style={styles.sheetText}>{proposal.text}</Text><Notice tone="info">{Math.round(proposal.confidence * 100)}% confidence · evidence-linked · human confirmation required</Notice>{!final ? <View style={styles.sheetActions}><PrimaryButton label="Confirm" icon="check" onPress={() => complete(onConfirm)} /><PrimaryButton label="Correct wording" tone="outline" icon="edit" onPress={() => complete(onCorrect)} /><PrimaryButton label="Dispute" tone="outline" icon="gavel" onPress={() => complete(onDispute)} /><PrimaryButton label="Reject" tone="outline" icon="close" onPress={() => complete(onReject)} /></View> : <View style={styles.sheetActions}><Notice tone={proposal.status === "confirmed" ? "good" : proposal.status === "disputed" ? "warn" : "danger"}>{proposal.status === "confirmed" ? "Human confirmation recorded. A delivery preview may now be created." : "This proposal is blocked from becoming confirmed memory unless it is corrected and reviewed again."}</Notice><PrimaryButton label="Correct wording" tone="outline" icon="edit" onPress={() => complete(onCorrect)} />{proposal.status === "confirmed" ? <PrimaryButton label="Create delivery preview" tone="outline" icon="send" onPress={() => { onDelivery(); onClose(); }} /> : null}</View>}</Pressable></Pressable></Modal>;
}

const styles = StyleSheet.create({
  content: { gap: 16, paddingBottom: 28 }, list: { gap: 12 }, section: { color: palette.muted, fontSize: 11, lineHeight: 14, fontWeight: "800", letterSpacing: 1.1, marginTop: 4 }, cardTop: { flexDirection: "row", gap: 12, justifyContent: "space-between", alignItems: "flex-start" }, cardCopy: { flex: 1, gap: 3 }, cardTitle: { color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: "800", letterSpacing: 0.1 }, quote: { color: palette.ink, fontSize: 16, lineHeight: 23, fontWeight: "600" }, proposalText: { color: palette.ink, fontSize: 16, lineHeight: 22, fontWeight: "800", marginTop: 5 }, helper: { color: palette.muted, fontSize: 12, lineHeight: 17 }, question: { color: palette.ink, fontSize: 14, lineHeight: 20 }, confirmedCard: { borderColor: palette.lime }, proposalPress: { borderRadius: 18 }, pressed: { opacity: 0.74 }, input: { minHeight: 112, borderWidth: 1, borderColor: palette.line, backgroundColor: palette.soft, borderRadius: 14, color: palette.ink, fontSize: 15, lineHeight: 21, padding: 13 }, actionRow: { gap: 9 }, backdrop: { flex: 1, backgroundColor: "rgba(17,24,39,0.38)", justifyContent: "flex-end" }, sheet: { backgroundColor: palette.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingHorizontal: 20, paddingTop: 10, paddingBottom: 30, gap: 14 }, sheetHandle: { alignSelf: "center", width: 36, height: 4, borderRadius: 2, backgroundColor: palette.line, marginBottom: 4 }, sheetTitle: { color: palette.ink, fontSize: 21, lineHeight: 27, fontWeight: "900" }, close: { width: 42, height: 42, borderRadius: 21, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" }, sheetText: { color: palette.ink, fontSize: 17, lineHeight: 24, fontWeight: "700" }, sheetActions: { gap: 10 },
});
