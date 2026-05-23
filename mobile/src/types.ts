export type UserRole = 'technician' | 'manager' | 'admin';
export type JobStatus = 'not_started' | 'in_progress' | 'completed';
export type JobPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface ApiErrorEnvelope {
  detail: string;
  error?: {
    code: string;
    message: string;
    details: Array<Record<string, unknown>>;
  };
  request_id?: string;
  path?: string;
  timestamp?: string;
}

export interface PaginatedResponse<T> {
  total: number;
  offset: number;
  limit: number;
  items: T[];
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
  role: UserRole;
  technician_code: string | null;
  full_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: number;
  title: string;
  description: string | null;
  technician_instructions: string | null;
  internal_notes: string | null;
  address_line1: string;
  address_line2: string | null;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  scheduled_start: string | null;
  scheduled_end: string | null;
  status: JobStatus;
  priority: JobPriority;
  created_by_id: number;
  created_at: string;
  updated_at: string;
}

export interface JobEvent {
  id: number;
  job_id: number;
  actor_id: number;
  event_type: string;
  occurred_at: string;
}

export interface JobUpdatePhoto {
  id: number;
  job_update_id: number;
  file_key: string;
  file_name: string | null;
  content_type: string | null;
  created_at: string;
}

export interface JobUpdate {
  id: number;
  job_id: number;
  author_id: number;
  message: string;
  created_at: string;
  photos: JobUpdatePhoto[];
}

export interface TechnicianLocation {
  id: number;
  technician_id: number;
  latitude: number;
  longitude: number;
  accuracy_meters: number | null;
  recorded_at: string;
  created_at: string;
}

export interface TechnicianPresence {
  technician_id: number;
  technician_name: string;
  is_logged_in: boolean;
  is_online: boolean;
  session_started_at: string;
  last_seen_at: string;
  latest_location: TechnicianLocation | null;
}

export interface CreateJobUpdatePayload {
  message: string;
}

export interface SendLocationPayload {
  latitude: number;
  longitude: number;
  accuracy_meters?: number | null;
  recorded_at?: string;
}
