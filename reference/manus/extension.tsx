import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { Image, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { ScreenContainer } from "@/components/screen-container";
import { Card, EmptyState, KeyValue, Notice, palette, PrimaryButton, ScreenTitle, SectionLabel, StatusPill } from "@/components/sayless-ui";
import { useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";

export default function ExtensionHandoffScreen() {
  const router = useRouter();
  const { session, setNetworkAvailable, selectBrowserMeeting } = useSayLess();
  const { role, isAuthenticated } = useRoleSession();
  const organizer = isAuthenticated && role === "organizer";
  if (!organizer) return <ScreenContainer className="px-5 pt-2"><ScrollView contentContainerStyle={styles.content}><ScreenTitle eyebrow="Browser companion" title="Host access required" /><Card><EmptyState icon="lock-outline" title="Only a meeting host can connect a browser companion" body="Participants can use a consented QR guest link or their permitted meeting library. Browser source selection and connection controls are not shared meeting controls." action={<PrimaryButton label="Open my meetings" icon="calendar-today" onPress={() => router.push("/operations" as any)} />} /></Card></ScrollView></ScreenContainer>;

  return <ScreenContainer className="px-5 pt-2"><ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
    <View style={styles.top}><View style={styles.brand}><Image source={require("@/assets/images/icon.png")} style={styles.logo} /><Text style={styles.wordmark}>say less</Text></View><StatusPill label="HOST CONTROL" tone="info" /></View>
    <ScreenTitle eyebrow="Online meeting companion" title="Connect a browser meeting, on purpose." />
    <Notice tone="warn">This prototype shows a session handoff and remote-control foundation. It does not claim that a browser tab, desktop app, or third-party meeting is being captured now.</Notice>
    <Card style={styles.connectionCard}><View style={styles.connectionTop}><View style={styles.browserIcon}><MaterialIcons name="language" size={28} color={palette.ink} /></View><View style={styles.connectionCopy}><Text style={styles.cardTitle}>Browser connection</Text><Text style={styles.helper}>Chrome or Edge companion · host starts the connection</Text></View></View><KeyValue label="Session code" value={session.code} accent={palette.lime} /><KeyValue label="Current source" value={session.source.replaceAll("_", " ")} /><KeyValue label="Connection" value={session.source === "browser_meeting" ? "Browser source selected" : "Not connected"} accent={session.source === "browser_meeting" ? palette.lime : palette.amber} /><PrimaryButton label="Select browser meeting source" icon="language" onPress={selectBrowserMeeting} /><PrimaryButton label="Open participant guest link" tone="outline" icon="qr-code" onPress={() => router.push(`/guest/${session.code}` as any)} /></Card>
    <SectionLabel>EXPLICIT START SEQUENCE</SectionLabel>
    <Card style={styles.steps}><Step number="1" title="Host chooses the browser source" body="The source remains labelled Browser companion throughout the session." /><Step number="2" title="Participants receive the meeting notice" body="A companion must not silently request or begin capture." /><Step number="3" title="Host begins a permitted session" body="Consent, source health, and availability must be visible before capture can proceed." /></Card>
    <SectionLabel>MOBILE REMOTE</SectionLabel>
    <Card><Text style={styles.cardTitle}>Prototype remote state</Text><Text style={styles.helper}>Use this only to model the companion’s network handoff. It does not establish a real browser connection.</Text><PrimaryButton label="Mark demo handoff available" icon="wifi" onPress={() => setNetworkAvailable(true)} /><PrimaryButton label="Return to capture setup" tone="outline" icon="mic" onPress={() => router.push("/capture" as any)} /></Card>
    <SectionLabel>PLATFORM BOUNDARIES</SectionLabel>
    <Card><KeyValue label="Google Meet" value="Adapter boundary prepared; host must initiate" /><KeyValue label="Teams web" value="Adapter boundary prepared; host must initiate" /><KeyValue label="Zoom web" value="Adapter boundary prepared; host must initiate" /><KeyValue label="Desktop meeting applications" value="Not captured by a browser companion" accent={palette.coral} /><KeyValue label="Unsupported site" value="Show unsupported state; do not substitute a source" accent={palette.amber} /></Card>
  </ScrollView></ScreenContainer>;
}

function Step({ number, title, body }: { number: string; title: string; body: string }) { return <View style={styles.step}><View style={styles.stepNumber}><Text style={styles.stepNumberText}>{number}</Text></View><View style={styles.stepCopy}><Text style={styles.stepTitle}>{title}</Text><Text style={styles.helper}>{body}</Text></View></View>; }

const styles = StyleSheet.create({
  content: { gap: 15, paddingBottom: 30 }, top: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" }, brand: { flexDirection: "row", gap: 8, alignItems: "center" }, logo: { width: 29, height: 29, borderRadius: 7 }, wordmark: { color: palette.ink, fontSize: 17, lineHeight: 21, fontWeight: "900", letterSpacing: -0.7 }, connectionCard: { gap: 13 }, connectionTop: { flexDirection: "row", gap: 12, alignItems: "center" }, browserIcon: { width: 52, height: 52, borderRadius: 16, alignItems: "center", justifyContent: "center", backgroundColor: palette.lime }, connectionCopy: { flex: 1, gap: 4 }, cardTitle: { color: palette.ink, fontSize: 16, lineHeight: 21, fontWeight: "900" }, helper: { color: palette.muted, fontSize: 12, lineHeight: 17 }, steps: { gap: 0 }, step: { flexDirection: "row", gap: 11, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.line }, stepNumber: { width: 26, height: 26, borderRadius: 8, alignItems: "center", justifyContent: "center", backgroundColor: palette.soft }, stepNumberText: { color: palette.ink, fontSize: 12, fontWeight: "900" }, stepCopy: { flex: 1, gap: 3 }, stepTitle: { color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: "800" },
});
