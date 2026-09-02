import { createContext, PropsWithChildren, useContext, useMemo, useState } from "react";
import { startOAuthLogin } from "@/constants/oauth";
import { useAuth } from "@/hooks/use-auth";

export type SayLessRole = "organizer" | "attendee" | "listener" | "decision_owner" | "workspace_admin" | "privacy_admin";

export const ROLE_DETAILS: Record<SayLessRole, { label: string; shortLabel: string; description: string }> = {
  organizer: { label: "Meeting organizer", shortLabel: "Organizer", description: "Creates sessions, manages capture and consent, and reviews proposed work." },
  attendee: { label: "Participant", shortLabel: "Participant", description: "Joins permitted meetings, asks questions, keeps personal notes, and saves shared outcomes." },
  listener: { label: "Listener", shortLabel: "Listener", description: "Reads only the meeting outcomes and evidence shared with them." },
  decision_owner: { label: "Decision owner", shortLabel: "Decision owner", description: "Acts on assigned work while keeping the linked evidence unchanged." },
  workspace_admin: { label: "Workspace administrator", shortLabel: "Workspace admin", description: "Reviews workspace policy and access settings without automatic private-content access." },
  privacy_admin: { label: "Privacy administrator", shortLabel: "Privacy admin", description: "Reviews privacy, retention, and receipt controls through an audited workspace route." },
};

type RoleSessionValue = {
  role: SayLessRole;
  userName: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  authError: Error | null;
  chooseRole: (role: SayLessRole) => void;
  beginSignIn: (role: SayLessRole) => Promise<void>;
  logout: () => Promise<void>;
};

const RoleSessionContext = createContext<RoleSessionValue | null>(null);

export function RoleSessionProvider({ children }: PropsWithChildren) {
  const { user, loading, error, isAuthenticated, logout } = useAuth();
  const [role, setRole] = useState<SayLessRole>("attendee");

  const beginSignIn = async (requestedRole: SayLessRole) => {
    setRole(requestedRole);
    await startOAuthLogin();
  };

  const value = useMemo<RoleSessionValue>(() => ({
    role,
    userName: user?.name ?? null,
    isAuthenticated,
    loading,
    authError: error,
    chooseRole: setRole,
    beginSignIn,
    logout,
  }), [role, user?.name, isAuthenticated, loading, error, logout]);

  return <RoleSessionContext.Provider value={value}>{children}</RoleSessionContext.Provider>;
}

export function useRoleSession() {
  const value = useContext(RoleSessionContext);
  if (!value) throw new Error("useRoleSession must be used within RoleSessionProvider");
  return value;
}
