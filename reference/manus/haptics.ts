import { Platform } from "react-native";
import * as Haptics from "expo-haptics";

export const haptic = {
  light: () => Platform.OS !== "web" && Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light),
  medium: () => Platform.OS !== "web" && Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium),
  success: () => Platform.OS !== "web" && Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
  warning: () => Platform.OS !== "web" && Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning),
  error: () => Platform.OS !== "web" && Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error),
};
