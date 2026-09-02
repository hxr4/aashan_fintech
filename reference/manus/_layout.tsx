import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { Tabs } from "expo-router";
import { Platform } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { palette } from "@/components/sayless-ui";
import { useRoleSession } from "@/lib/role-session";

const icons = { index: "home-filled", capture: "mic-none", memory: "account-tree", operations: "calendar-month", settings: "tune" } as const;

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  const { role, isAuthenticated } = useRoleSession();
  const bottom = Platform.OS === "web" ? 10 : Math.max(10, insets.bottom);
  const organizerControls = isAuthenticated && role === "organizer";
  return <Tabs screenOptions={({ route }) => ({
    headerShown: false,
    tabBarActiveTintColor: palette.ink,
    tabBarInactiveTintColor: palette.muted,
    tabBarStyle: { height: 60 + bottom, paddingTop: 8, paddingBottom: bottom, backgroundColor: palette.surface, borderTopColor: palette.line, borderTopWidth: 1 },
    tabBarLabelStyle: { fontSize: 10, fontWeight: "700" },
    tabBarIcon: ({ color, size }) => <MaterialIcons name={icons[route.name as keyof typeof icons]} size={size} color={color} />,
  })}>
    <Tabs.Screen name="index" options={{ title: "Home" }} />
    <Tabs.Screen name="capture" options={{ title: "Capture", href: organizerControls ? undefined : null }} />
    <Tabs.Screen name="memory" options={{ title: role === "attendee" ? "Notes" : "Work" }} />
    <Tabs.Screen name="operations" options={{ title: "Meetings" }} />
    <Tabs.Screen name="settings" options={{ title: "Settings" }} />
  </Tabs>;
}
