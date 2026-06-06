import type {
  ApiErrorEnvelope,
  AuthToken,
  Job,
  JobAssignment,
  JobCreate,
  JobEvent,
  JobPatch,
  JobUpdate,
  PaginatedResponse,
  PhotoDownload,
  TechnicianLatestLocation,
  TechnicianLocation,
  TechnicianPresence,
  User,
  UserCreate,
} from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || 'http://127.0.0.1:8000';

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

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`);
  }

  let body: BodyInit | undefined;
  if (options.body instanceof FormData || typeof options.body === 'string' || options.body instanceof Blob) {
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
    throw new ApiError(response.status, payload as ApiErrorEnvelope | null, `Request failed with ${response.status}`);
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
  users(token: string, params: URLSearchParams) {
    return request<PaginatedResponse<User>>(`/users?${params.toString()}`, { token });
  },
  jobs(token: string, params: URLSearchParams) {
    return request<PaginatedResponse<Job>>(`/jobs?${params.toString()}`, { token });
  },
  job(token: string, jobId: number) {
    return request<Job>(`/jobs/${jobId}`, { token });
  },
  assignments(token: string, jobId: number) {
    return request<JobAssignment[]>(`/jobs/${jobId}/assignments`, { token });
  },
  assignTechnician(token: string, jobId: number, technicianId: number) {
    return request<JobAssignment>(`/jobs/${jobId}/assignments`, {
      method: 'POST',
      token,
      body: { technician_id: technicianId },
    });
  },
  removeAssignment(token: string, jobId: number, assignmentId: number) {
    return request<void>(`/jobs/${jobId}/assignments/${assignmentId}`, {
      method: 'DELETE',
      token,
    });
  },
  events(token: string, jobId: number) {
    return request<JobEvent[]>(`/jobs/${jobId}/events`, { token });
  },
  updates(token: string, jobId: number) {
    return request<JobUpdate[]>(`/jobs/${jobId}/updates`, { token });
  },
  latestLocations(token: string, params: URLSearchParams) {
    return request<PaginatedResponse<TechnicianLatestLocation>>(`/locations/technicians/latest?${params.toString()}`, { token });
  },
  locationHistory(token: string, technicianId: number, params: URLSearchParams) {
    return request<PaginatedResponse<TechnicianLocation>>(`/locations/technicians/${technicianId}/history?${params.toString()}`, {
      token,
    });
  },
  presence(token: string, params: URLSearchParams) {
    return request<PaginatedResponse<TechnicianPresence>>(`/presence/technicians?${params.toString()}`, { token });
  },
  technicianPresence(token: string, technicianId: number) {
    return request<TechnicianPresence>(`/presence/technicians/${technicianId}`, { token });
  },
  createJob(token: string, payload: JobCreate) {
    return request<Job>('/jobs', { method: 'POST', token, body: payload });
  },
  updateJob(token: string, jobId: number, payload: JobPatch) {
    return request<Job>(`/jobs/${jobId}`, { method: 'PATCH', token, body: payload });
  },
  createUser(token: string, payload: UserCreate) {
    return request<User>('/users', { method: 'POST', token, body: payload });
  },
  photoDownload(token: string, jobId: number, updateId: number, photoId: number) {
    return request<PhotoDownload>(`/jobs/${jobId}/updates/${updateId}/photos/${photoId}/download`, { token });
  },
};