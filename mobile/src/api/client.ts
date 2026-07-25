import { apiUrl, config } from '../lib/config';

/** Session returned by an OAuth exchange. */
export interface SessionOut {
  access_token: string;
  token_type: string;
  account: Account;
  connected_provider: string;
  is_new_account: boolean;
}

/** Shape of the backend's typed entities used across the app. */
export interface Account {
  id: number;
  display_name: string;
  email: string | null;
  created_at: string;
}

export interface Connection {
  id: number;
  provider: string;
  display_name: string | null;
  email: string | null;
  external_ref: string | null;
  scopes: string | null;
  created_at: string;
  token_expires_at: string | null;
  has_refresh: boolean;
  needs_reconnect: boolean;
}

export interface Ticket {
  id: number;
  channel: string;
  message_id: string;
  author_name: string;
  content: string;
  criticality_score: number;
  urgency_score: number;
  ai_draft_reply: string | null;
  status: 'PENDING' | 'APPROVED' | 'MODIFIED' | 'DISMISSED' | 'AUTO_REPLIED';
  created_at: string;
}

export type TicketStatus = Ticket['status'];

export interface KbDocument {
  id: number;
  title: string;
  content_type: string | null;
  source: string;
  source_ref: string | null;
  status: 'processing' | 'ready' | 'failed';
  chunk_count: number;
  chunk_total: number;
  error: string | null;
  created_at: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Token provider — set by the auth store so the client can attach the Bearer
 * token without a circular import.
 */
let tokenGetter: () => string | null = () => null;
export function setTokenGetter(fn: () => string | null) {
  tokenGetter = fn;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = tokenGetter();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(apiUrl(path), { ...options, headers });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new ApiError(res.status, String(detail));
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

// --- Typed endpoint helpers ------------------------------------------------

/** POST to an exchange endpoint with the X-API-Key header (no Bearer yet). */
async function postExchange(
  path: string,
  body: unknown,
  sessionToken?: string | null,
): Promise<SessionOut> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-API-Key': config.apiKey,
  };
  // If already signed in (adding a channel), send the session as a Bearer so the
  // backend links the new connection to the SAME account instead of a new one.
  if (sessionToken) headers.Authorization = `Bearer ${sessionToken}`;
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, String(data?.detail ?? `Exchange failed (${res.status})`));
  }
  return data as SessionOut;
}

export const AuthApi = {
  me: () => api.get<{ account: Account; connections: Connection[] }>('/me'),
  providers: () => api.get<{ providers: string[] }>('/auth/providers'),
  connections: () => api.get<Connection[]>('/connections'),
  deleteConnection: (id: number) => api.del<void>(`/connections/${id}`),
  discordGuilds: () =>
    api.get<{ guilds: { id: string; name: string }[]; linked_guild: string | null }>(
      '/connections/discord/guilds',
    ),
  linkGuild: (guild_id: string) =>
    api.post<Connection>('/connections/discord/link-guild', { guild_id }),

  // Option B: app-owned OAuth exchange. Pass sessionToken to link to an
  // existing account (adding a second channel).
  exchangeDiscordPkce: (
    code: string,
    code_verifier: string,
    redirect_uri: string,
    sessionToken?: string | null,
  ) =>
    postExchange('/auth/discord/exchange', { code, code_verifier, redirect_uri }, sessionToken),
  exchangeGoogleServerCode: (server_auth_code: string, sessionToken?: string | null) =>
    postExchange('/auth/google/exchange', { server_auth_code }, sessionToken),
};

export const TicketsApi = {
  list: (status?: TicketStatus) =>
    api.get<Ticket[]>(`/support/tickets${status ? `?status=${status}` : ''}`),
  get: (id: number) => api.get<Ticket>(`/support/tickets/${id}`),
  update: (id: number, body: { status: TicketStatus; ai_draft_reply?: string }) =>
    api.patch<Ticket>(`/support/tickets/${id}`, body),
};

export const NotificationsApi = {
  register: (token: string, platform?: string) =>
    api.post<void>('/notifications/register', { token, platform }),
  unregister: (token: string) =>
    api.post<void>('/notifications/unregister', { token }),
};

/** A file picked on-device, ready to upload as multipart/form-data. */
export interface UploadFile {
  uri: string;
  name: string;
  mimeType?: string | null;
}

export const KbApi = {
  list: () => api.get<KbDocument[]>('/kb/documents'),
  remove: (id: number) => api.del<void>(`/kb/documents/${id}`),
  addWebsite: (url: string) => api.post<KbDocument>('/kb/sources', { url }),
  resync: (id: number) => api.post<KbDocument>(`/kb/sources/${id}/resync`),
  upload: (file: UploadFile): Promise<KbDocument> => uploadKbFile('/kb/documents', file),
  replace: (id: number, file: UploadFile): Promise<KbDocument> =>
    uploadKbFile(`/kb/documents/${id}/replace`, file),
};

/** Shared multipart POST for KB file upload + replace. */
async function uploadKbFile(path: string, file: UploadFile): Promise<KbDocument> {
  const form = new FormData();
  // React Native FormData accepts a { uri, name, type } file part.
  form.append('file', {
    uri: file.uri,
    name: file.name,
    type: file.mimeType || 'application/octet-stream',
  } as unknown as Blob);

  const token = tokenGetter();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  // Do NOT set Content-Type — fetch sets the multipart boundary itself.

  const res = await fetch(apiUrl(path), { method: 'POST', headers, body: form });
  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message)) || `Upload failed (${res.status})`;
    throw new ApiError(res.status, String(detail));
  }
  return data as KbDocument;
}
