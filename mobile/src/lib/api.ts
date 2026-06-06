import type {
  ApiErrorEnvelope,
  AuthToken,
  CreateJobUpdatePayload,
  Job,
  JobAttachment,
  JobAttachmentDownload,
  JobEvent,
  JobUpdate,
  JobUpdatePhoto,
  PaginatedResponse,
  SendLocationPayload,
  TechnicianLocation,
  TechnicianPresence,
  User,
} from '../types';

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ||
  'http://127.0.0.1:8000';

export class ApiError extends Error {
  status: number;
  requestId?: string;
  code?: string;

  constructor(status: number, payload: ApiErrorEnvelope | null, fallbackMessage: string) {
    super(payload?.error?.message || payload?.detail || fallbackMessage);
    this.status = status;
    this.requestId = payload?.request_id;
    this.code = payload?.error?.code;
  }
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: BodyInit | object | null;
  token?: string | null;
};

async function request<T>(path: string, options: RequestOptions = {}) {
  const headers = new Headers(options.headers);
  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`);
  }

  let body: BodyInit | undefined;
  if (
    options.body instanceof FormData ||
    typeof options.body === 'string' ||
    options.body instanceof Blob
  ) {
    body = options.body;
  } else if (options.body != null) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? ((await response.json()) as T | ApiErrorEnvelope)
    : null;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      payload as ApiErrorEnvelope | null,
      `Request failed with ${response.status}`,
    );
  }

  return payload as T;
}

export const api = {
  baseUrl: API_BASE_URL,
  login(email: string, password: string) {
    const formData = new URLSearchParams();
    formData.set('username', email);
    formData.set('password', password);
    return request<AuthToken>('/auth/login', {
      method: 'POST',
      body: formData.toString(),
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
  },
  logout(token: string) {
    return request<void>('/auth/logout', { method: 'POST', token });
  },
  me(token: string) {
    return request<User>('/users/me', { token });
  },
  jobs(token: string) {
    return request<PaginatedResponse<Job>>('/jobs?offset=0&limit=50&status=not_started&status=in_progress', { token });
  },
  job(token: string, jobId: number) {
    return request<Job>(`/jobs/${jobId}`, { token });
  },
  events(token: string, jobId: number) {
    return request<JobEvent[]>(`/jobs/${jobId}/events`, { token });
  },
  updates(token: string, jobId: number) {
    return request<JobUpdate[]>(`/jobs/${jobId}/updates`, { token });
  },
  createUpdate(token: string, jobId: number, payload: CreateJobUpdatePayload) {
    return request<JobUpdate>(`/jobs/${jobId}/updates`, {
      method: 'POST',
      token,
      body: payload,
    });
  },
  uploadPhoto(token: string, jobId: number, updateId: number, file: FormData) {
    return request<JobUpdatePhoto>(`/jobs/${jobId}/updates/${updateId}/photos`, {
      method: 'POST',
      token,
      body: file,
    });
  },
  checkIn(token: string, jobId: number) {
    return request<JobEvent>(`/jobs/${jobId}/check-in`, {
      method: 'POST',
      token,
    });
  },
  checkOut(token: string, jobId: number) {
    return request<JobEvent>(`/jobs/${jobId}/check-out`, {
      method: 'POST',
      token,
    });
  },
  heartbeat(token: string) {
    return request<TechnicianPresence>('/presence/me/heartbeat', {
      method: 'POST',
      token,
    });
  },
  logoutPresence(token: string) {
    return request<void>('/presence/me/logout', { method: 'POST', token });
  },
  sendLocation(token: string, payload: SendLocationPayload) {
    return request<TechnicianLocation>('/locations/me', {
      method: 'POST',
      token,
      body: payload,
    });
  },
  attachments(token: string, jobId: number) {
    return request<JobAttachment[]>(`/jobs/${jobId}/attachments`, { token });
  },
  attachmentDownload(token: string, jobId: number, attachmentId: number) {
    return request<JobAttachmentDownload>(`/jobs/${jobId}/attachments/${attachmentId}/download`, { token });
  },
};
