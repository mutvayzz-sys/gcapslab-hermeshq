import { apiClient } from "./client";

export interface OidcProviderRead {
  id: string;
  slug: string;
  name: string;
  client_id: string;
  discovery_url: string;
  scopes: string;
  enabled: boolean;
  auto_provision: boolean;
  allowed_domains: string | null;
  icon_slug: string | null;
}

export interface OidcProviderCreate {
  slug: string;
  name: string;
  client_id: string;
  client_secret: string;
  discovery_url: string;
  scopes?: string;
  enabled?: boolean;
  auto_provision?: boolean;
  allowed_domains?: string | null;
  icon_slug?: string | null;
}

export interface OidcProviderUpdate {
  name?: string;
  client_id?: string;
  client_secret?: string;
  discovery_url?: string;
  scopes?: string;
  enabled?: boolean;
  auto_provision?: boolean;
  allowed_domains?: string | null;
  icon_slug?: string | null;
}

export async function listOidcProviders(): Promise<OidcProviderRead[]> {
  const { data } = await apiClient.get<OidcProviderRead[]>("/oidc-providers");
  return data;
}

export async function createOidcProvider(payload: OidcProviderCreate): Promise<OidcProviderRead> {
  const { data } = await apiClient.post<OidcProviderRead>("/oidc-providers", payload);
  return data;
}

export async function updateOidcProvider(
  id: string,
  payload: OidcProviderUpdate,
): Promise<OidcProviderRead> {
  const { data } = await apiClient.patch<OidcProviderRead>(`/oidc-providers/${id}`, payload);
  return data;
}

export async function deleteOidcProvider(id: string): Promise<void> {
  await apiClient.delete(`/oidc-providers/${id}`);
}
