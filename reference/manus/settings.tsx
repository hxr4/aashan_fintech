import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Card, KeyValue, Notice, palette, PrimaryButton, ScreenTitle, StatusPill } from "@/components/sayless-ui";
import { ROLE_DETAILS, useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";
import { resolveAnnualKitPricing } from "@/shared/policy";

export default function SettingsScreen() {
  const { billingState, setBillingState, landedCost, setLandedCost, attendeeAllowance, selectAttendeePlan, isMinorOrUnverified } = useSayLess();
  const { role, isAuthenticated, userName } = useRoleSession();
  const pricing = resolveAnnualKitPricing(landedCost);
  const organizer = isAuthenticated && role === "organizer";
  const attendee = isAuthenticated && role === "attendee";
  const workspaceControl = isAuthenticated && ["workspace_admin", "privacy_admin"].includes(role);
  const roleDetail = ROLE_DETAILS[role];
  const annual = billingState === "demo_entitlement_active";

  return <ScreenContainer className="px-5 pt-2"><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
    <ScreenTitle eyebrow="Account and controls" title="Settings" action={<StatusPill label={isAuthenticated ? roleDetail.shortLabel.toUpperCase() : "GUEST"} tone={isAuthenticated ? "info" : "warn"} />}/>
    <Notice tone="warn">Payment, role authorization, deletion, and provider delivery are simulated where marked. No card details, payment details, or billing address are collected.</Notice>

    <Text style={styles.section}>ACCOUNT</Text>
    <Card><SettingRow icon="manage-accounts" title={isAuthenticated ? userName ?? "Signed-in account" : "Sign in or choose a role"} detail={isAuthenticated ? `${roleDetail.shortLabel} view · ${roleDetail.description}` : "QR guests can still read notice, consent, withdraw, and ask a private question without an account."} action="Manage" onPress={() => router.push("/account" as any)} /><SettingRow icon="privacy-tip" title="Access boundary" detail={isAuthenticated ? "This view is prototype-scoped; server enforcement is not claimed." : "Account-only routes stay unavailable until sign-in."} last /></Card>

    {organizer ? <OrganizerSettings annual={annual} landedCost={landedCost} setLandedCost={setLandedCost} pricing={pricing} billingState={billingState} setBillingState={setBillingState} minorMode={isMinorOrUnverified} /> : null}
    {attendee ? <AttendeeSettings plan={attendeeAllowance.plan} questions={attendeeAllowance.questionCreditsRemaining} notes={attendeeAllowance.noteCreditsRemaining} onPlan={selectAttendeePlan} /> : null}
    {workspaceControl ? <WorkspaceControlSettings privacy={role === "privacy_admin"} /> : null}

    <Text style={styles.section}>DEVICES AND COMPANIONS</Text>
    <Card><SettingRow icon="mic-none" title="Phone Ambient" detail={organizer ? "Primary in-room microphone route. Permission, consent, and preflight are required." : "Hosts choose the capture source. Participants see the source disclosure in each meeting."} action={organizer ? "Capture" : undefined} onPress={organizer ? () => router.push("/capture" as any) : undefined} /><SettingRow icon="settings-input-component" title="Say Less Duo Kit" detail={organizer ? "Annual subscriber hardware with separate Speaker A and Audience B health." : "Dual-channel capture is disclosed by the host and meeting notice."} action={organizer ? "View" : undefined} onPress={organizer ? () => router.push("/kit" as any) : undefined} /><SettingRow icon="language" title="Browser companion" detail="Consent-first session handoff. It does not silently capture browser audio in this prototype." action="Open" onPress={() => router.push("/extension" as any)} last /></Card>

    <Text style={styles.section}>MEETING SAFETY</Text>
    <Card><SettingRow icon="verified-user" title="Consent standard" detail="Individual, explicit, scope-specific consent; a host acknowledgement is not enough." /><SettingRow icon="record-voice-over" title="Speaker Repeat Mode" detail={organizer ? (isMinorOrUnverified ? "Enabled: audience Channel B is locked off." : "Available automatically for minors or unverified classrooms.") : "Automatically locks audience capture when a safety rule is active."} badge={organizer && isMinorOrUnverified ? "ACTIVE" : "POLICY"} badgeTone={organizer && isMinorOrUnverified ? "good" : "info"} /><SettingRow icon="timer" title="Raw-audio lifecycle" detail="24-hour purge policy with a receipt model. A legal hold never extends raw-audio retention." last /></Card>

    <Text style={styles.section}>PROTOTYPE BOUNDARIES</Text>
    <Card><KeyValue label="Audio" value="Device recording may be real; queues and transport receipts are simulated" /><KeyValue label="AI" value="Provider route and outputs are simulated and advisory" /><KeyValue label="Data lifecycle" value="Deletion verification and receipts are simulated" /><KeyValue label="Workspace roles" value="UI-scoped; production authorization requires server enforcement" /></Card>
  </ScrollView></ScreenContainer>;
}

function OrganizerSettings({ annual, landedCost, setLandedCost, pricing, billingState, setBillingState, minorMode }: { annual: boolean; landedCost: number; setLandedCost: (value: number) => void; pricing: { priceInr: number }; billingState: string; setBillingState: (value: any) => void; minorMode: boolean }) {
  return <>
    <Text style={styles.section}>ORGANIZER ACCESS</Text>
    <Card><View style={styles.cardHead}><View style={styles.cardCopy}><Text style={styles.cardTitle}>Hosted meeting access</Text><Text style={styles.helper}>An organizer activates upfront in this simulation. Hardware is annual only.</Text></View><StatusPill label={annual ? "ACTIVE" : "PILOT"} tone={annual ? "good" : "warn"} /></View><KeyValue label="Annual Duo Kit" value={`₹${pricing.priceInr.toLocaleString("en-IN")}`} accent={palette.lime} /><KeyValue label="Monthly hardware plan" value="Not available" accent={palette.coral} /><KeyValue label="Enterprise pilot" value="₹75,000 + GST · 90 days" /><View style={styles.switchLine}><View style={styles.cardCopy}><Text style={styles.rowTitle}>Cost exceeds ₹8,000</Text><Text style={styles.helper}>Tests the price gate. Current landed cost: ₹{landedCost.toLocaleString("en-IN")}</Text></View><Switch value={landedCost > 8000} onValueChange={(value) => setLandedCost(value ? 8600 : 7600)} trackColor={{ false: palette.line, true: palette.amber }} thumbColor={palette.surface} /></View><View style={styles.buttonStack}><PrimaryButton label="Open organizer checkout demo" icon="shopping-bag" onPress={() => setBillingState("demo_checkout")} /><PrimaryButton label="Activate demo entitlement" tone="outline" icon="verified" onPress={() => setBillingState("demo_entitlement_active")} /></View><Notice tone={minorMode ? "good" : "info"}>{minorMode ? "Speaker Repeat Mode is active. Audience channel controls are locked in the capture route." : `Current simulated billing state: ${billingState.replaceAll("_", " ")}.`}</Notice></Card>
  </>;
}

function AttendeeSettings({ plan, questions, notes, onPlan }: { plan: "free" | "personal" | "education"; questions: number; notes: number; onPlan: (plan: "free" | "personal" | "education") => void }) {
  return <>
    <Text style={styles.section}>PARTICIPANT ACCESS</Text>
    <Card><View style={styles.cardHead}><View style={styles.cardCopy}><Text style={styles.cardTitle}>Questions, notes, and saved outcomes</Text><Text style={styles.helper}>Use a free allowance in permitted meetings. An account is still needed to save an outcome.</Text></View><StatusPill label={plan.toUpperCase()} tone={plan === "free" ? "warn" : "good"} /></View><KeyValue label="Question allowance" value={`${questions} remaining`} accent={questions ? palette.lime : palette.amber} /><KeyValue label="Personal note allowance" value={`${notes} remaining`} accent={notes ? palette.lime : palette.amber} /><View style={styles.buttonStack}><PrimaryButton label="Use free access" tone="outline" icon="card-membership" onPress={() => onPlan("free")} /><PrimaryButton label="Try personal access" icon="person" onPress={() => onPlan("personal")} /><PrimaryButton label="Try education access" tone="outline" icon="school" onPress={() => onPlan("education")} /></View></Card>
  </>;
}

function WorkspaceControlSettings({ privacy }: { privacy: boolean }) {
  return <>
    <Text style={styles.section}>{privacy ? "PRIVACY OPERATIONS" : "WORKSPACE CONTROL"}</Text>
    <Card><Notice tone="warn">This is a scoped prototype view. Production workspace administration needs server-enforced tenant isolation, authenticated approval, append-only audit records, and policy tests.</Notice><SettingRow icon={privacy ? "policy" : "group"} title={privacy ? "Rights and retention review" : "Workspace membership and policy"} detail={privacy ? "Review requests, legal-hold scope, retention, and receipts without exposing all private meeting content." : "Review workspace settings without receiving automatic private-content access."} badge="SIMULATED" badgeTone="warn" last /></Card>
  </>;
}

function SettingRow({ icon, title, detail, action, onPress, badge, badgeTone = "info", last = false }: { icon: keyof typeof MaterialIcons.glyphMap; title: string; detail: string; action?: string; onPress?: () => void; badge?: string; badgeTone?: "neutral" | "good" | "warn" | "danger" | "info"; last?: boolean }) {
  const content = <View style={[styles.row, last ? styles.rowLast : null]}><View style={styles.rowIcon}><MaterialIcons name={icon} color={palette.ink} size={20} /></View><View style={styles.rowCopy}><View style={styles.rowTitleLine}><Text style={styles.rowTitle}>{title}</Text>{badge ? <StatusPill label={badge} tone={badgeTone} /> : null}</View><Text style={styles.rowDetail}>{detail}</Text></View>{action ? <Text style={styles.actionText}>{action}</Text> : onPress ? <MaterialIcons name="chevron-right" color={palette.muted} size={20} /> : null}</View>;
  return onPress ? <PrimaryRowPress onPress={onPress}>{content}</PrimaryRowPress> : content;
}

function PrimaryRowPress({ children, onPress }: { children: React.ReactNode; onPress: () => void }) {
  return <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.68 : 1 })}>{children}</Pressable>;
}

const styles = StyleSheet.create({
  content: { gap: 16, paddingBottom: 28 }, section: { color: palette.muted, fontSize: 11, lineHeight: 14, fontWeight: "800", letterSpacing: 1.1, marginTop: 3 }, cardHead: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }, cardCopy: { flex: 1, gap: 2 }, cardTitle: { color: palette.ink, fontSize: 15, lineHeight: 20, fontWeight: "800" }, helper: { color: palette.muted, fontSize: 12, lineHeight: 17 }, switchLine: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 }, rowTitle: { color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: "800" }, buttonStack: { gap: 9 }, row: { minHeight: 68, paddingVertical: 10, flexDirection: "row", gap: 12, alignItems: "center", borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.line }, rowLast: { borderBottomWidth: 0 }, rowIcon: { width: 38, height: 38, borderRadius: 19, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" }, rowCopy: { flex: 1, gap: 3 }, rowTitleLine: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 6 }, rowDetail: { color: palette.muted, fontSize: 12, lineHeight: 17 }, actionText: { color: palette.blue, fontSize: 12, fontWeight: "800" },
});
