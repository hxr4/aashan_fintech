import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { ScreenContainer } from "@/components/screen-container";
import { Card, Notice, palette, PrimaryButton, ScreenTitle, StatusPill } from "@/components/sayless-ui";
import { ROLE_DETAILS, type SayLessRole, useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";

const signInRoles: SayLessRole[] = ["organizer", "attendee", "listener", "decision_owner", "workspace_admin", "privacy_admin"];

function asRole(value: string | string[] | undefined): SayLessRole | null {
  const candidate = Array.isArray(value) ? value[0] : value;
  return signInRoles.includes(candidate as SayLessRole) ? candidate as SayLessRole : null;
}

export default function SignInScreen() {
  const account = useRoleSession();
  const { session } = useSayLess();
  const params = useLocalSearchParams<{ role?: string }>();
  const initialRole = useMemo(() => asRole(params.role) ?? account.role, [params.role, account.role]);
  const [selectedRole, setSelectedRole] = useState<SayLessRole>(initialRole);
  const [submitting, setSubmitting] = useState(false);
  const [handoffError, setHandoffError] = useState<string | null>(null);

  useEffect(() => setSelectedRole(initialRole), [initialRole]);

  const continueToSignIn = async () => {
    setHandoffError(null);
    setSubmitting(true);
    try {
      await account.beginSignIn(selectedRole);
    } catch {
      setHandoffError("We could not open the account provider. Check your connection, then try again. You can still join a shared meeting as a QR guest.");
    } finally {
      setSubmitting(false);
    }
  };

  const accountError = handoffError ?? (account.authError ? "We could not check your account right now. Try again, or continue as a QR guest for a shared meeting." : null);

  if (account.loading) {
    return <ScreenContainer edges={["top", "bottom", "left", "right"]} className="px-5"><View style={styles.loading}><ActivityIndicator color={palette.ink} /><Text style={styles.loadingText}>Checking account access…</Text></View></ScreenContainer>;
  }

  if (account.isAuthenticated) {
    router.replace("/account" as any);
    return null;
  }

  return <ScreenContainer edges={["top", "bottom", "left", "right"]} className="px-5">
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
      <View style={styles.topline}>
        <Pressable accessibilityRole="button" accessibilityLabel="Go back" onPress={() => router.back()} style={({ pressed }) => [styles.iconButton, pressed && styles.pressed]}><MaterialIcons name="arrow-back" color={palette.ink} size={22} /></Pressable>
        <View style={styles.brand}><Image source={require("@/assets/images/icon.png")} style={styles.logo} accessibilityLabel="Say Less" /><Text style={styles.wordmark}>say less</Text></View>
        <StatusPill label="SECURE ENTRY" tone="info" />
      </View>

      <ScreenTitle eyebrow="Account access" title="Sign in to use your meeting role" />
      <Text style={styles.intro}>Use your workspace account to create meetings, save permitted outcomes, or work in an assigned role. Guest participation never requires sign-in.</Text>
      {accountError ? <Notice tone="danger">{accountError}</Notice> : null}

      <Card style={styles.card}>
        <Text style={styles.cardEyebrow}>CHOOSE A ROLE</Text>
        <Text style={styles.cardTitle}>How will you use Say Less?</Text>
        <Text style={styles.cardBody}>The role only changes the prototype view. Production access must still be enforced by workspace policy.</Text>
        <View style={styles.roleList}>
          {signInRoles.map((role) => {
            const detail = ROLE_DETAILS[role];
            const active = selectedRole === role;
            return <Pressable key={role} accessibilityRole="radio" accessibilityState={{ selected: active }} accessibilityLabel={`Use ${detail.label}`} onPress={() => setSelectedRole(role)} style={({ pressed }) => [styles.roleRow, active && styles.roleRowActive, pressed && styles.pressed]}>
              <View style={[styles.roleIcon, active && styles.roleIconActive]}><MaterialIcons name={role === "organizer" ? "mic-none" : role === "decision_owner" ? "assignment-turned-in" : role.includes("admin") ? "admin-panel-settings" : "person-outline"} size={19} color={active ? palette.surface : palette.ink} /></View>
              <View style={styles.roleCopy}><Text style={styles.roleTitle}>{detail.label}</Text><Text style={styles.roleDescription}>{detail.description}</Text></View>
              <MaterialIcons name={active ? "radio-button-checked" : "radio-button-unchecked"} size={21} color={active ? palette.lime : palette.muted} />
            </Pressable>;
          })}
        </View>
        <PrimaryButton label={submitting ? "Opening secure sign-in…" : `Continue as ${ROLE_DETAILS[selectedRole].shortLabel}`} icon="login" disabled={submitting} onPress={continueToSignIn} />
      </Card>

      <Notice tone="info">Say Less will open the supported account provider. This prototype does not collect or store a password in the app.</Notice>
      <View style={styles.guestBlock}><Text style={styles.guestTitle}>Joining a meeting only?</Text><Text style={styles.guestBody}>Open the meeting notice, record consent or withdrawal, and ask a private question without an account.</Text><PrimaryButton label="Continue as QR guest" tone="outline" icon="qr-code-2" onPress={() => router.push(`/guest/${session.code}` as any)} /></View>
    </ScrollView>
  </ScreenContainer>;
}

const styles = StyleSheet.create({
  content: { paddingTop: 10, paddingBottom: 28, gap: 16 },
  loading: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  loadingText: { color: palette.muted, fontSize: 14, lineHeight: 20, fontWeight: "700" },
  topline: { minHeight: 44, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  iconButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: palette.soft },
  brand: { flexDirection: "row", alignItems: "center", gap: 8, marginLeft: "auto", marginRight: 12 },
  logo: { width: 28, height: 28, borderRadius: 7 },
  wordmark: { color: palette.ink, fontSize: 17, lineHeight: 22, fontWeight: "900", letterSpacing: -0.7 },
  intro: { color: palette.muted, fontSize: 15, lineHeight: 22, marginTop: -7 },
  card: { gap: 13, padding: 18 },
  cardEyebrow: { color: palette.muted, fontSize: 11, lineHeight: 15, fontWeight: "900", letterSpacing: 1.05 },
  cardTitle: { color: palette.ink, fontSize: 20, lineHeight: 26, fontWeight: "900", letterSpacing: -0.25 },
  cardBody: { color: palette.muted, fontSize: 13, lineHeight: 19 },
  roleList: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: palette.line, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.line },
  roleRow: { minHeight: 68, paddingVertical: 10, flexDirection: "row", alignItems: "center", gap: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.line },
  roleRowActive: { backgroundColor: "#F0F8F4" },
  roleIcon: { width: 36, height: 36, borderRadius: 18, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center", marginLeft: 2 },
  roleIconActive: { backgroundColor: palette.ink },
  roleCopy: { flex: 1, gap: 1 },
  roleTitle: { color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: "800" },
  roleDescription: { color: palette.muted, fontSize: 11, lineHeight: 15, paddingRight: 3 },
  guestBlock: { gap: 8, paddingHorizontal: 4, paddingTop: 5 },
  guestTitle: { color: palette.ink, fontSize: 16, lineHeight: 21, fontWeight: "800" },
  guestBody: { color: palette.muted, fontSize: 13, lineHeight: 19 },
  pressed: { opacity: 0.68 },
});
