import { PropsWithChildren, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View, type ViewStyle } from "react-native";
import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { haptic } from "@/lib/haptics";

export const palette = {
  canvas: "#F7F7F2",
  surface: "#FFFFFF",
  ink: "#111827",
  paper: "#111827",
  muted: "#64748B",
  mist: "#64748B",
  line: "#E6E8EC",
  soft: "#F1F3F5",
  lime: "#1F9D67",
  amber: "#C9831B",
  coral: "#E65C4F",
  blue: "#2563EB",
  slate: "#FFFFFF",
  white: "#FFFFFF",
  navy: "#172033",
};

export function ScreenTitle({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return <View style={styles.titleRow}><View style={styles.titleCopy}>{eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}<Text style={styles.title}>{title}</Text></View>{action}</View>;
}

export function Card({ children, style }: PropsWithChildren<{ style?: ViewStyle }>) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function StatusPill({ label, tone = "neutral" }: { label: string; tone?: "neutral" | "good" | "warn" | "danger" | "info" }) {
  const color = tone === "good" ? palette.lime : tone === "warn" ? palette.amber : tone === "danger" ? palette.coral : tone === "info" ? palette.blue : palette.muted;
  return <View style={[styles.pill, { backgroundColor: `${color}12` }]}><View style={[styles.dot, { backgroundColor: color }]} /><Text style={[styles.pillText, { color }]}>{label}</Text></View>;
}

export function PrimaryButton({ label, onPress, tone = "lime", disabled = false, icon }: { label: string; onPress: () => void; tone?: "lime" | "coral" | "paper" | "outline"; disabled?: boolean; icon?: keyof typeof MaterialIcons.glyphMap }) {
  const isPrimary = tone === "lime";
  const isCoral = tone === "coral";
  const background = isPrimary ? palette.ink : isCoral ? palette.coral : tone === "paper" ? palette.surface : "transparent";
  const textColor = isPrimary || isCoral ? palette.white : palette.ink;
  return <Pressable accessibilityRole="button" disabled={disabled} onPress={() => { haptic.light(); onPress(); }} style={({ pressed }) => [styles.button, { backgroundColor: background, borderColor: tone === "outline" || tone === "paper" ? palette.line : background, opacity: disabled ? 0.42 : pressed ? 0.84 : 1, transform: [{ scale: pressed ? 0.985 : 1 }] }]}><View style={styles.buttonInner}>{icon ? <MaterialIcons name={icon} size={19} color={textColor} /> : null}<Text style={[styles.buttonText, { color: textColor }]}>{label}</Text></View></Pressable>;
}

export function IconButton({ icon, label, onPress, tone = "default" }: { icon: keyof typeof MaterialIcons.glyphMap; label: string; onPress: () => void; tone?: "default" | "danger" }) {
  const color = tone === "danger" ? palette.coral : palette.ink;
  return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={() => { haptic.light(); onPress(); }} style={({ pressed }) => [styles.iconButton, { opacity: pressed ? 0.62 : 1 }]}><MaterialIcons name={icon} size={21} color={color} /></Pressable>;
}

export function KeyValue({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return <View style={styles.keyValue}><Text style={styles.key}>{label}</Text><Text style={[styles.value, accent ? { color: accent } : null]}>{value}</Text></View>;
}

export function Notice({ tone = "info", children }: PropsWithChildren<{ tone?: "info" | "warn" | "danger" | "good" }>) {
  const color = tone === "good" ? palette.lime : tone === "warn" ? palette.amber : tone === "danger" ? palette.coral : palette.blue;
  const icon = tone === "danger" ? "error-outline" : tone === "warn" ? "warning-amber" : tone === "good" ? "verified" : "info-outline";
  return <View style={[styles.notice, { backgroundColor: `${color}10` }]}><MaterialIcons name={icon} color={color} size={19} /><Text style={styles.noticeText}>{children}</Text></View>;
}

export function SectionLabel({ children }: PropsWithChildren) { return <Text style={styles.sectionLabel}>{children}</Text>; }

export function EmptyState({ icon, title, body, action }: { icon: keyof typeof MaterialIcons.glyphMap; title: string; body: string; action?: ReactNode }) {
  return <View style={styles.empty}><View style={styles.emptyIcon}><MaterialIcons name={icon} size={24} color={palette.ink} /></View><Text style={styles.emptyTitle}>{title}</Text><Text style={styles.emptyBody}>{body}</Text>{action}</View>;
}

export const styles = StyleSheet.create({
  titleRow: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18, gap: 12 },
  titleCopy: { flex: 1 },
  eyebrow: { color: palette.muted, fontWeight: "700", fontSize: 13, lineHeight: 18, marginBottom: 3 },
  title: { color: palette.ink, fontSize: 30, lineHeight: 36, fontWeight: "800", letterSpacing: -0.7 },
  card: { backgroundColor: palette.surface, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: palette.line, gap: 12 },
  pill: { flexDirection: "row", alignItems: "center", alignSelf: "flex-start", borderRadius: 999, paddingHorizontal: 9, paddingVertical: 6, gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  pillText: { fontSize: 11, lineHeight: 14, fontWeight: "800", letterSpacing: 0.2 },
  button: { minHeight: 50, borderRadius: 14, paddingHorizontal: 16, justifyContent: "center", borderWidth: 1 },
  buttonInner: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 8 },
  buttonText: { fontSize: 15, lineHeight: 20, fontWeight: "800", textAlign: "center" },
  iconButton: { width: 44, height: 44, borderRadius: 22, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center" },
  keyValue: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: palette.line, paddingBottom: 10 },
  key: { color: palette.muted, fontSize: 13, lineHeight: 18, flex: 1 },
  value: { color: palette.ink, fontSize: 13, lineHeight: 18, fontWeight: "700", textAlign: "right", flex: 1 },
  notice: { flexDirection: "row", gap: 9, padding: 12, borderRadius: 14 },
  noticeText: { color: palette.ink, fontSize: 13, lineHeight: 18, flex: 1 },
  sectionLabel: { color: palette.muted, fontSize: 13, lineHeight: 18, fontWeight: "800", marginTop: 7 },
  empty: { alignItems: "center", paddingHorizontal: 20, paddingVertical: 30, gap: 8 },
  emptyIcon: { width: 48, height: 48, borderRadius: 24, backgroundColor: palette.soft, alignItems: "center", justifyContent: "center", marginBottom: 3 },
  emptyTitle: { color: palette.ink, fontSize: 17, lineHeight: 22, fontWeight: "800", textAlign: "center" },
  emptyBody: { color: palette.muted, fontSize: 14, lineHeight: 20, textAlign: "center" },
});
