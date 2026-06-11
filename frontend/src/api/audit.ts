import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";

export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  actor_username: string | null;
  actor_role: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  target_name: string | null;
  ip_address: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogPage {
  items: AuditLogEntry[];
  total: number;
  has_more: boolean;
}

export function useAuditLogs(filters?: {
  action?: string;
  target_type?: string;
  actor_id?: string;
  search?: string;
  cursor?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["audit", filters],
    queryFn: async () => {
      const params: Record<string, string | number> = {};
      if (filters?.action) params.action = filters.action;
      if (filters?.target_type) params.target_type = filters.target_type;
      if (filters?.actor_id) params.actor_id = filters.actor_id;
      if (filters?.search) params.search = filters.search;
      if (filters?.cursor) params.cursor = filters.cursor;
      if (filters?.limit) params.limit = filters.limit;
      const { data } = await apiClient.get<AuditLogPage>("/audit", { params });
      return data;
    },
  });
}
