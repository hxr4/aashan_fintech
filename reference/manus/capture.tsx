import { useEffect, useMemo, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import MaterialIcons from "@expo/vector-icons/MaterialIcons";
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from "expo-audio";
import { useRouter } from "expo-router";
import { ScreenContainer } from "@/components/screen-container";
import { LiveCaptureAwake } from "@/components/live-capture-awake";
import { Card, EmptyState, KeyValue, Notice, PrimaryButton, ScreenTitle, SectionLabel, StatusPill, palette } from "@/components/sayless-ui";
import { haptic } from "@/lib/haptics";
import { useRoleSession } from "@/lib/role-session";
import { useSayLess } from "@/lib/sayless-store";
import type { CaptureSource } from "@/shared/domain";

const sourceOptions: { id: CaptureSource; name: string; detail: string; icon: keyof typeof MaterialIcons.glyphMap }[] = [
  { id: "phone_ambient", name: "Phone Ambient", detail: "One local room source", icon: "phone-android" },
  { id: "kit_dual_channel", name: "Duo Kit", detail: "Speaker + audience channels", icon: "settings-input-component" },
  { id: "browser_meeting", name: "Browser meeting", detail: "Consent-first companion handoff", icon: "language" },
  { id: "hybrid_meeting", name: "Hybrid", detail: "Local and browser sources labelled", icon: "groups" },
  { id: "approved_import", name: "Approved import", detail: "Receipt only — no phone audio", icon: "upload-file" },
];

const stateLabel = (state: string) => state.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function CaptureScreen() {
  const router = useRouter();
  const store = useSayLess();
  const { role, isAuthenticated } = useRoleSession();
  const { session, micPermission, preflightReady, networkAvailable, isMinorOrUnverified, setMicPermission, setPreflightReady, setNetworkAvailable, setMinorOrUnverified, markConsentReady, startCapture, pauseCapture, recordLocalChunk, stopCapture, simulateSync, runSimulatedAi, selectPhoneAmbient, selectSubscriberKit, selectBrowserMeeting, selectHybridMeeting, selectApprovedImport } = store;
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);
  const [permissionBusy, setPermissionBusy] = useState(false);
  const isCapturing = session.state === "capturing_offline";
  const queued = session.queue.filter((chunk) => chunk.status === "queued").length;
  const acknowledged = session.queue.filter((chunk) => chunk.status === "acknowledged").length;
  const canRecord = session.state === "offline_ready" && (session.source === "approved_import" || (micPermission && preflightReady));
  const elapsed = useMemo(() => `${Math.floor((recorderState.durationMillis ?? 0) / 60000).toString().padStart(2, "0")}:${Math.floor(((recorderState.durationMillis ?? 0) / 1000) % 60).toString().padStart(2, "0")}`, [recorderState.durationMillis]);
  const organizer = isAuthenticated && role === "organizer";

  useEffect(() => { setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true }).catch(() => undefined); }, []);

  const chooseSource = (source: CaptureSource) => {
    if (source === "phone_ambient") selectPhoneAmbient();
    else if (source === "kit_dual_channel") { if (!selectSubscriberKit()) router.push("/kit" as any); }
    else if (source === "browser_meeting") selectBrowserMeeting();
    else if (source === "hybrid_meeting") selectHybridMeeting();
    else selectApprovedImport();
  };

  const requestMic = async () => {
    setPermissionBusy(true);
    try {
      const result = await requestRecordingPermissionsAsync();
      setMicPermission(result.granted);
      if (!result.granted) Alert.alert("Microphone permission is off", "Phone Ambient cannot start until microphone access is allowed. You can still use an approved import or browser handoff.");
      else haptic.success();
    } catch { Alert.alert("Permission could not be checked", "No capture has started. Try again or choose another allowed source."); }
    finally { setPermissionBusy(false); }
  };

  const beginRecording = async () => {
    if (!startCapture()) { Alert.alert("Finish the setup first", "Record consent, complete preflight, and allow the microphone before starting local capture."); return; }
    try { await recorder.prepareToRecordAsync(); recorder.record(); haptic.success(); }
    catch { pauseCapture(); Alert.alert("Recording did not start", "No audio was added to the meeting. Check the microphone and try again."); }
  };

  const finishRecording = async () => {
    try { if (recorderState.isRecording) await recorder.stop(); recordLocalChunk(recorder.uri); stopCapture(); haptic.success(); }
    catch { stopCapture(); Alert.alert("Stopped safely", "No raw-audio receipt was created. Say Less will not claim otherwise."); }
  };

  if (!organizer) return <ScreenContainer className="px-5 pt-2"><ScrollView contentContainerStyle={styles.content}><ScreenTitle eyebrow="Meeting capture" title="Hosts start new meetings." /><Card><EmptyState icon="mic-off" title="Capture controls are not shared" body={isAuthenticated ? "Your role can join, ask questions, save private notes, and complete assigned work. Recording sources, consent setup, hardware, and retention controls belong to the meeting host." : "Guests can join one meeting from a QR link without an account after viewing its notice and recording a participation choice."} action={<PrimaryButton label={isAuthenticated ? "Open my meetings" : "Open guest meeting"} icon={isAuthenticated ? "calendar-today" : "open-in-new"} onPress={() => router.push((isAuthenticated ? "/operations" : `/guest/${session.code}`) as any)} />} /></Card></ScrollView></ScreenContainer>;

  return <ScreenContainer className="px-5 pt-2"><ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>{isCapturing ? <LiveCaptureAwake /> : null}
    <ScreenTitle eyebrow="New meeting" title={isCapturing ? "Capture is live" : "Start with consent"} action={<StatusPill label={stateLabel(session.state)} tone={isCapturing ? "good" : session.state === "consent_required" ? "warn" : "neutral"} />}/>

    {isMinorOrUnverified ? <Notice tone="warn">Speaker Repeat Mode is active. Audience capture stays off for this meeting.</Notice> : null}
    {session.state === "consent_required" ? <Card><Text style={styles.cardTitle}>Before anyone speaks</Text><Text style={styles.body}>Share the purpose and capture notice. Everyone must know what will be recorded and how long the raw audio will remain available.</Text><View style={styles.switchRow}><View style={{ flex: 1 }}><Text style={styles.switchTitle}>Minor or unverified classroom</Text><Text style={styles.switchHelp}>Uses Speaker Repeat Mode and blocks audience capture.</Text></View><Switch value={isMinorOrUnverified} onValueChange={setMinorOrUnverified} trackColor={{ false: palette.line, true: palette.amber }} thumbColor={palette.white} /></View><PrimaryButton label="Record required consent" icon="verified-user" onPress={markConsentReady}/></Card> : null}

    <SectionLabel>Capture source</SectionLabel>
    <View style={styles.sourceGrid}>{sourceOptions.map((option) => <Pressable key={option.id} onPress={() => chooseSource(option.id)} style={({ pressed }) => [styles.sourceTile, session.source === option.id && styles.sourceTileActive, { opacity: pressed ? 0.72 : 1 }]}><MaterialIcons name={option.icon} size={21} color={session.source === option.id ? palette.white : palette.ink}/><Text style={[styles.sourceName, session.source === option.id && { color: palette.white }]}>{option.name}</Text><Text style={[styles.sourceDetail, session.source === option.id && { color: "#DDE6F3" }]}>{option.detail}</Text></Pressable>)}</View>
    {session.source === "kit_dual_channel" ? <Notice tone="good">Duo Kit labels Speaker and Audience channels separately in every capture receipt.</Notice> : session.source === "phone_ambient" ? <Notice tone="info">Phone Ambient is one room source. It is not a two-channel microphone kit.</Notice> : session.source === "approved_import" ? <Notice tone="info">An import creates a provenance receipt. The phone microphone is not used or claimed.</Notice> : session.source === "browser_meeting" ? <Notice tone="info">The browser companion provides a consent-first handoff. This demo does not claim live tab capture.</Notice> : null}

    <Card><View style={styles.row}><View><Text style={styles.cardTitle}>Ready check</Text><Text style={styles.body}>Only the checks needed for your chosen source are shown.</Text></View><StatusPill label={canRecord ? "Ready" : "Setup"} tone={canRecord ? "good" : "warn"}/></View>
      {session.source !== "approved_import" ? <><KeyValue label="Microphone access" value={micPermission ? "Allowed" : "Needed"} accent={micPermission ? palette.lime : palette.amber}/><KeyValue label="Preflight" value={preflightReady ? "Complete" : "Not complete"} accent={preflightReady ? palette.lime : palette.amber}/><View style={styles.buttonGap}><PrimaryButton label={permissionBusy ? "Checking permission…" : micPermission ? "Microphone allowed" : "Allow microphone"} disabled={permissionBusy || micPermission} onPress={requestMic} tone={micPermission ? "outline" : "paper"} icon="mic"/><PrimaryButton label={preflightReady ? "Preflight complete" : "Complete preflight"} disabled={preflightReady} onPress={() => { setPreflightReady(true); haptic.success(); }} tone={preflightReady ? "outline" : "lime"} icon="check-circle"/></View></> : <Notice tone="good">This source does not need local microphone permission. Its provenance receipt is the preflight record.</Notice>}</Card>

    <Card style={isCapturing ? styles.liveCard : undefined}><View style={styles.row}><View><Text style={styles.cardTitle}>{isCapturing ? elapsed : "Local capture"}</Text><Text style={styles.body}>{isCapturing ? "Recording locally. A visible indicator stays on." : queued ? `${queued} chunk${queued === 1 ? "" : "s"} are safely queued on this device.` : "Nothing is being claimed as captured."}</Text></View><StatusPill label={isCapturing ? "Live" : queued ? "Queued" : "Standby"} tone={isCapturing ? "good" : queued ? "warn" : "neutral"}/></View>
      {isCapturing ? <><PrimaryButton label="Stop and save local chunk" tone="coral" icon="stop-circle" onPress={finishRecording}/><Pressable onPress={() => { recordLocalChunk(null); haptic.light(); }}><Text style={styles.textAction}>Add a 5-second demo chunk</Text></Pressable></> : session.source === "approved_import" ? <PrimaryButton label="Add approved import receipt" icon="upload-file" disabled={session.state !== "offline_ready"} onPress={() => { recordLocalChunk(null); haptic.success(); }}/> : <PrimaryButton label={canRecord ? "Start local capture" : "Finish setup to capture"} disabled={!canRecord} icon="fiber-manual-record" onPress={beginRecording}/>}</Card>

    <Card><View style={styles.row}><View><Text style={styles.cardTitle}>Sync and live understanding</Text><Text style={styles.body}>Content is interactive only after its receipt is acknowledged. Gaps stay visible.</Text></View><StatusPill label={networkAvailable ? "Online" : "Offline"} tone={networkAvailable ? "good" : "warn"}/></View><View style={styles.switchRow}><Text style={styles.switchTitle}>Connection available</Text><Switch value={networkAvailable} onValueChange={setNetworkAvailable} trackColor={{ false: palette.line, true: palette.lime }} thumbColor={palette.white}/></View><KeyValue label="Waiting on device" value={`${queued} chunks`}/><KeyValue label="Acknowledged" value={`${acknowledged} chunks`} accent={acknowledged ? palette.lime : undefined}/><View style={styles.buttonGap}><PrimaryButton label="Send queued chunks" disabled={!networkAvailable || !queued} icon="cloud-upload" onPress={() => simulateSync(false)}/><PrimaryButton label="Mark an audio gap" disabled={!networkAvailable || !queued} tone="outline" icon="warning-amber" onPress={() => simulateSync(true)}/>{session.state === "synced_pending_ai" ? <PrimaryButton label="Create review proposals" tone="paper" icon="auto-awesome" onPress={runSimulatedAi}/> : null}</View></Card>
    <PrimaryButton label="Manage Duo Kit" tone="outline" icon="settings-input-component" onPress={() => router.push("/kit" as any)}/>
  </ScrollView></ScreenContainer>;
}

const styles = StyleSheet.create({
  content: { gap: 15, paddingBottom: 30 }, cardTitle: { color: palette.ink, fontSize: 18, lineHeight: 24, fontWeight: "800" }, body: { color: palette.muted, fontSize: 13, lineHeight: 19, marginTop: 4 }, row: { flexDirection: "row", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }, switchRow: { flexDirection: "row", gap: 12, alignItems: "center", paddingVertical: 4 }, switchTitle: { color: palette.ink, fontSize: 14, lineHeight: 19, fontWeight: "700" }, switchHelp: { color: palette.muted, fontSize: 12, lineHeight: 17, marginTop: 2 }, sourceGrid: { flexDirection: "row", flexWrap: "wrap", gap: 9 }, sourceTile: { width: "48%", flexGrow: 1, minHeight: 112, borderRadius: 16, backgroundColor: palette.surface, borderWidth: 1, borderColor: palette.line, padding: 13, gap: 6 }, sourceTileActive: { backgroundColor: palette.ink, borderColor: palette.ink }, sourceName: { color: palette.ink, fontSize: 14, lineHeight: 18, fontWeight: "800", marginTop: 3 }, sourceDetail: { color: palette.muted, fontSize: 11, lineHeight: 15 }, buttonGap: { gap: 9 }, textAction: { color: palette.blue, fontSize: 13, lineHeight: 18, fontWeight: "800", textAlign: "center", paddingTop: 2 }, liveCard: { borderColor: "#A8DCC4", backgroundColor: "#F4FCF8" },
});
