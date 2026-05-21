import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import { resolveApiBase } from "../lib/apiBase";
import { cachePublicThemeMode } from "../lib/theme";
import type { AppSettings } from "../types/api";

const apiBase = resolveApiBase();
const apiRoot = apiBase.replace(/\/api$/, "");

export function resolveAssetUrl(path: string | null | undefined) {
  if (!path) {
    return null;
  }
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  return `${apiRoot}${path.startsWith("/") ? path : `/${path}`}`;
}

export function useSettings(enabled = true) {
  return useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const { data } = await apiClient.get<AppSettings>("/settings");
      return data;
    },
    enabled,
  });
}

export function usePublicBranding() {
  return useQuery({
    queryKey: ["branding", "public"],
    queryFn: async () => {
      const { data } = await apiClient.get<AppSettings>("/settings/public");
      cachePublicThemeMode(data.theme_mode);
      return data;
    },
    staleTime: 0,
    refetchOnMount: "always",
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const { data } = await apiClient.put<AppSettings>("/settings", payload);
      return data;
    },
    onSuccess: async (data) => {
      cachePublicThemeMode(data.theme_mode);
      queryClient.setQueryData(["branding", "public"], data);
      queryClient.setQueryData(["settings"], data);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["branding", "public"] });
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
      await queryClient.invalidateQueries({ queryKey: ["hermes-versions"] });
    },
  });
}

export function useUploadBrandAsset(kind: "logo" | "favicon") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post<AppSettings>(`/settings/branding/${kind}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["branding", "public"] });
    },
  });
}

export function useDeleteBrandAsset(kind: "logo" | "favicon") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.delete<AppSettings>(`/settings/branding/${kind}`);
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["branding", "public"] });
    },
  });
}

export function useUploadTuiSkin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post<AppSettings>("/settings/tui-skin", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["branding", "public"] });
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}

export function useDeleteTuiSkin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.delete<AppSettings>("/settings/tui-skin");
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["branding", "public"] });
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}

// ── Resource endpoints ─────────────────────────────────────────────────────

export interface ResourceStatus {
  semaphore: {
    current: number;
    active_tasks: number;
    max_tasks: number;
    utilization_pct: number;
  };
  container: {
    memory_limit_mb: number | null;
    memory_usage_mb: number | null;
    cpu_limit: number | null;
    cpu_usage_pct: number | null;
  };
  system: {
    total_ram_mb: number;
    available_ram_mb: number;
    cpu_cores: number;
    disk_available_gb: number;
  };
  estimate: {
    agents: number;
    concurrent: number;
    semaphore: number;
    ram_backend_mb: number;
    ram_postgres_mb: number;
    cpu_needed: number;
    disk_gb: number;
  } | null;
}

export function useResourceStatus(enabled = true) {
  return useQuery({
    queryKey: ["settings", "resources"],
    queryFn: async () => {
      const { data } = await apiClient.get<ResourceStatus>("/settings/resources");
      return data;
    },
    enabled,
    refetchInterval: 10_000,
  });
}

export function useUpdateSemaphore() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (semaphore: number) => {
      const { data } = await apiClient.put<{ semaphore: number; restart_required: boolean }>(
        "/settings/resources/semaphore",
        { semaphore },
      );
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "resources"] });
    },
  });
}

export function useGenerateOverride() {
  return useMutation({
    mutationFn: async (agents: number) => {
      const { data } = await apiClient.post<{
        content: string;
        agents: number;
        semaphore: number;
        applied: boolean;
        restart_required: boolean;
      }>("/settings/resources/generate-override", { agents });
      return data;
    },
  });
}
