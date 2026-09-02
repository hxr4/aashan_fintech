import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { router } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Card, EmptyState, KeyValue, Notice, palette, PrimaryButton, ScreenTitle, StatusPill } from "@/components/sayless-ui";
import { useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";
import type { LibraryMeetingItem } from "@/shared/domain";

type Filter = "all" | "available" | "shared_outcome" | "review_ready";
const sourceLabel = (origin: LibraryMeetingItem["origin"]) => ({ phone_capture: "Phone Ambient", qr_guest_save: "Saved from QR", browser_handoff: "Browser companion", approved_import: "Approved import", workspace_share: "Workspace share" }[origin]);
const availabilityTone = (availability: LibraryMeetingItem["availability"]) => availability === "available" || availability === "review_ready" ? "good" : availability === "recording" ? "info" : availability === "removed" ? "danger" : "warn";

export default function MeetingsScreen() {
  const { session, libraryMeetings, simulatePurge } = useSayLess();
  const { role, isAuthenticated } = useRoleSession();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const isOrganizer = isAuthenticated && role === "organizer";
  const canSeeLibrary = isAuthenticated && ["organizer", "attendee", "listener", "decision_owner"].includes(role);
  const remaining = Math.max(0, new Date(session.retentionEndsAt).getTime() - Date.now());
  const hours = Math.floor(remaining / 3_600_000).toString().padStart(2, "0");
  const minutes = Math.floor((remaining % 3_600_000) / 60_000).toString().padStart(2, "0");
  const purgeFailed = session.state === "purge_failed";
  const filtered = useMemo(() => libraryMeetings.filter((item) => (filter === "all" || item.availability === filter) && `${item.title} ${item.summary} ${item.accessRule}`.toLowerCase().includes(query.trim().toLowerCase())), [libraryMeetings, filter, query]);
  const grouped = useMemo(() => {
    const now = new Date(); const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime(); const weekStart = todayStart - 6 * 24 * 60 * 60 * 1000;
    const buckets: { title: string; data: LibraryMeetingItem[] }[] = [{ title: "TODAY", data: [] }, { title: "THIS WEEK", data: [] }, { title: "EARLIER", data: [] }];
    filtered.forEach((item) => { const date = new Date(item.occurredAt).getTime(); buckets[date >= todayStart ? 0 : date >= weekStart ? 1 : 2].data.push(item); });
    return buckets.filter((bucket) => bucket.data.length);
  }, [filtered]);

  if (!canSeeLibrary) return <AccountRequired />;

  return <ScreenContainer className="px-5 pt-2"><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
    <ScreenTitle eyebrow={isOrganizer ? "Organizer library" : "Your allowed meetings"} title="Meetings" action={<StatusPill label={isOrganizer ? "HOST" : "SCOPED ACCESS"} tone={isOrganizer ? "good" : "info"} />}/>
    {isOrganizer ? <Notice tone={purgeFailed ? "danger" : "info"}>{purgeFailed ? "Deletion verification failed. This is a critical lifecycle incident; no success receipt is shown." : "Raw-audio status is distinct from meeting memory. Audit receipts remain according to the defined retention policy."}</Notice> : <Notice tone="info">This library contains only meeting memories or outcomes you are allowed to access. Source, host rules, and retention notes remain visible.</Notice>}
    <View style={styles.search}><MaterialIcons name="search" size={20} color={palette.muted} /><TextInput value={query} onChangeText={setQuery} placeholder="Search allowed meetings" placeholderTextColor={palette.muted} style={styles.searchInput} accessibilityLabel="Search allowed meetings" /></View>
    <View style={styles.chips}>{(["all", "available", "shared_outcome", "review_ready"] as Filter[]).map((item) => <Pressable key={item} accessibilityRole="button" accessibilityLabel={`Filter ${item.replaceAll("_", " ")}`} onPress={() => setFilter(item)} style={({ pressed }) => [styles.chip, filter === item ? styles.chipActive : null, pressed ? styles.pressed : null]}><Text style={[styles.chipText, filter === item ? styles.chipTextActive : null]}>{item === "all" ? "All" : item.replaceAll("_", " ")}</Text></Pressable>)}</View>
    {grouped.length ? grouped.map((group) => <View key={group.title} style={styles.group}><Text style={styles.section}>{group.title}</Text><FlatList scrollEnabled={false} data={group.data} keyExtractor={(item) => item.id} contentContainerStyle={styles.list} renderItem={({ item }) => <Pressable accessibilityRole="button" accessibilityLabel={`Open ${item.title}`} onPress={() => router.push(`/meeting/${item.id}` as any)} style={({ pressed }) => [styles.meetingPress, pressed ? styles.pressed : null]}><Card><View style={styles.cardTop}><View style={styles.cardCopy}><Text style={styles.meetingTitle}>{item.title}</Text><Text style={styles.meetingMeta}>{new Date(item.occurredAt).toLocaleDateString([], { month: "short", day: "numeric" })} · {sourceLabel(item.origin)}</Text></View><StatusPill label={item.availability.replaceAll("_", " ").toUpperCase()} tone={availabilityTone(item.availability)} /></View><Text style={styles.summary}>{item.summary}</Text><KeyValue label="Access" value={item.accessRule} /><KeyValue label="Retention" value={item.retentionNote} /></Card></Pressable>} /></View>) : <Card><EmptyState icon="search-off" title="No allowed meetings match" body={query || filter !== "all" ? "Try another search or remove a filter." : "Saved meetings appear after a host shares a permitted outcome or you complete the optional account save path."} /></Card>}
    {isOrganizer ? <OrganizerLifecycle sessionState={session.state} hours={hours} minutes={minutes} purgeFailed={purgeFailed} onVerify={() => simulatePurge(false)} onFailure={() => simulatePurge(true)} /> : null}
  </ScrollView></ScreenContainer>;
}

function OrganizerLifecycle({ sessionState, hours, minutes, purgeFailed, onVerify, onFailure }: { sessionState: string; hours: string; minutes: string; purgeFailed: boolean; onVerify: () => void; onFailure: () => void }) {
  const { session } = useSayLess();
  return <>
    <Text style={styles.section}>HOST LIFECYCLE CONTROLS</Text>
    <Card style={purgeFailed ? styles.dangerCard : undefined}><View style={styles.retentionTop}><View><Text style={styles.meetingTitle}>Raw-audio retention</Text><Text style={styles.timer}>{sessionState === "purged" ? "PURGED" : `${hours}:${minutes}`}</Text><Text style={styles.helper}>{sessionState === "purged" ? "Simulated deletion receipt verified." : "Remaining before scheduled purge"}</Text></View><View style={styles.lifecycleIcon}><MaterialIcons name={sessionState === "purged" ? "verified" : "timer"} size={24} color={sessionState === "purged" ? palette.lime : palette.amber} /></View></View><KeyValue label="Scope" value="Raw audio only; audit retained" /><KeyValue label="Legal hold" value="No active hold · demo" /><KeyValue label="Verification" value={sessionState === "purged" ? "Receipt #del_sim_0818" : purgeFailed ? "Failed — escalated" : "Pending simulated verifier"} accent={sessionState === "purged" ? palette.lime : purgeFailed ? palette.coral : palette.amber} />{sessionState !== "purged" ? <View style={styles.actions}><PrimaryButton label="Verify simulated purge" icon="delete-sweep" onPress={onVerify} /><PrimaryButton label="Simulate verification failure" tone="outline" icon="error-outline" onPress={onFailure} /></View> : null}</Card>
    <Text style={styles.section}>SESSION RECEIPTS</Text>
    <FlatList scrollEnabled={false} data={session.audit.slice(0, 8)} keyExtractor={(item) => item.id} contentContainerStyle={styles.auditList} renderItem={({ item }) => <View style={styles.auditRow}><View style={styles.auditDot} /><View style={styles.auditCopy}><Text style={styles.auditType}>{item.type.replaceAll("_", " ")}</Text><Text style={styles.auditDetail}>{item.detail}</Text><Text style={styles.auditMeta}>{new Date(item.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })} · {item.correlationId}</Text></View></View>} />
    <Text style={styles.section}>MODEL ROUTING</Text><Card><KeyValue label="Live transcription" value="Deepgram Nova-3 Multilingual" /><KeyValue label="Batch recovery" value="Google Chirp 3" /><KeyValue label="Live insights" value="GPT-5.6 Luna · advisory" /><KeyValue label="Memory" value="GPT-5.6 Terra · human-confirmed" /></Card>
  </>;
}

function AccountRequired() {
  const { role, isAuthenticated } = useRoleSession();
  return <ScreenContainer className="px-5 pt-2"><ScrollView contentContainerStyle={styles.content}><ScreenTitle eyebrow={isAuthenticated ? "Restricted role" : "Account required"} title="Your meeting library" /><Card><EmptyState icon="folder-shared" title={isAuthenticated ? "No meeting library in this role" : "Sign in to view saved meetings"} body={isAuthenticated ? `${role.replaceAll("_", " ")} access is limited to workspace policy and does not include a personal meeting library.` : "QR guests can participate without an account. Sign in only when you choose to save permitted meeting outcomes."} /></Card></ScrollView></ScreenContainer>;
}

const styles = StyleSheet.create({
  content: { gap: 16, paddingBottom: 28 }, search: { height: 50, borderWidth: 1, borderColor: palette.line, borderRadius: 14, backgroundColor: palette.surface, flexDirection: "row", alignItems: "center", paddingHorizontal: 13, gap: 9 }, searchInput: { flex: 1, color: palette.ink, fontSize: 15, lineHeight: 20, paddingVertical: 0 }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 }, chip: { minHeight: 38, paddingHorizontal: 12, borderRadius: 19, borderWidth: 1, borderColor: palette.line, justifyContent: "center", backgroundColor: palette.surface }, chipActive: { backgroundColor: palette.ink, borderColor: palette.ink }, chipText: { color: palette.ink, fontSize: 12, lineHeight: 16, fontWeight: "800", textTransform: "capitalize" }, chipTextActive: { color: palette.surface }, pressed: { opacity: 0.7 }, group: { gap: 9 }, section: { color: palette.muted, fontSize: 11, lineHeight: 14, fontWeight: "800", letterSpacing: 1.1, marginTop: 4 }, list: { gap: 11 }, meetingPress: { borderRadius: 18 }, cardTop: { flexDirection: "row", gap: 10, justifyContent: "space-between", alignItems: "flex-start" }, cardCopy: { flex: 1, gap: 2 }, meetingTitle: { color: palette.ink, fontSize: 16, lineHeight: 21, fontWeight: "800" }, meetingMeta: { color: palette.muted, fontSize: 12, lineHeight: 17 }, summary: { color: palette.ink, fontSize: 13, lineHeight: 19 }, retentionTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" }, timer: { color: palette.ink, fontSize: 34, lineHeight: 40, fontWeight: "900", letterSpacing: -1, marginTop: 2, fontVariant: ["tabular-nums"] }, helper: { color: palette.muted, fontSize: 12, lineHeight: 17 }, lifecycleIcon: { width: 52, height: 52, borderRadius: 26, alignItems: "center", justifyContent: "center", backgroundColor: palette.soft }, actions: { gap: 9 }, dangerCard: { borderColor: palette.coral }, auditList: { gap: 0 }, auditRow: { flexDirection: "row", gap: 11, paddingVertical: 8 }, auditDot: { width: 9, height: 9, borderRadius: 5, backgroundColor: palette.lime, marginTop: 4 }, auditCopy: { flex: 1, gap: 3 }, auditType: { color: palette.ink, fontSize: 12, lineHeight: 17, fontWeight: "800", textTransform: "capitalize" }, auditDetail: { color: palette.muted, fontSize: 12, lineHeight: 17 }, auditMeta: { color: palette.muted, fontSize: 10, lineHeight: 14, fontFamily: "monospace" },
});
