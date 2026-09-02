import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { ScreenContainer } from "@/components/screen-container";
import { Card, Notice, palette, PrimaryButton, ScreenTitle, StatusPill } from "@/components/sayless-ui";
import { ROLE_DETAILS, SayLessRole, useRoleSession } from "@/lib/role-session";

const roleOrder: SayLessRole[] = ["organizer", "attendee", "listener", "decision_owner", "workspace_admin", "privacy_admin"];

function RoleRow({ role }: { role: SayLessRole }) {
  const account = useRoleSession();
  const detail = ROLE_DETAILS[role];
  const active = account.role === role;
  const label = !account.isAuthenticated ? `Sign in as ${detail.shortLabel}` : active ? `${detail.shortLabel} selected` : `Use ${detail.shortLabel} view`;

  return <Pressable
    accessibilityRole="button"
    accessibilityLabel={label}
    onPress={() => account.isAuthenticated ? account.chooseRole(role) : account.beginSignIn(role)}
    style={({ pressed }) => [styles.roleRow, active ? styles.roleRowActive : null, pressed ? styles.pressed : null]}
  >
    <View style={[styles.roleIcon, active ? styles.roleIconActive : null]}><MaterialIcons name={role === "organizer" ? "mic-none" : role === "decision_owner" ? "assignment-turned-in" : role.includes("admin") ? "admin-panel-settings" : "person-outline"} size={20} color={active ? palette.surface : palette.ink} /></View>
    <View style={styles.roleCopy}><Text style={styles.roleTitle}>{detail.label}</Text><Text style={styles.roleBody}>{detail.description}</Text></View>
    <MaterialIcons name={active ? "check-circle" : "chevron-right"} size={21} color={active ? palette.lime : palette.muted} />
  </Pressable>;
}

export default function AccountScreen() {
  const account = useRoleSession();
  const current = ROLE_DETAILS[account.role];

  return <ScreenContainer edges={["top", "bottom", "left", "right"]}>
    <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
      <ScreenTitle eyebrow="Access" title="Your Say Less role" action={<Pressable accessibilityRole="button" accessibilityLabel="Close account screen" onPress={() => router.back()} style={styles.close}><MaterialIcons name="close" color={palette.ink} size={21} /></Pressable>} />
      {account.loading ? <Card><View style={styles.loading}><ActivityIndicator color={palette.ink} /><Text style={styles.loadingText}>Checking your account access…</Text></View></Card> : null}
      {!account.loading && !account.isAuthenticated ? <>
        <Notice tone="info">You can join a QR meeting without an account. Sign in only to create a meeting, save permitted outcomes, or use a workspace role.</Notice>
        <Card>
          <Text style={styles.cardTitle}>Choose how you’ll use Say Less</Text>
          <Text style={styles.cardBody}>Your account is required before the selected role can access any workspace content. This prototype does not claim that a role assignment is production authorization.</Text>
        </Card>
      </> : null}
      {!account.loading && account.isAuthenticated ? <Card>
        <View style={styles.signedInRow}><View><Text style={styles.cardTitle}>{account.userName ?? "Signed-in account"}</Text><Text style={styles.cardBody}>Current workspace view: {current.shortLabel}</Text></View><StatusPill label="Signed in" tone="good" /></View>
        <PrimaryButton label="Sign out" tone="outline" icon="logout" onPress={() => account.logout()} />
      </Card> : null}
      {account.authError ? <Notice tone="danger">Account status could not be confirmed. Try again before using account-only controls.</Notice> : null}
      <Text style={styles.sectionLabel}>{account.isAuthenticated ? "Switch prototype role" : "Sign in to this role"}</Text>
      <View style={styles.roles}>{roleOrder.map((role) => <RoleRow key={role} role={role} />)}</View>
      {!account.isAuthenticated ? <Text style={styles.footnote}>Guest actions remain available through a meeting QR link. No account is requested for notice, consent, withdrawal, or a private question.</Text> : <Text style={styles.footnote}>Role selection is a prototype control. Production workspace authorization, SSO, and privacy administration require server-enforced policies and audit checks.</Text>}
    </ScrollView>
  </ScreenContainer>;
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: 18, paddingTop: 12, paddingBottom: 28, gap: 14 },
  close: { width: 44, height: 44, borderRadius: 22, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" },
  loading: { flexDirection: "row", alignItems: "center", gap: 10 },
  loadingText: { color: palette.muted, fontSize: 14, lineHeight: 20, fontWeight: "700" },
  cardTitle: { color: palette.ink, fontSize: 17, lineHeight: 23, fontWeight: "800" },
  cardBody: { color: palette.muted, fontSize: 14, lineHeight: 20 },
  signedInRow: { flexDirection: "row", gap: 12, justifyContent: "space-between", alignItems: "flex-start" },
  sectionLabel: { color: palette.muted, fontSize: 13, lineHeight: 18, fontWeight: "800", marginTop: 5 },
  roles: { backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.line, borderRadius: 18, overflow: "hidden" },
  roleRow: { minHeight: 76, padding: 14, flexDirection: "row", gap: 12, alignItems: "center", borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.line },
  roleRowActive: { backgroundColor: "#F0F8F4" },
  roleIcon: { width: 42, height: 42, borderRadius: 21, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" },
  roleIconActive: { backgroundColor: palette.ink },
  roleCopy: { flex: 1, gap: 2 },
  roleTitle: { color: palette.ink, fontSize: 15, lineHeight: 20, fontWeight: "800" },
  roleBody: { color: palette.muted, fontSize: 12, lineHeight: 17 },
  pressed: { opacity: 0.72 },
  footnote: { color: palette.muted, fontSize: 12, lineHeight: 18, paddingHorizontal: 4 },
});
