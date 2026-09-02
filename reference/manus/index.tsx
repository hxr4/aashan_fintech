import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { router } from "expo-router";
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Card, EmptyState, KeyValue, Notice, palette, PrimaryButton, ScreenTitle, StatusPill } from "@/components/sayless-ui";
import { ROLE_DETAILS, useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";

const stateTone = (state: string) => state === "review" || state === "purged" ? "good" : state.includes("degraded") || state === "purge_failed" ? "danger" : state === "capturing_offline" ? "info" : "warn";
const sourceLabel = (source: string) => ({ phone_ambient: "Phone Ambient", kit_dual_channel: "Duo Kit · dual channel", browser_meeting: "Browser companion", hybrid_meeting: "Hybrid meeting", approved_import: "Approved import", speaker_repeat: "Speaker Repeat Mode" }[source] ?? source.replaceAll("_", " "));

export default function HomeScreen() {
  const { session, networkAvailable, attendeeAllowance, resetDemo } = useSayLess();
  const account = useRoleSession();
  const isOrganizer = account.isAuthenticated && account.role === "organizer";
  const role = ROLE_DETAILS[account.role];
  const queued = session.queue.filter((chunk) => chunk.status === "queued").length;
  const pendingProposal = session.proposals.filter((proposal) => proposal.status === "proposed").length;
  const confirmed = session.workflows.filter((workflow) => ["confirmed", "in_progress", "done"].includes(workflow.status)).length;

  const firstUseGuide = <Card style={styles.guideCard}>
    <View style={styles.guideHeading}><View style={styles.guideIcon}><MaterialIcons name="route" size={20} color={palette.ink} /></View><View style={styles.guideCopy}><Text style={styles.guideTitle}>How Say Less works</Text><Text style={styles.guideBody}>Consent and source truth stay visible from the meeting notice to the confirmed outcome.</Text></View></View>
    <View style={styles.guideSteps}>
      <View style={styles.guideStep}><Text style={styles.guideNumber}>1</Text><View style={styles.guideStepCopy}><Text style={styles.guideStepTitle}>Read the notice</Text><Text style={styles.guideStepBody}>Know what a meeting may capture before you join.</Text></View></View>
      <View style={styles.guideStep}><Text style={styles.guideNumber}>2</Text><View style={styles.guideStepCopy}><Text style={styles.guideStepTitle}>Choose your access</Text><Text style={styles.guideStepBody}>Join by QR as a guest, or sign in to create and save.</Text></View></View>
      <View style={styles.guideStep}><Text style={styles.guideNumber}>3</Text><View style={styles.guideStepCopy}><Text style={styles.guideStepTitle}>Confirm what matters</Text><Text style={styles.guideStepBody}>Proposals stay editable until an authorised person confirms them.</Text></View></View>
    </View>
  </Card>;

  const accountCard = <Card>
    <View style={styles.accountRow}><View style={styles.accountIcon}><MaterialIcons name={account.isAuthenticated ? "verified-user" : "person-outline"} size={21} color={palette.ink} /></View><View style={styles.accountCopy}><Text style={styles.accountTitle}>{account.isAuthenticated ? account.userName ?? "Signed-in account" : "Use your meeting role"}</Text><Text style={styles.accountBody}>{account.isAuthenticated ? `${role.shortLabel} view is active.` : "Join by QR without an account, or sign in to create, save, or manage meetings."}</Text></View></View>
    <PrimaryButton label={account.isAuthenticated ? "Manage role and account" : "Sign in or choose a role"} tone="outline" icon="manage-accounts" onPress={() => router.push((account.isAuthenticated ? "/account" : "/sign-in") as any)} />
  </Card>;

  return <ScreenContainer containerClassName="bg-background" className="px-5 pt-2">
    <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
      <View style={styles.topline}><View style={styles.brand}><Image source={require("@/assets/images/icon.png")} style={styles.logo} accessibilityLabel="Say Less" /><Text style={styles.wordmark}>say less</Text></View><StatusPill label="PROTOTYPE" tone="warn" /></View>
      <ScreenTitle eyebrow={isOrganizer ? "Organizer home" : account.isAuthenticated ? `${role.shortLabel} home` : "Your meeting space"} title={isOrganizer ? "Run the meeting with consent in view." : "Every meeting under the palm of your hands."} />
      {!account.isAuthenticated ? <><Notice tone="info">Guests do not need an account for a meeting notice, consent, withdrawal, or a private question. Account-only access is shown before saved history or organizer tools.</Notice>{firstUseGuide}</> : null}

      {isOrganizer ? <>
        <Card style={styles.sessionCard}>
          <View style={styles.cardTop}><View style={styles.liveMark}><MaterialIcons name="mic-none" color={palette.surface} size={17} /></View><View style={styles.sessionCopy}><Text style={styles.sessionTitle}>{session.title}</Text><Text style={styles.sessionPurpose} numberOfLines={2}>{session.purpose}</Text></View></View>
          <View style={styles.pillRow}><StatusPill label={session.state.replaceAll("_", " ").toUpperCase()} tone={stateTone(session.state) as any} /><StatusPill label={sourceLabel(session.source).toUpperCase()} tone="info" /></View>
          <View style={styles.stats}><View><Text style={styles.statNumber}>{queued}</Text><Text style={styles.statLabel}>QUEUED</Text></View><View><Text style={styles.statNumber}>{pendingProposal}</Text><Text style={styles.statLabel}>TO REVIEW</Text></View><View><Text style={styles.statNumber}>{confirmed}</Text><Text style={styles.statLabel}>CONFIRMED</Text></View></View>
          <PrimaryButton label={session.state === "capturing_offline" ? "Open live meeting room" : "Prepare capture"} icon={session.state === "capturing_offline" ? "forum" : "mic"} onPress={() => router.push((session.state === "capturing_offline" ? `/live/${session.code}` : "/capture") as any)} />
          <PrimaryButton label="Open participant QR website" tone="outline" icon="qr-code-2" onPress={() => router.push(`/guest/${session.code}` as any)} />
        </Card>
        <Text style={styles.sectionLabel}>SESSION SAFETY</Text>
        <Card><KeyValue label="Consent roster" value={`${session.participants.filter((participant) => participant.consent === "granted").length}/${session.participants.length} recorded`} accent={palette.lime} /><KeyValue label="Source" value={sourceLabel(session.source)} /><KeyValue label="Network" value={networkAvailable ? "Network reachable · demo" : "Offline queue mode"} accent={networkAvailable ? palette.lime : palette.amber} /><KeyValue label="Raw audio" value="24-hour policy countdown" /></Card>
      </> : <>
        <Card style={styles.joinCard}>
          <View style={styles.joinIcon}><MaterialIcons name="qr-code-scanner" size={25} color={palette.ink} /></View>
          <Text style={styles.joinTitle}>Join a meeting on your terms.</Text>
          <Text style={styles.joinBody}>Review the notice before you consent. If a host has shared outcomes with you, they appear only after your allowed access is recorded.</Text>
          <PrimaryButton label="Open QR guest example" icon="open-in-new" onPress={() => router.push(`/guest/${session.code}` as any)} />
        </Card>
        {account.isAuthenticated && account.role === "attendee" ? <Card><View style={styles.inlineHeader}><View><Text style={styles.cardTitle}>Your participation allowance</Text><Text style={styles.cardBody}>Personal questions and notes stay separate from the shared room.</Text></View><StatusPill label={`${attendeeAllowance.plan} plan`.toUpperCase()} tone="info" /></View><View style={styles.allowance}><View><Text style={styles.statNumber}>{attendeeAllowance.questionCreditsRemaining}</Text><Text style={styles.statLabel}>QUESTIONS LEFT</Text></View><View><Text style={styles.statNumber}>{attendeeAllowance.noteCreditsRemaining}</Text><Text style={styles.statLabel}>NOTES LEFT</Text></View></View><PrimaryButton label="Open notes and allowed work" tone="outline" icon="sticky-note-2" onPress={() => router.push("/memory" as any)} /></Card> : null}
        {account.role === "decision_owner" ? <Card><Text style={styles.cardTitle}>Assigned work stays evidence-linked.</Text><Text style={styles.cardBody}>{confirmed ? `${confirmed} confirmed item${confirmed === 1 ? " is" : "s are"} available for you to progress.` : "No human-confirmed item is assigned to you yet."}</Text><PrimaryButton label="Review assigned work" tone="outline" icon="assignment-turned-in" onPress={() => router.push("/memory" as any)} /></Card> : null}
        {account.role === "listener" ? <Card><EmptyState icon="visibility" title="Outcome-only access" body="You’ll see only the parts a host or workspace policy has shared. Raw capture is not included in this prototype view." action={<PrimaryButton label="Browse shared meetings" tone="outline" icon="folder-open" onPress={() => router.push("/operations" as any)} />} /></Card> : null}
        {["workspace_admin", "privacy_admin"].includes(account.role) ? <Card><Notice tone="warn">This role is a prototype view. Production workspace policy and privacy administration require server-enforced authorization and audited operations.</Notice><PrimaryButton label="Open scoped settings" tone="outline" icon="admin-panel-settings" onPress={() => router.push("/settings" as any)} /></Card> : null}
        {!account.isAuthenticated ? accountCard : null}
      </>}

      {isOrganizer ? <>
        <Text style={styles.sectionLabel}>ACCOUNT</Text>{accountCard}
        <View style={styles.footerActions}><PrimaryButton label="Browser companion" tone="outline" icon="language" onPress={() => router.push("/extension" as any)} /><Pressable accessibilityRole="button" onPress={resetDemo} style={({ pressed }) => [styles.reset, { opacity: pressed ? 0.6 : 1 }]}><Text style={styles.resetText}>Reset demonstration</Text></Pressable></View>
      </> : null}
    </ScrollView>
  </ScreenContainer>;
}

const styles = StyleSheet.create({
  content: { paddingBottom: 28, gap: 16 },
  topline: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 6 },
  brand: { flexDirection: "row", alignItems: "center", gap: 8 },
  logo: { width: 28, height: 28, borderRadius: 7 },
  wordmark: { color: palette.ink, fontSize: 17, lineHeight: 22, fontWeight: "900", letterSpacing: -0.7 },
  sessionCard: { gap: 15, padding: 18 },
  cardTop: { flexDirection: "row", gap: 11 },
  liveMark: { width: 30, height: 30, borderRadius: 15, backgroundColor: palette.ink, alignItems: "center", justifyContent: "center", marginTop: 1 },
  sessionCopy: { flex: 1 },
  sessionTitle: { color: palette.ink, fontWeight: "800", fontSize: 17, lineHeight: 22 },
  sessionPurpose: { color: palette.muted, fontSize: 13, lineHeight: 18, marginTop: 4 },
  pillRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  stats: { flexDirection: "row", justifyContent: "space-between", borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.line, paddingTop: 13 },
  statNumber: { color: palette.ink, fontWeight: "900", fontSize: 22, lineHeight: 26 },
  statLabel: { color: palette.muted, fontSize: 10, lineHeight: 14, fontWeight: "800", letterSpacing: 0.4 },
  sectionLabel: { color: palette.muted, fontSize: 11, lineHeight: 14, fontWeight: "800", letterSpacing: 1.1, marginTop: 8 },
  accountRow: { flexDirection: "row", gap: 12, alignItems: "center" },
  accountIcon: { width: 42, height: 42, borderRadius: 21, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" },
  accountCopy: { flex: 1, gap: 2 },
  accountTitle: { color: palette.ink, fontSize: 15, lineHeight: 20, fontWeight: "800" },
  accountBody: { color: palette.muted, fontSize: 12, lineHeight: 17 },
  joinCard: { alignItems: "flex-start", gap: 12, padding: 20 },
  joinIcon: { width: 50, height: 50, borderRadius: 25, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" },
  joinTitle: { color: palette.ink, fontWeight: "900", fontSize: 21, lineHeight: 27, letterSpacing: -0.3 },
  joinBody: { color: palette.muted, fontSize: 14, lineHeight: 20 },
  guideCard: { gap: 14, padding: 18 },
  guideHeading: { flexDirection: "row", alignItems: "center", gap: 10 },
  guideIcon: { width: 38, height: 38, borderRadius: 19, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" },
  guideCopy: { flex: 1, gap: 2 },
  guideTitle: { color: palette.ink, fontSize: 16, lineHeight: 21, fontWeight: "800" },
  guideBody: { color: palette.muted, fontSize: 12, lineHeight: 17 },
  guideSteps: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.line, gap: 10, paddingTop: 13 },
  guideStep: { flexDirection: "row", gap: 10, alignItems: "flex-start" },
  guideNumber: { color: palette.lime, fontSize: 12, lineHeight: 18, fontWeight: "900", width: 13, textAlign: "center" },
  guideStepCopy: { flex: 1, gap: 1 },
  guideStepTitle: { color: palette.ink, fontSize: 13, lineHeight: 18, fontWeight: "800" },
  guideStepBody: { color: palette.muted, fontSize: 12, lineHeight: 17 },
  inlineHeader: { flexDirection: "row", gap: 12, justifyContent: "space-between", alignItems: "flex-start" },
  cardTitle: { color: palette.ink, fontSize: 16, lineHeight: 22, fontWeight: "800" },
  cardBody: { color: palette.muted, fontSize: 13, lineHeight: 19, marginTop: 3, maxWidth: 238 },
  allowance: { flexDirection: "row", gap: 34, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.line, paddingTop: 12 },
  footerActions: { gap: 12, marginTop: 4 },
  reset: { alignItems: "center", padding: 10 },
  resetText: { color: palette.muted, fontSize: 12, fontWeight: "700" },
});
