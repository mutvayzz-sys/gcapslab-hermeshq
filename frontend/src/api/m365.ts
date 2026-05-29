import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface M365AppConfig {
  client_id: string | null;
  tenant_id: string | null;
  enabled_scopes: string[];
  available_scopes: Record<string, string>;
  configured: boolean;
}

export interface M365UserStatus {
  connected: boolean;
  account_email: string | null;
  account_name: string | null;
  scopes: string[];
  expires_at: string | null;
  revoked: boolean;
}

export interface M365ConnectFlow {
  verification_uri: string;
  user_code: string;
  expires_in: number;
}

export interface M365ConnectStatus {
  status: "pending" | "connected";
  account_email: string | null;
  account_name: string | null;
}

// ─── Admin: configuración de la instancia ────────────────────────────────────

export function useM365AppConfig() {
  return useQuery({
    queryKey: ["m365-config"],
    queryFn: async () => {
      const { data } = await apiClient.get<M365AppConfig>("/m365/config");
      return data;
    },
  });
}

export function useUpdateM365AppConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<M365AppConfig>) => {
      const { data } = await apiClient.put<M365AppConfig>("/m365/config", payload);
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["m365-config"] });
    },
  });
}

// ─── Usuario: su propia cuenta M365 ──────────────────────────────────────────

export function useMyM365Status() {
  return useQuery({
    queryKey: ["m365-me"],
    queryFn: async () => {
      const { data } = await apiClient.get<M365UserStatus>("/m365/me");
      return data;
    },
  });
}

export function useStartM365Connect() {
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<M365ConnectFlow>("/m365/me/connect");
      return data;
    },
  });
}

export function usePollM365ConnectStatus() {
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.get<M365ConnectStatus>("/m365/me/connect/status");
      return data;
    },
  });
}

export interface AgentM365Scopes {
  allowed_scopes: string[] | null;
  user_scopes: string[];
  available_scopes: Record<string, string>;
}

export function useAgentM365Scopes(agentId: string | null) {
  return useQuery({
    queryKey: ["m365-agent-scopes", agentId],
    queryFn: async () => {
      const { data } = await apiClient.get<AgentM365Scopes>(`/m365/me/agents/${agentId}/scopes`);
      return data;
    },
    enabled: Boolean(agentId),
    retry: false,
  });
}

export function useUpdateAgentM365Scopes(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (allowedScopes: string[] | null) => {
      const { data } = await apiClient.put<{ allowed_scopes: string[] | null }>(
        `/m365/me/agents/${agentId}/scopes`,
        { allowed_scopes: allowedScopes },
      );
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["m365-agent-scopes", agentId] });
    },
  });
}

export function useDisconnectM365() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await apiClient.delete("/m365/me");
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["m365-me"] });
    },
  });
}
