import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ScreenContainer } from "@/components/screen-container";
import { Card, EmptyState, KeyValue, Notice, palette, PrimaryButton, ScreenTitle, SectionLabel, StatusPill } from "@/components/sayless-ui";
import { useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";

const sourceLabel = { phone_capture: "Phone Ambient", qr_guest_save: "Saved through guest link", browser_handoff: "Browser companion", approved_import: "Approved import", workspace_share: "Workspace share" } as const;
const availabilityTone = (status: string) => status === "review_ready" || status === "available" ? "good" : status === "recording" ? "info" : status === "removed" ? "danger" : "neutral";

export default function MeetingDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { libraryMeetings, session } = useSayLess();
  const { role, isAuthenticated } = useRoleSession();
  const meeting = libraryMeetings.find((item) => item.id === id);
  const organizer = isAuthenticated && role === "organizer";
  const decisionOwner = isAuthenticated && role === "decision_owner";
  if (!meeting) return <ScreenContainer className="px-5 pt-2"><ScrollView contentContainerStyle={styles.content}><ScreenTitle eyebrow="Meeting unavailable" title="This meeting is not in your library." /><Card><EmptyState icon="remove-circle-outline" title="Access has changed" body="The host may have removed this meeting, or your permitted access window may have ended." action={<PrimaryButton label="Back to meetings" onPress={() => router.back()} icon="arrow-back" />} /></Card></ScrollView></ScreenContainer>;
  const isLiveSession = meeting.id === session.id;
  const source = meeting.origin as keyof typeof sourceLabel;
  const confirmed = isLiveSession ? session.workflows.filter((item) => ["confirmed", "in_progress", "done"].includes(item.status)) : [];
  const latestReceipt = isLiveSession ? session.audit.at(0) : undefined;

  return <ScreenContainer className="px-5 pt-2"><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
    <ScreenTitle eyebrow={organizer ? "Host meeting record" : decisionOwner ? "Assigned meeting work" : "My meeting record"} title={meeting.title} action={<StatusPill label={meeting.availability.replaceAll("_", " ").toUpperCase()} tone={availabilityTone(meeting.availability)} />} />
    <Card style={styles.summaryCard}><View style={styles.summaryTop}><View style={styles.icon}><MaterialIcons name="verified-user" size={23} color={palette.ink} /></View><View style={styles.summaryCopy}><Text style={styles.cardTitle}>Why this is in your library</Text><Text style={styles.copy}>{meeting.summary}</Text></View></View><KeyValue label="Source" value={sourceLabel[source]} /><KeyValue label="Access rule" value={meeting.accessRule} accent={palette.lime} /><KeyValue label="Meeting date" value={new Date(meeting.occurredAt).toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" })} /></Card>
    <SectionLabel>ACCESS AND RETENTION</SectionLabel>
    <Card><KeyValue label="Availability" value={meeting.availability.replaceAll("_", " ")} /><KeyValue label="Retention" value={meeting.retentionNote} accent={palette.amber} />{isLiveSession ? <><KeyValue label="Raw-audio deadline" value={new Date(session.retentionEndsAt).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })} /><Text style={styles.receipt}>Latest receipt · {latestReceipt?.type.replaceAll("_", " ") ?? "No lifecycle receipt recorded"} · {latestReceipt?.correlationId ?? "not available"}</Text></> : <Notice tone="info">This shared library record does not expose raw capture, device data, or another workspace’s controls.</Notice>}</Card>
    {isLiveSession ? <><SectionLabel>{organizer || decisionOwner ? "CONFIRMED WORK" : "PERMITTED OUTCOMES"}</SectionLabel><Card>{confirmed.length ? confirmed.map((item) => <View key={item.id} style={styles.workRow}><View style={styles.workMarker}><MaterialIcons name={item.status === "done" ? "check" : "assignment"} size={17} color={palette.ink} /></View><View style={styles.workCopy}><Text style={styles.workTitle}>{item.title}</Text><Text style={styles.copy}>{item.owner} · {item.status.replaceAll("_", " ")} · Due {item.dueDate}</Text><Text style={styles.receipt}>Evidence: {item.evidenceIds.join(", ")}</Text></View></View>) : <EmptyState icon="assignment" title="No confirmed work yet" body="Proposals need human confirmation before they appear as meeting work." />}</Card></> : null}
    {isLiveSession && organizer ? <Card><Text style={styles.cardTitle}>Host controls</Text><Text style={styles.copy}>Evidence review, capture, and lifecycle controls remain subject to consent, source integrity, and retention state.</Text><PrimaryButton label={session.state === "review" ? "Open evidence review" : "Open capture"} onPress={() => router.push((session.state === "review" ? "/memory" : "/capture") as any)} icon={session.state === "review" ? "fact-check" : "mic"} /><PrimaryButton label="Open retention and audit" tone="outline" onPress={() => router.push("/operations" as any)} icon="policy" /></Card> : null}
    {isLiveSession && decisionOwner ? <Card><Text style={styles.cardTitle}>Your assigned work</Text><Text style={styles.copy}>You can update your permitted work items. Meeting capture, evidence edits, retention, and billing remain host controls.</Text><PrimaryButton label="Open work" onPress={() => router.push("/memory" as any)} icon="assignment" /></Card> : null}
    {!organizer && !decisionOwner ? <Notice tone="info">Your library view follows the sharing rule shown above. It does not grant host capture, evidence-editing, billing, hardware, lifecycle, or workspace-administration controls.</Notice> : null}
  </ScrollView></ScreenContainer>;
}

const styles = StyleSheet.create({
  content: { gap: 15, paddingBottom: 30 }, summaryCard: { gap: 14 }, summaryTop: { flexDirection: "row", gap: 12, alignItems: "flex-start" }, summaryCopy: { flex: 1, gap: 5 }, icon: { width: 46, height: 46, borderRadius: 15, backgroundColor: palette.lime, alignItems: "center", justifyContent: "center" }, cardTitle: { color: palette.ink, fontSize: 17, lineHeight: 22, fontWeight: "900" }, copy: { color: palette.muted, fontSize: 12, lineHeight: 18 }, receipt: { color: palette.blue, fontSize: 10, lineHeight: 15, fontWeight: "700" }, workRow: { flexDirection: "row", gap: 10, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.line }, workMarker: { width: 31, height: 31, borderRadius: 9, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" }, workCopy: { flex: 1, gap: 3 }, workTitle: { color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: "800" },
});
