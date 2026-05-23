import {
  type FormEvent,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { ApiError, api } from './lib/api';
import type {
  Job,
  JobAssignment,
  JobCreate,
  JobEvent,
  JobPriority,
  JobStatus,
  JobUpdate,
  TechnicianLatestLocation,
  TechnicianLocation,
  TechnicianPresence,
  User,
  UserCreate,
  UserRole,
} from './types';

type TabKey = 'dashboard' | 'users' | 'jobs' | 'locations' | 'presence';
type AvailabilityFilter = 'all' | 'active' | 'inactive';

const TOKEN_KEY = 'field-service-web-token';
const PAGE_SIZE = 20;
const LIVE_REFRESH_MS = 30000;

function formatDubaiTime(value: string | null | undefined) {
  if (!value) {
    return 'Not available';
  }

  return new Intl.DateTimeFormat('en-AE', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Dubai',
  }).format(new Date(value));
}

function buildQuery(
  params: Record<string, string | number | boolean | undefined | null>,
) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    query.set(key, String(value));
  });
  return query;
}

function formatApiError(error: unknown) {
  if (error instanceof ApiError) {
    return error.requestId
      ? `${error.message} (request ${error.requestId})`
      : error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Request failed';
}

function formatLoginError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Incorrect email or password.';
    }
    if (error.status === 403) {
      return 'This account is inactive. Contact an administrator.';
    }
    if (error.status === 429) {
      return 'Too many sign-in attempts. Please wait a moment and try again.';
    }
    return formatApiError(error);
  }

  return 'Unable to sign in right now. Please check your details and try again.';
}

function timeAgo(value: string | null | undefined): string {
  if (!value) return 'never';
  const minutes = Math.floor((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function toneFor(value: string) {
  if (
    value === 'completed' ||
    value === 'online' ||
    value === 'active' ||
    value === 'fresh'
  ) {
    return 'good';
  }
  if (
    value === 'urgent' ||
    value === 'offline' ||
    value === 'stale' ||
    value === 'inactive'
  ) {
    return 'bad';
  }
  if (value === 'in_progress' || value === 'high') {
    return 'warn';
  }
  return 'neutral';
}

async function guarded<T>(
  task: () => Promise<T>,
  onUnauthorized: (message?: string) => void,
) {
  try {
    return await task();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      onUnauthorized('Your session expired. Please log in again.');
    }
    throw error;
  }
}

export default function App() {
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem(TOKEN_KEY),
  );
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');

  const [users, setUsers] = useState<User[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [usersQuery, setUsersQuery] = useState('');
  const [usersRole, setUsersRole] = useState<UserRole | ''>('');
  const [usersAvailability, setUsersAvailability] =
    useState<AvailabilityFilter>('active');
  const [usersOffset, setUsersOffset] = useState(0);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [jobsQuery, setJobsQuery] = useState('');
  const [jobsStatus, setJobsStatus] = useState<JobStatus | ''>('');
  const [jobsPriority, setJobsPriority] = useState<JobPriority | ''>('');
  const [jobsOffset, setJobsOffset] = useState(0);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [jobAssignments, setJobAssignments] = useState<JobAssignment[]>([]);
  const [jobEvents, setJobEvents] = useState<JobEvent[]>([]);
  const [jobUpdates, setJobUpdates] = useState<JobUpdate[]>([]);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [jobDetailError, setJobDetailError] = useState<string | null>(null);
  const [assignmentTechnicianId, setAssignmentTechnicianId] = useState<
    number | ''
  >('');
  const [showCreateJob, setShowCreateJob] = useState(false);
  const [createJobError, setCreateJobError] = useState<string | null>(null);

  const [showCreateUser, setShowCreateUser] = useState(false);
  const [createUserError, setCreateUserError] = useState<string | null>(null);
  const [createUserRole, setCreateUserRole] = useState<UserRole>('technician');

  const [technicianDirectory, setTechnicianDirectory] = useState<User[]>([]);

  const [locations, setLocations] = useState<TechnicianLatestLocation[]>([]);
  const [locationsTotal, setLocationsTotal] = useState(0);
  const [locationsLoading, setLocationsLoading] = useState(false);
  const [locationsError, setLocationsError] = useState<string | null>(null);
  const [locationsQuery, setLocationsQuery] = useState('');
  const [includeStaleLocations, setIncludeStaleLocations] = useState(true);
  const [locationsOffset, setLocationsOffset] = useState(0);
  const [selectedLocationTechnicianId, setSelectedLocationTechnicianId] =
    useState<number | null>(null);
  const [locationHistory, setLocationHistory] = useState<TechnicianLocation[]>(
    [],
  );
  const [locationHistoryLoading, setLocationHistoryLoading] = useState(false);
  const [locationHistoryError, setLocationHistoryError] = useState<
    string | null
  >(null);

  const [presence, setPresence] = useState<TechnicianPresence[]>([]);
  const [presenceTotal, setPresenceTotal] = useState(0);
  const [presenceLoading, setPresenceLoading] = useState(false);
  const [presenceError, setPresenceError] = useState<string | null>(null);
  const [presenceQuery, setPresenceQuery] = useState('');
  const [includeOfflinePresence, setIncludeOfflinePresence] = useState(true);
  const [presenceOffset, setPresenceOffset] = useState(0);
  const [selectedPresenceTechnicianId, setSelectedPresenceTechnicianId] =
    useState<number | null>(null);
  const [selectedPresence, setSelectedPresence] =
    useState<TechnicianPresence | null>(null);
  const [presenceDetailLoading, setPresenceDetailLoading] = useState(false);
  const [presenceDetailError, setPresenceDetailError] = useState<string | null>(
    null,
  );

  const deferredUsersQuery = useDeferredValue(usersQuery);
  const deferredJobsQuery = useDeferredValue(jobsQuery);
  const deferredLocationsQuery = useDeferredValue(locationsQuery);
  const deferredPresenceQuery = useDeferredValue(presenceQuery);

  const activeTechnicians = useMemo(
    () =>
      technicianDirectory.filter(
        (user) => user.role === 'technician' && user.is_active,
      ),
    [technicianDirectory],
  );
  const onlineTechnicians = useMemo(
    () => presence.filter((entry) => entry.is_online).length,
    [presence],
  );
  const staleLocations = useMemo(
    () => locations.filter((entry) => entry.is_stale).length,
    [locations],
  );
  const urgentJobs = useMemo(
    () => jobs.filter((job) => job.priority === 'urgent').length,
    [jobs],
  );

  const pageMeta: Record<TabKey, { eyebrow: string; title: string; copy: string }> = {
    dashboard: {
      eyebrow: 'Command Center',
      title: 'Dispatch dashboard',
      copy: 'A live summary of jobs, field technicians, location freshness, and session presence.',
    },
    users: {
      eyebrow: 'Access Control',
      title: 'Users and technician roster',
      copy: 'Manager-facing identity, technician availability, and account visibility controls.',
    },
    jobs: {
      eyebrow: 'Field Work',
      title: 'Jobs and assignments',
      copy: 'Track active work orders, assignment coverage, and the latest operational activity.',
    },
    locations: {
      eyebrow: 'Tracking',
      title: 'Live technician locations',
      copy: 'Monitor fresh versus stale GPS updates with Dubai-time visibility across the fleet.',
    },
    presence: {
      eyebrow: 'Sessions',
      title: 'Technician mobile presence',
      copy: 'See who is logged in, online, and recently active in the technician mobile app.',
    },
  };

  function resetSession(message = 'Your session has ended. Please log in again.') {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setCurrentUser(null);
    setSelectedJobId(null);
    setSelectedJob(null);
    setSelectedLocationTechnicianId(null);
    setSelectedPresenceTechnicianId(null);
    setSelectedPresence(null);
    setAuthError(message);
  }

  useEffect(() => {
    if (!flash) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => setFlash(null), 4000);
    return () => window.clearTimeout(timeoutId);
  }, [flash]);

  useEffect(() => {
    if (!token) {
      setBooting(false);
      return;
    }

    let cancelled = false;
    setBooting(true);
    guarded(() => api.me(token), resetSession)
      .then((user) => {
        if (!cancelled) {
          setCurrentUser(user);
          setAuthError(null);
        }
      })
      .catch((error) => {
        if (!cancelled && !(error instanceof ApiError && error.status === 401)) {
          setAuthError(formatApiError(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBooting(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token || !currentUser || currentUser.role === 'technician') {
      return;
    }

    guarded(
      () =>
        api.users(
          token,
          buildQuery({
            role: 'technician',
            is_active: true,
            offset: 0,
            limit: 200,
          }),
        ),
      resetSession,
    )
      .then((response) => setTechnicianDirectory(response.items))
      .catch(() => undefined);
  }, [token, currentUser]);

  useEffect(() => {
    if (!token || !currentUser || currentUser.role === 'technician') {
      return;
    }

    setUsersLoading(true);
    setUsersError(null);
    guarded(
      () =>
        api.users(
          token,
          buildQuery({
            offset: usersOffset,
            limit: PAGE_SIZE,
            q: deferredUsersQuery,
            role: usersRole || undefined,
            is_active:
              usersAvailability === 'all'
                ? undefined
                : usersAvailability === 'active',
          }),
        ),
      resetSession,
    )
      .then((response) => {
        setUsers(response.items);
        setUsersTotal(response.total);
      })
      .catch((error) => setUsersError(formatApiError(error)))
      .finally(() => setUsersLoading(false));
  }, [
    token,
    currentUser,
    usersOffset,
    usersRole,
    usersAvailability,
    deferredUsersQuery,
  ]);

  useEffect(() => {
    if (!token || !currentUser || currentUser.role === 'technician') {
      return;
    }

    setJobsLoading(true);
    setJobsError(null);
    guarded(
      () =>
        api.jobs(
          token,
          buildQuery({
            offset: jobsOffset,
            limit: PAGE_SIZE,
            q: deferredJobsQuery,
            status: jobsStatus || undefined,
            priority: jobsPriority || undefined,
          }),
        ),
      resetSession,
    )
      .then((response) => {
        setJobs(response.items);
        setJobsTotal(response.total);
        if (response.items.length === 0) {
          setSelectedJobId(null);
          setSelectedJob(null);
        } else if (selectedJobId == null) {
          setSelectedJobId(response.items[0].id);
        }
      })
      .catch((error) => setJobsError(formatApiError(error)))
      .finally(() => setJobsLoading(false));
  }, [
    token,
    currentUser,
    jobsOffset,
    jobsStatus,
    jobsPriority,
    deferredJobsQuery,
    selectedJobId,
  ]);

  useEffect(() => {
    if (!token || !currentUser || currentUser.role === 'technician') {
      return;
    }

    setLocationsLoading(true);
    setLocationsError(null);
    guarded(
      () =>
        api.latestLocations(
          token,
          buildQuery({
            offset: locationsOffset,
            limit: PAGE_SIZE,
            q: deferredLocationsQuery,
            include_stale: includeStaleLocations,
          }),
        ),
      resetSession,
    )
      .then((response) => {
        setLocations(response.items);
        setLocationsTotal(response.total);
        if (response.items.length === 0) {
          setSelectedLocationTechnicianId(null);
        }
      })
      .catch((error) => setLocationsError(formatApiError(error)))
      .finally(() => setLocationsLoading(false));
  }, [
    token,
    currentUser,
    locationsOffset,
    includeStaleLocations,
    deferredLocationsQuery,
  ]);

  useEffect(() => {
    if (!token || !currentUser || currentUser.role === 'technician') {
      return;
    }

    setPresenceLoading(true);
    setPresenceError(null);
    guarded(
      () =>
        api.presence(
          token,
          buildQuery({
            offset: presenceOffset,
            limit: PAGE_SIZE,
            q: deferredPresenceQuery,
            include_offline: includeOfflinePresence,
          }),
        ),
      resetSession,
    )
      .then((response) => {
        setPresence(response.items);
        setPresenceTotal(response.total);
        if (response.items.length === 0) {
          setSelectedPresenceTechnicianId(null);
          setSelectedPresence(null);
        }
      })
      .catch((error) => setPresenceError(formatApiError(error)))
      .finally(() => setPresenceLoading(false));
  }, [
    token,
    currentUser,
    presenceOffset,
    includeOfflinePresence,
    deferredPresenceQuery,
  ]);

  useEffect(() => {
    if (!token || selectedJobId == null) {
      return;
    }

    setJobDetailLoading(true);
    setJobDetailError(null);
    guarded(
      async () => {
        const [job, assignments, events, updates] = await Promise.all([
          api.job(token, selectedJobId),
          api.assignments(token, selectedJobId),
          api.events(token, selectedJobId),
          api.updates(token, selectedJobId),
        ]);
        setSelectedJob(job);
        setJobAssignments(assignments);
        setJobEvents(events);
        setJobUpdates(updates);
      },
      resetSession,
    )
      .catch((error) => setJobDetailError(formatApiError(error)))
      .finally(() => setJobDetailLoading(false));
  }, [token, selectedJobId]);

  useEffect(() => {
    if (!token || selectedLocationTechnicianId == null) {
      return;
    }

    setLocationHistoryLoading(true);
    setLocationHistoryError(null);
    guarded(
      () =>
        api.locationHistory(
          token,
          selectedLocationTechnicianId,
          buildQuery({ offset: 0, limit: 15 }),
        ),
      resetSession,
    )
      .then((response) => setLocationHistory(response.items))
      .catch((error) => setLocationHistoryError(formatApiError(error)))
      .finally(() => setLocationHistoryLoading(false));
  }, [token, selectedLocationTechnicianId]);

  useEffect(() => {
    if (!token || selectedPresenceTechnicianId == null) {
      return;
    }

    setPresenceDetailLoading(true);
    setPresenceDetailError(null);
    guarded(
      () => api.technicianPresence(token, selectedPresenceTechnicianId),
      resetSession,
    )
      .then(setSelectedPresence)
      .catch((error) => setPresenceDetailError(formatApiError(error)))
      .finally(() => setPresenceDetailLoading(false));
  }, [token, selectedPresenceTechnicianId]);

  useEffect(() => {
    if (!token || activeTab !== 'locations') {
      return;
    }

    const intervalId = window.setInterval(() => {
      guarded(
        () =>
          api.latestLocations(
            token,
            buildQuery({
              offset: locationsOffset,
              limit: PAGE_SIZE,
              q: deferredLocationsQuery,
              include_stale: includeStaleLocations,
            }),
          ),
        resetSession,
      )
        .then((response) => {
          setLocations(response.items);
          setLocationsTotal(response.total);
        })
        .catch(() => undefined);
    }, LIVE_REFRESH_MS);

    return () => window.clearInterval(intervalId);
  }, [
    token,
    activeTab,
    locationsOffset,
    includeStaleLocations,
    deferredLocationsQuery,
  ]);

  useEffect(() => {
    if (!token || activeTab !== 'presence') {
      return;
    }

    const intervalId = window.setInterval(() => {
      guarded(
        () =>
          api.presence(
            token,
            buildQuery({
              offset: presenceOffset,
              limit: PAGE_SIZE,
              q: deferredPresenceQuery,
              include_offline: includeOfflinePresence,
            }),
          ),
        resetSession,
      )
        .then((response) => {
          setPresence(response.items);
          setPresenceTotal(response.total);
          if (selectedPresenceTechnicianId != null) {
            return guarded(
              () => api.technicianPresence(token, selectedPresenceTechnicianId),
              resetSession,
            ).then(setSelectedPresence);
          }
          return undefined;
        })
        .catch(() => undefined);
    }, LIVE_REFRESH_MS);

    return () => window.clearInterval(intervalId);
  }, [
    token,
    activeTab,
    presenceOffset,
    includeOfflinePresence,
    deferredPresenceQuery,
    selectedPresenceTechnicianId,
  ]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get('email') || '');
    const password = String(form.get('password') || '');
    setBusy('login');
    setAuthError(null);

    try {
      const auth = await api.login(email, password);
      sessionStorage.setItem(TOKEN_KEY, auth.access_token);
      setToken(auth.access_token);
      setFlash('Signed in. Restoring session state from the backend.');
    } catch (error) {
      setAuthError(formatLoginError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleLogout() {
    if (!token) {
      resetSession();
      return;
    }

    setBusy('logout');
    try {
      await api.logout(token);
    } catch {
      // The local session still has to be cleared.
    } finally {
      resetSession('You have been logged out.');
      setBusy(null);
    }
  }

  async function handleAssignTechnician() {
    if (!token || selectedJobId == null || assignmentTechnicianId === '') {
      return;
    }

    setBusy('assign');
    try {
      await guarded(
        () => api.assignTechnician(token, selectedJobId, Number(assignmentTechnicianId)),
        resetSession,
      );
      const [assignments, events, updates] = await Promise.all([
        guarded(() => api.assignments(token, selectedJobId), resetSession),
        guarded(() => api.events(token, selectedJobId), resetSession),
        guarded(() => api.updates(token, selectedJobId), resetSession),
      ]);
      setJobAssignments(assignments);
      setJobEvents(events);
      setJobUpdates(updates);
      setAssignmentTechnicianId('');
      setFlash('Technician assignment saved.');
    } catch (error) {
      setFlash(formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleRemoveAssignment(assignmentId: number) {
    if (!token || selectedJobId == null) {
      return;
    }

    setBusy(`remove-${assignmentId}`);
    try {
      await guarded(
        () => api.removeAssignment(token, selectedJobId, assignmentId),
        resetSession,
      );
      setJobAssignments((current) =>
        current.filter((assignment) => assignment.id !== assignmentId),
      );
      setFlash('Assignment removed.');
    } catch (error) {
      setFlash(formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleCreateJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;

    const form = new FormData(event.currentTarget);
    const toApiDateTime = (v: FormDataEntryValue | null): string | null => {
      if (!v || typeof v !== 'string' || !v.trim()) return null;
      return `${v}:00+04:00`;
    };

    const payload: JobCreate = {
      title: String(form.get('title') || ''),
      description: String(form.get('description') || '').trim() || null,
      address_line1: String(form.get('address_line1') || ''),
      address_line2: String(form.get('address_line2') || '').trim() || null,
      city: String(form.get('city') || ''),
      state: String(form.get('state') || ''),
      postal_code: String(form.get('postal_code') || ''),
      country: String(form.get('country') || 'UAE'),
      priority: (form.get('priority') as JobPriority) || 'medium',
      scheduled_start: toApiDateTime(form.get('scheduled_start')),
      scheduled_end: toApiDateTime(form.get('scheduled_end')),
    };

    setBusy('create-job');
    setCreateJobError(null);
    try {
      const created = await guarded(() => api.createJob(token, payload), resetSession);
      setJobs((prev) => [created, ...prev]);
      setJobsTotal((prev) => prev + 1);
      setSelectedJobId(created.id);
      setShowCreateJob(false);
      setFlash('Job created.');
      (event.target as HTMLFormElement).reset();
    } catch (error) {
      setCreateJobError(formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleCreateUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const role = data.get('role') as UserRole;
    const payload: UserCreate = {
      full_name: data.get('full_name') as string,
      email: data.get('email') as string,
      password: data.get('password') as string,
      role,
      technician_code: role === 'technician' ? (data.get('technician_code') as string) || undefined : undefined,
      is_active: true,
    };
    setBusy('create-user');
    setCreateUserError(null);
    try {
      const created = await guarded(() => api.createUser(token, payload), resetSession);
      setUsers((prev) => [created, ...prev]);
      setUsersTotal((prev) => prev + 1);
      if (created.role === 'technician' && created.is_active) {
        setTechnicianDirectory((prev) => [...prev, created]);
      }
      setFlash(`User ${created.full_name} created.`);
      form.reset();
      setCreateUserRole('technician');
      setShowCreateUser(false);
    } catch (error) {
      setCreateUserError(formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleUpdateJobStatus(newStatus: JobStatus) {
    if (!token || selectedJobId == null) return;
    setBusy(`status-${newStatus}`);
    try {
      const updated = await guarded(
        () => api.updateJob(token, selectedJobId, { status: newStatus }),
        resetSession,
      );
      setSelectedJob(updated);
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      setFlash(`Job status set to ${newStatus.replace(/_/g, ' ')}.`);
    } catch (error) {
      setFlash(formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  if (booting) {
    return (
      <div className="shell loading-shell">
        <div className="panel status-card">
          <p className="eyebrow">Field Service Control</p>
          <h1>Restoring session</h1>
          <p className="lede">Validating the saved bearer token with GET /users/me.</p>
        </div>
      </div>
    );
  }

  if (!token || !currentUser) {
    return (
      <div className="shell auth-shell">
        <section className="hero-card panel">
          <h1 className="brand-hero-title">Al Terhab Logistics</h1>
          <p className="lede">
            Sign in to access dispatch control, technician monitoring, and live field operations.
          </p>
          <div className="hero-points">
            <span className="request-chip">Users</span>
            <span className="request-chip">Jobs</span>
            <span className="request-chip">Assignments</span>
            <span className="request-chip">Location monitoring</span>
            <span className="request-chip">Presence monitoring</span>
          </div>
        </section>

        <form className="panel auth-panel" onSubmit={handleLogin}>
          <div>
            <p className="eyebrow">Manager Login</p>
            <h2>Access the dispatch console</h2>
          </div>
          <label>
            Email
            <input
              name="email"
              type="email"
              placeholder="manager@example.com"
              required
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              placeholder="Secret123!"
              required
            />
          </label>
          <button
            className="primary-button"
            type="submit"
            disabled={busy === 'login'}
          >
            {busy === 'login' ? 'Signing in...' : 'Sign in'}
          </button>
          {authError ? <p className="error-text">{authError}</p> : null}
          <p className="hint-text">Secure access for authorized operations staff.</p>
        </form>
      </div>
    );
  }

  if (currentUser.role === 'technician') {
    return (
      <div className="shell single-shell">
        <section className="panel status-card">
          <p className="eyebrow">Role mismatch</p>
          <h1>{currentUser.full_name}</h1>
          <p className="lede">
            The web console is scoped to managers and admins. Technician workflows
            belong in the mobile app.
          </p>
          <div className="split-actions">
            <span className="request-chip">{currentUser.role}</span>
            <button
              className="ghost-button"
              type="button"
              onClick={handleLogout}
              disabled={busy === 'logout'}
            >
              {busy === 'logout' ? 'Logging out...' : 'Logout'}
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="shell workspace-shell">
      <aside className="sidebar panel">
        <div className="brand-mark">
          <span className="brand-glyph">D</span>
          <div>
            <strong>Dasher FS</strong>
            <p>Field operations</p>
          </div>
        </div>

        <div className="sidebar-group">
          <p className="sidebar-label">Workspace</p>
          {(
            [
              ['dashboard', 'Dashboard'],
              ['jobs', 'Jobs'],
              ['locations', 'Locations'],
              ['presence', 'Presence'],
              ['users', 'Users'],
            ] as Array<[TabKey, string]>
          ).map(([tab, label]) => (
            <button
              key={tab}
              type="button"
              className={tab === activeTab ? 'nav-link active' : 'nav-link'}
              onClick={() => setActiveTab(tab)}
            >
              <span className="nav-dot" />
              <span>{label}</span>
            </button>
          ))}
        </div>

        <div className="sidebar-foot">
          <p className="sidebar-label">Signed In</p>
          <div className="operator-card">
            <div className="operator-avatar">
              {currentUser.full_name
                .split(' ')
                .map((part) => part[0])
                .join('')
                .slice(0, 2)}
            </div>
            <div>
              <strong>{currentUser.full_name}</strong>
              <p>
                {currentUser.role} · Asia/Dubai
              </p>
            </div>
          </div>
          <small className="sidebar-note">
            Live shell preview. We will restyle each operational screen after you approve this foundation.
          </small>
        </div>
      </aside>

      <main className="main-stage">
        <header className="topbar panel">
          <div>
            <p className="eyebrow">{pageMeta[activeTab].eyebrow}</p>
            <h1>{pageMeta[activeTab].title}</h1>
            <p className="lede">{pageMeta[activeTab].copy}</p>
          </div>
          <div className="topbar-actions">
            <span className="request-chip">{api.baseUrl}</span>
            <span className="request-chip">Manager view</span>
            <button
              className="ghost-button"
              type="button"
              onClick={handleLogout}
              disabled={busy === 'logout'}
            >
              {busy === 'logout' ? 'Logging out...' : 'Logout'}
            </button>
          </div>
        </header>

        {flash ? <p className="flash-text flash-banner">{flash}</p> : null}

        {activeTab === 'dashboard' ? (
          <section className="dashboard-grid">
            <article className="panel hero-panel">
              <p className="eyebrow">Hello {currentUser.full_name.split(' ')[0]},</p>
              <h2>Run dispatch, technician visibility, and live field oversight from one console.</h2>
              <p className="lede">
                This shell sets the visual direction first: dark command center, teal signal accents, rounded cards, and compact operations density.
              </p>
              <div className="hero-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => setActiveTab('jobs')}
                >
                  Open jobs
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => setActiveTab('locations')}
                >
                  View tracking
                </button>
              </div>
            </article>

            <article className="panel spotlight-panel">
              <div className="spotlight-head">
                <p className="sidebar-label">Dispatch status</p>
                <span className={`request-chip${onlineTechnicians > 0 ? ' chip-live' : ''}`}>
                  {onlineTechnicians > 0 ? 'Live' : 'No signal'}
                </span>
              </div>
              <h3>
                {onlineTechnicians > 0
                  ? `${onlineTechnicians} technician${onlineTechnicians !== 1 ? 's' : ''} online now`
                  : 'No technicians online right now'}
              </h3>
              <p className="section-copy">
                {activeTechnicians.length} active in roster
                {urgentJobs > 0 ? ` · ${urgentJobs} urgent job${urgentJobs !== 1 ? 's' : ''}` : ''}
                {staleLocations > 0 ? ` · ${staleLocations} stale GPS ping${staleLocations !== 1 ? 's' : ''}` : ' · all GPS fresh'}
              </p>
              <button
                type="button"
                className="ghost-button"
                onClick={() => setActiveTab('presence')}
              >
                View presence
              </button>
            </article>

            <section className="metrics-grid metrics-grid-dark">
              <MetricCard label="Active technicians" value={activeTechnicians.length} note={`${onlineTechnicians} online now`} />
              <MetricCard label="Visible jobs" value={jobsTotal} note={`${urgentJobs} urgent`} />
              <MetricCard label="Latest GPS records" value={locationsTotal} note={`${staleLocations} stale`} />
              <MetricCard label="Presence records" value={presenceTotal} note="Live mobile sessions" />
            </section>

            <article className="panel dashboard-panel dashboard-panel-wide">
              <div className="section-head section-head-tight">
                <div>
                  <h2>Operational snapshot</h2>
                  <p className="section-copy">
                    Quick read on the three most important streams for dispatch control.
                  </p>
                </div>
              </div>
              <div className="mini-grid">
                <div className="mini-card">
                  <span>Jobs under watch</span>
                  <strong>{jobs.slice(0, 1)[0]?.title || 'No jobs loaded yet'}</strong>
                  <p>
                    {jobs.slice(0, 1)[0]
                      ? `${jobs[0].city}, ${jobs[0].country}`
                      : 'Connect the backend and sign in to review the live job feed.'}
                  </p>
                </div>
                <div className="mini-card">
                  <span>Latest tracked technician</span>
                  <strong>{locations.slice(0, 1)[0]?.technician_name || 'Awaiting location data'}</strong>
                  <p>
                    {locations.slice(0, 1)[0]
                      ? formatDubaiTime(locations[0].recorded_at)
                      : 'Location freshness will appear here after technician pings arrive.'}
                  </p>
                </div>
                <div className="mini-card">
                  <span>Current session signal</span>
                  <strong>{presence.slice(0, 1)[0]?.technician_name || 'Awaiting presence data'}</strong>
                  <p>
                    {presence.slice(0, 1)[0]
                      ? `${presence[0].is_online ? 'Online' : 'Offline'} · last seen ${formatDubaiTime(
                          presence[0].last_seen_at,
                        )}`
                      : 'Presence status will surface here when technicians log in.'}
                  </p>
                </div>
              </div>
            </article>

            <article className="panel dashboard-panel">
              <div className="section-head section-head-tight">
                <div>
                  <h2>Queue preview</h2>
                  <p className="section-copy">A compact preview of the current jobs feed.</p>
                </div>
              </div>
              <div className="list-table">
                {jobs.slice(0, 4).map((job) => (
                  <button
                    key={job.id}
                    type="button"
                    className="list-row selectable-row"
                    onClick={() => {
                      setSelectedJobId(job.id);
                      setActiveTab('jobs');
                    }}
                  >
                    <div>
                      <strong>{job.title}</strong>
                      <p>
                        {job.city}, {job.country}
                      </p>
                    </div>
                    <div className="row-meta">
                      <span className={`tone-chip ${toneFor(job.status)}`}>
                        {job.status.replace('_', ' ')}
                      </span>
                      <span className={`tone-chip ${toneFor(job.priority)}`}>
                        {job.priority}
                      </span>
                    </div>
                  </button>
                ))}
                {jobs.length === 0 ? (
                  <p className="empty-state">The jobs list preview will appear here once data is loaded.</p>
                ) : null}
              </div>
            </article>

            <article className="panel dashboard-panel">
              <div className="section-head section-head-tight">
                <div>
                  <h2>Field presence</h2>
                  <p className="section-copy">A live technician pulse in the new shell.</p>
                </div>
              </div>
              <div className="list-table">
                {presence.slice(0, 4).map((entry) => (
                  <button
                    key={entry.technician_id}
                    type="button"
                    className="list-row selectable-row"
                    onClick={() => {
                      setSelectedPresenceTechnicianId(entry.technician_id);
                      setActiveTab('presence');
                    }}
                  >
                    <div>
                      <strong>{entry.technician_name}</strong>
                      <p>Session started {formatDubaiTime(entry.session_started_at)}</p>
                    </div>
                    <div className="row-meta">
                      <span
                        className={`tone-chip ${toneFor(
                          entry.is_online ? 'online' : 'offline',
                        )}`}
                      >
                        {entry.is_online ? 'online' : 'offline'}
                      </span>
                    </div>
                  </button>
                ))}
                {presence.length === 0 ? (
                  <p className="empty-state">Presence preview will populate here when technicians connect.</p>
                ) : null}
              </div>
            </article>
          </section>
        ) : null}

        {activeTab === 'users' ? (
        <section className="content-grid">
          <article className="panel">
            <div className="section-head">
              <div>
                <h2>Users</h2>
                <p className="section-copy">
                  {usersTotal} user{usersTotal !== 1 ? 's' : ''} — manage accounts, roles, and technician codes.
                </p>
              </div>
              <button
                type="button"
                className={showCreateUser ? 'ghost-button' : 'primary-button'}
                onClick={() => {
                  setShowCreateUser((prev) => !prev);
                  setCreateUserError(null);
                }}
              >
                {showCreateUser ? 'Cancel' : 'New user'}
              </button>
            </div>
            <div className="toolbar multi-toolbar">
              <input
                value={usersQuery}
                onChange={(event) => {
                  setUsersOffset(0);
                  setUsersQuery(event.target.value);
                }}
                placeholder="Search by name, email, or technician code"
              />
              <select
                value={usersRole}
                onChange={(event) => {
                  setUsersOffset(0);
                  setUsersRole(event.target.value as UserRole | '');
                }}
              >
                <option value="">All roles</option>
                <option value="admin">Admin</option>
                <option value="manager">Manager</option>
                <option value="technician">Technician</option>
              </select>
              <select
                value={usersAvailability}
                onChange={(event) => {
                  setUsersOffset(0);
                  setUsersAvailability(event.target.value as AvailabilityFilter);
                }}
              >
                <option value="all">All users</option>
                <option value="active">Active only</option>
                <option value="inactive">Inactive only</option>
              </select>
            </div>
            <div className="list-table">
              {usersLoading ? (
                <p className="empty-state">Loading users...</p>
              ) : null}
              {!usersLoading && usersError ? (
                <p className="error-text">{usersError}</p>
              ) : null}
              {!usersLoading && !usersError && users.length === 0 ? (
                <p className="empty-state">No users match the current filters.</p>
              ) : null}
              {!usersLoading &&
                !usersError &&
                users.map((user) => (
                  <div key={user.id} className="list-row">
                    <div>
                      <strong>{user.full_name}</strong>
                      <p>{user.email}</p>
                      {user.technician_code ? (
                        <small>{user.technician_code}</small>
                      ) : null}
                    </div>
                    <div className="row-meta row-meta-col">
                      <span className={`tone-chip ${toneFor(user.is_active ? 'active' : 'inactive')}`}>
                        {user.is_active ? 'active' : 'inactive'}
                      </span>
                      <span className="request-chip">{user.role}</span>
                    </div>
                  </div>
                ))}
            </div>
            <Pagination
              offset={usersOffset}
              total={usersTotal}
              onChange={setUsersOffset}
            />
          </article>

          <article className="panel detail-panel">
            {showCreateUser ? (
              <>
                <h2>New user</h2>
                <form className="create-job-form" onSubmit={handleCreateUser}>
                  <div className="form-row">
                    <label className="field-label">
                      Full name <span className="required-mark">*</span>
                      <input name="full_name" type="text" placeholder="e.g. Ahmed Al Mansoori" required />
                    </label>
                    <label className="field-label">
                      Email <span className="required-mark">*</span>
                      <input name="email" type="email" placeholder="user@example.com" required />
                    </label>
                  </div>
                  <div className="form-row">
                    <label className="field-label">
                      Password <span className="required-mark">*</span>
                      <input name="password" type="password" placeholder="Minimum 8 characters" required />
                    </label>
                    <label className="field-label">
                      Role <span className="required-mark">*</span>
                      <select
                        name="role"
                        value={createUserRole}
                        onChange={(e) => setCreateUserRole(e.target.value as UserRole)}
                        required
                      >
                        <option value="technician">Technician</option>
                        <option value="manager">Manager</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>
                  </div>
                  {createUserRole === 'technician' ? (
                    <label className="field-label">
                      Technician code <span className="required-mark">*</span>
                      <input name="technician_code" type="text" placeholder="e.g. DXB-002" required />
                    </label>
                  ) : null}
                  {createUserError ? (
                    <p className="error-text">{createUserError}</p>
                  ) : null}
                  <div className="form-actions">
                    <button type="submit" className="primary-button" disabled={busy === 'create-user'}>
                      {busy === 'create-user' ? 'Creating...' : 'Create user'}
                    </button>
                    <button type="button" className="ghost-button" onClick={() => setShowCreateUser(false)}>
                      Cancel
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <>
                <h2>Technician roster</h2>
                <p className="section-copy">
                  Active technicians available for job assignment.
                </p>
                {activeTechnicians.length === 0 ? (
                  <p className="empty-state">No active technicians available.</p>
                ) : null}
                {activeTechnicians.map((technician) => (
                  <div key={technician.id} className="detail-card">
                    <strong>{technician.full_name}</strong>
                    <p>{technician.email}</p>
                    <small>
                      {technician.technician_code || 'No code'} · Created {formatDubaiTime(technician.created_at)}
                    </small>
                  </div>
                ))}
              </>
            )}
          </article>
        </section>
      ) : null}

        {activeTab === 'jobs' ? (
        <section className="content-grid">
          <article className="panel">
            <div className="section-head">
              <div>
                <h2>Jobs</h2>
                <p className="section-copy">
                  {jobsTotal} job{jobsTotal !== 1 ? 's' : ''} — select to inspect, assign, and manage status.
                </p>
              </div>
              <button
                type="button"
                className={showCreateJob ? 'ghost-button' : 'primary-button'}
                onClick={() => {
                  setShowCreateJob((prev) => !prev);
                  setCreateJobError(null);
                }}
              >
                {showCreateJob ? 'Cancel' : 'New job'}
              </button>
            </div>
            <div className="toolbar multi-toolbar">
              <input
                value={jobsQuery}
                onChange={(event) => {
                  setJobsOffset(0);
                  setJobsQuery(event.target.value);
                }}
                placeholder="Search title, description, city, or address"
              />
              <select
                value={jobsStatus}
                onChange={(event) => {
                  setJobsOffset(0);
                  setJobsStatus(event.target.value as JobStatus | '');
                }}
              >
                <option value="">All statuses</option>
                <option value="not_started">Not started</option>
                <option value="in_progress">In progress</option>
                <option value="completed">Completed</option>
              </select>
              <select
                value={jobsPriority}
                onChange={(event) => {
                  setJobsOffset(0);
                  setJobsPriority(event.target.value as JobPriority | '');
                }}
              >
                <option value="">All priorities</option>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
            <div className="list-table">
              {jobsLoading ? <p className="empty-state">Loading jobs...</p> : null}
              {!jobsLoading && jobsError ? (
                <p className="error-text">{jobsError}</p>
              ) : null}
              {!jobsLoading && !jobsError && jobs.length === 0 ? (
                <p className="empty-state">No jobs match the current filters.</p>
              ) : null}
              {!jobsLoading &&
                !jobsError &&
                jobs.map((job) => (
                  <button
                    key={job.id}
                    type="button"
                    className={
                      job.id === selectedJobId
                        ? 'list-row selectable-row selected'
                        : 'list-row selectable-row'
                    }
                    onClick={() => {
                      setSelectedJobId(job.id);
                      setShowCreateJob(false);
                    }}
                  >
                    <div className="job-row-body">
                      <strong>{job.title}</strong>
                      <p>{job.city}, {job.country}</p>
                      <small className="job-schedule-line">
                        {job.scheduled_start
                          ? formatDubaiTime(job.scheduled_start)
                          : 'Unscheduled'}
                      </small>
                    </div>
                    <div className="row-meta row-meta-col">
                      <span className={`tone-chip ${toneFor(job.status)}`}>
                        {job.status.replace(/_/g, ' ')}
                      </span>
                      <span className={`tone-chip ${toneFor(job.priority)}`}>
                        {job.priority}
                      </span>
                    </div>
                  </button>
                ))}
            </div>
            <Pagination
              offset={jobsOffset}
              total={jobsTotal}
              onChange={setJobsOffset}
            />
          </article>

          <article className="panel detail-panel">
            {showCreateJob ? (
              <>
                <h2>New job</h2>
                <form className="create-job-form" onSubmit={handleCreateJob}>
                  <label className="field-label">
                    Title <span className="required-mark">*</span>
                    <input
                      name="title"
                      type="text"
                      placeholder="e.g. Emergency compressor repair"
                      required
                    />
                  </label>
                  <div className="form-row">
                    <label className="field-label">
                      Address line 1 <span className="required-mark">*</span>
                      <input name="address_line1" type="text" placeholder="Street address" required />
                    </label>
                    <label className="field-label">
                      Address line 2
                      <input name="address_line2" type="text" placeholder="Apt, floor, building" />
                    </label>
                  </div>
                  <div className="form-row form-row-3">
                    <label className="field-label">
                      City <span className="required-mark">*</span>
                      <input name="city" type="text" placeholder="Dubai" required />
                    </label>
                    <label className="field-label">
                      State <span className="required-mark">*</span>
                      <input name="state" type="text" placeholder="Dubai" required />
                    </label>
                    <label className="field-label">
                      Postal code <span className="required-mark">*</span>
                      <input name="postal_code" type="text" required />
                    </label>
                  </div>
                  <div className="form-row">
                    <label className="field-label">
                      Country
                      <input name="country" type="text" defaultValue="UAE" />
                    </label>
                    <label className="field-label">
                      Priority
                      <select name="priority" defaultValue="medium">
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="urgent">Urgent</option>
                      </select>
                    </label>
                  </div>
                  <div className="form-row">
                    <label className="field-label">
                      Scheduled start
                      <input name="scheduled_start" type="datetime-local" />
                    </label>
                    <label className="field-label">
                      Scheduled end
                      <input name="scheduled_end" type="datetime-local" />
                    </label>
                  </div>
                  <label className="field-label">
                    Description
                    <textarea name="description" rows={3} placeholder="Optional job description" />
                  </label>
                  {createJobError ? (
                    <p className="error-text">{createJobError}</p>
                  ) : null}
                  <div className="form-actions">
                    <button
                      type="submit"
                      className="primary-button"
                      disabled={busy === 'create-job'}
                    >
                      {busy === 'create-job' ? 'Creating...' : 'Create job'}
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => setShowCreateJob(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </>
            ) : null}

            {!showCreateJob && jobDetailLoading ? (
              <p className="empty-state">Loading job detail...</p>
            ) : null}
            {!showCreateJob && !jobDetailLoading && jobDetailError ? (
              <p className="error-text">{jobDetailError}</p>
            ) : null}
            {!showCreateJob && !jobDetailLoading && !jobDetailError && !selectedJob ? (
              <p className="empty-state">
                Select a job to inspect details, manage assignments, and view the activity timeline.
              </p>
            ) : null}

            {!showCreateJob && !jobDetailLoading && !jobDetailError && selectedJob ? (
              <>
                <div className="job-detail-header">
                  <div className="job-detail-chips">
                    <span className={`tone-chip ${toneFor(selectedJob.status)}`}>
                      {selectedJob.status.replace(/_/g, ' ')}
                    </span>
                    <span className={`tone-chip ${toneFor(selectedJob.priority)}`}>
                      {selectedJob.priority}
                    </span>
                  </div>
                  <h2>{selectedJob.title}</h2>
                  {selectedJob.description ? (
                    <p className="section-copy">{selectedJob.description}</p>
                  ) : null}
                </div>

                <div className="info-grid">
                  <div className="info-block">
                    <p className="info-label">Location</p>
                    <p>{selectedJob.address_line1}</p>
                    {selectedJob.address_line2 ? <p>{selectedJob.address_line2}</p> : null}
                    <p>
                      {selectedJob.city}, {selectedJob.state} {selectedJob.postal_code}
                    </p>
                    <p>{selectedJob.country}</p>
                  </div>
                  <div className="info-block">
                    <p className="info-label">Schedule</p>
                    <p>Start: {formatDubaiTime(selectedJob.scheduled_start)}</p>
                    <p>End: {formatDubaiTime(selectedJob.scheduled_end)}</p>
                  </div>
                </div>

                <div className="status-actions-block">
                  <p className="info-label">Change status</p>
                  <div className="status-actions">
                    {(
                      ['not_started', 'in_progress', 'completed'] as JobStatus[]
                    )
                      .filter((s) => s !== selectedJob.status)
                      .map((s) => (
                        <button
                          key={s}
                          type="button"
                          className="ghost-button"
                          onClick={() => handleUpdateJobStatus(s)}
                          disabled={busy === `status-${s}`}
                        >
                          {busy === `status-${s}`
                            ? 'Updating...'
                            : `Set ${s.replace(/_/g, ' ')}`}
                        </button>
                      ))}
                  </div>
                </div>

                <section>
                  <h3>Assign technician</h3>
                  <div className="inline-form">
                    <select
                      value={assignmentTechnicianId}
                      onChange={(event) =>
                        setAssignmentTechnicianId(
                          event.target.value ? Number(event.target.value) : '',
                        )
                      }
                    >
                      <option value="">Choose a technician</option>
                      {activeTechnicians.map((technician) => (
                        <option key={technician.id} value={technician.id}>
                          {technician.full_name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="primary-button"
                      onClick={handleAssignTechnician}
                      disabled={busy === 'assign' || assignmentTechnicianId === ''}
                    >
                      {busy === 'assign' ? 'Saving...' : 'Assign'}
                    </button>
                  </div>
                  {jobAssignments.length === 0 ? (
                    <p className="empty-state">No technicians assigned yet.</p>
                  ) : null}
                  {jobAssignments.map((assignment) => {
                    const tech = technicianDirectory.find(
                      (t) => t.id === assignment.technician_id,
                    );
                    return (
                      <div key={assignment.id} className="detail-card split-card">
                        <div>
                          <strong>
                            {tech?.full_name ||
                              `Technician #${assignment.technician_id}`}
                          </strong>
                          <p>Assigned {formatDubaiTime(assignment.assigned_at)}</p>
                        </div>
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => handleRemoveAssignment(assignment.id)}
                          disabled={busy === `remove-${assignment.id}`}
                        >
                          {busy === `remove-${assignment.id}` ? 'Removing...' : 'Remove'}
                        </button>
                      </div>
                    );
                  })}
                </section>

                {jobEvents.length > 0 ? (
                  <section>
                    <h3>Activity timeline</h3>
                    <div className="timeline-track">
                      {jobEvents.map((event) => {
                        const actorName =
                          currentUser?.id === event.actor_id
                            ? currentUser.full_name
                            : (technicianDirectory.find((t) => t.id === event.actor_id)
                                ?.full_name ?? `Actor #${event.actor_id}`);
                        return (
                          <div
                            key={event.id}
                            className={`timeline-item timeline-${event.event_type}`}
                          >
                            <div className="timeline-dot" />
                            <div className="timeline-content">
                              <strong>{event.event_type.replace(/_/g, ' ')}</strong>
                              <p>
                                {actorName} · {formatDubaiTime(event.occurred_at)}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                ) : null}

                {jobUpdates.length > 0 ? (
                  <section>
                    <h3>Updates</h3>
                    {jobUpdates.map((update) => {
                      const authorName =
                        currentUser?.id === update.author_id
                          ? currentUser.full_name
                          : (technicianDirectory.find((t) => t.id === update.author_id)
                              ?.full_name ?? `Author #${update.author_id}`);
                      return (
                        <div key={update.id} className="detail-card update-card">
                          <p>{update.message}</p>
                          <small>
                            {authorName} · {formatDubaiTime(update.created_at)}
                            {update.photos.length > 0
                              ? ` · ${update.photos.length} photo${update.photos.length > 1 ? 's' : ''}`
                              : ''}
                          </small>
                        </div>
                      );
                    })}
                  </section>
                ) : null}

                {jobEvents.length === 0 && jobUpdates.length === 0 ? (
                  <p className="empty-state">
                    No activity or updates recorded for this job yet.
                  </p>
                ) : null}
              </>
            ) : null}
          </article>
        </section>
      ) : null}

        {activeTab === 'locations' ? (
        <section className="content-grid">
          <article className="panel">
            <div className="section-head">
              <div>
                <h2>Latest technician locations</h2>
                <p className="section-copy">
                  Auto-refreshes every 30 s · {locationsTotal} record{locationsTotal !== 1 ? 's' : ''}
                  {staleLocations > 0 ? ` · ${staleLocations} stale` : ' · all fresh'}
                </p>
              </div>
              <TogglePill
                label="Include stale"
                checked={includeStaleLocations}
                onChange={(value) => {
                  setLocationsOffset(0);
                  setIncludeStaleLocations(value);
                }}
              />
            </div>
            <div className="toolbar">
              <input
                value={locationsQuery}
                onChange={(event) => {
                  setLocationsOffset(0);
                  setLocationsQuery(event.target.value);
                }}
                placeholder="Search technician name"
              />
            </div>
            <div className="list-table">
              {locationsLoading ? (
                <p className="empty-state">Loading latest locations...</p>
              ) : null}
              {!locationsLoading && locationsError ? (
                <p className="error-text">{locationsError}</p>
              ) : null}
              {!locationsLoading && !locationsError && locations.length === 0 ? (
                <p className="empty-state">
                  No technician locations match the current filters.
                </p>
              ) : null}
              {!locationsLoading &&
                !locationsError &&
                locations.map((location) => (
                  <button
                    key={location.id}
                    type="button"
                    className={
                      selectedLocationTechnicianId === location.technician_id
                        ? 'list-row selectable-row selected'
                        : 'list-row selectable-row'
                    }
                    onClick={() =>
                      setSelectedLocationTechnicianId(location.technician_id)
                    }
                  >
                    <div className="job-row-body">
                      <strong>{location.technician_name}</strong>
                      <p className="loc-coords">
                        {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}
                      </p>
                      <small className="job-schedule-line">{timeAgo(location.recorded_at)}</small>
                    </div>
                    <div className="row-meta row-meta-col">
                      <span className={`tone-chip ${toneFor(location.is_stale ? 'stale' : 'fresh')}`}>
                        {location.is_stale ? 'stale' : 'fresh'}
                      </span>
                      <a
                        className="loc-map-link"
                        href={`https://maps.google.com/?q=${location.latitude},${location.longitude}`}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                      >
                        map ↗
                      </a>
                    </div>
                  </button>
                ))}
            </div>
            <Pagination
              offset={locationsOffset}
              total={locationsTotal}
              onChange={setLocationsOffset}
            />
          </article>

          <article className="panel detail-panel">
            <h2>Location history</h2>
            {locationHistoryLoading ? (
              <p className="empty-state">Loading location history...</p>
            ) : null}
            {!locationHistoryLoading && locationHistoryError ? (
              <p className="error-text">{locationHistoryError}</p>
            ) : null}
            {!locationHistoryLoading &&
            !locationHistoryError &&
            selectedLocationTechnicianId == null ? (
              <p className="empty-state">
                Select a technician to view recent GPS history.
              </p>
            ) : null}
            {!locationHistoryLoading &&
              !locationHistoryError &&
              selectedLocationTechnicianId != null &&
              locationHistory.length === 0 ? (
                <p className="empty-state">No location history recorded yet.</p>
              ) : null}
            {!locationHistoryLoading &&
              !locationHistoryError &&
              locationHistory.map((entry) => (
                <div key={entry.id} className="detail-card">
                  <div className="split-line">
                    <span className="loc-coords">
                      {entry.latitude.toFixed(5)}, {entry.longitude.toFixed(5)}
                    </span>
                    <a
                      className="loc-map-link"
                      href={`https://maps.google.com/?q=${entry.latitude},${entry.longitude}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      map ↗
                    </a>
                  </div>
                  <p>Accuracy: {entry.accuracy_meters != null ? `${entry.accuracy_meters} m` : 'n/a'}</p>
                  <small>{formatDubaiTime(entry.recorded_at)} · {timeAgo(entry.recorded_at)}</small>
                </div>
              ))}
          </article>
        </section>
      ) : null}

        {activeTab === 'presence' ? (
        <section className="content-grid">
          <article className="panel">
            <div className="section-head">
              <div>
                <h2>Technician presence</h2>
                <p className="section-copy">
                  Auto-refreshes every 30 s · {onlineTechnicians} online now
                </p>
              </div>
              <TogglePill
                label="Include offline"
                checked={includeOfflinePresence}
                onChange={(value) => {
                  setPresenceOffset(0);
                  setIncludeOfflinePresence(value);
                }}
              />
            </div>
            <div className="toolbar">
              <input
                value={presenceQuery}
                onChange={(event) => {
                  setPresenceOffset(0);
                  setPresenceQuery(event.target.value);
                }}
                placeholder="Search technician name"
              />
            </div>
            <div className="list-table">
              {presenceLoading ? (
                <p className="empty-state">Loading presence records...</p>
              ) : null}
              {!presenceLoading && presenceError ? (
                <p className="error-text">{presenceError}</p>
              ) : null}
              {!presenceLoading && !presenceError && presence.length === 0 ? (
                <p className="empty-state">No presence records match the current filters.</p>
              ) : null}
              {!presenceLoading &&
                !presenceError &&
                presence.map((entry) => (
                  <button
                    key={entry.technician_id}
                    type="button"
                    className={
                      selectedPresenceTechnicianId === entry.technician_id
                        ? 'list-row selectable-row selected'
                        : 'list-row selectable-row'
                    }
                    onClick={() =>
                      setSelectedPresenceTechnicianId(entry.technician_id)
                    }
                  >
                    <div className="job-row-body">
                      <div className="presence-name-row">
                        <span className={`presence-dot ${entry.is_online ? 'dot-online' : 'dot-offline'}`} />
                        <strong>{entry.technician_name}</strong>
                      </div>
                      <p>Last seen {timeAgo(entry.last_seen_at)}</p>
                      <small className="job-schedule-line">
                        Session {formatDubaiTime(entry.session_started_at)}
                      </small>
                    </div>
                    <div className="row-meta row-meta-col">
                      <span className={`tone-chip ${toneFor(entry.is_online ? 'online' : 'offline')}`}>
                        {entry.is_online ? 'online' : 'offline'}
                      </span>
                      <span className="request-chip">
                        {entry.is_logged_in ? 'logged in' : 'logged out'}
                      </span>
                    </div>
                  </button>
                ))}
            </div>
            <Pagination
              offset={presenceOffset}
              total={presenceTotal}
              onChange={setPresenceOffset}
            />
          </article>

          <article className="panel detail-panel">
            <h2>Presence detail</h2>
            {presenceDetailLoading ? (
              <p className="empty-state">Loading presence detail...</p>
            ) : null}
            {!presenceDetailLoading && presenceDetailError ? (
              <p className="error-text">{presenceDetailError}</p>
            ) : null}
            {!presenceDetailLoading &&
            !presenceDetailError &&
            !selectedPresence ? (
              <p className="empty-state">
                Select a technician to inspect their current presence record.
              </p>
            ) : null}
            {!presenceDetailLoading && !presenceDetailError && selectedPresence ? (
              <>
                <div className="detail-card">
                  <div className="presence-detail-header">
                    <span className={`presence-dot-large ${selectedPresence.is_online ? 'dot-online' : 'dot-offline'}`} />
                    <div>
                      <strong>{selectedPresence.technician_name}</strong>
                      <p className={selectedPresence.is_online ? 'status-online' : 'status-offline'}>
                        {selectedPresence.is_online ? 'Online' : 'Offline'} · last seen {timeAgo(selectedPresence.last_seen_at)}
                      </p>
                    </div>
                  </div>
                  <p>
                    {selectedPresence.is_logged_in
                      ? 'Logged into the mobile app'
                      : 'Logged out of the mobile app'}
                  </p>
                  <small>
                    Last heartbeat {formatDubaiTime(selectedPresence.last_seen_at)}
                  </small>
                </div>

                <div className="detail-card">
                  <p className="info-label">Latest location</p>
                  {selectedPresence.latest_location ? (
                    <>
                      <div className="split-line">
                        <span className="loc-coords">
                          {selectedPresence.latest_location.latitude.toFixed(5)},{' '}
                          {selectedPresence.latest_location.longitude.toFixed(5)}
                        </span>
                        <a
                          className="loc-map-link"
                          href={`https://maps.google.com/?q=${selectedPresence.latest_location.latitude},${selectedPresence.latest_location.longitude}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          map ↗
                        </a>
                      </div>
                      <small>
                        {formatDubaiTime(selectedPresence.latest_location.recorded_at)} · {timeAgo(selectedPresence.latest_location.recorded_at)}
                      </small>
                    </>
                  ) : (
                    <p>No location recorded for this technician yet.</p>
                  )}
                </div>
              </>
            ) : null}
          </article>
        </section>
      ) : null}
      </main>
    </div>
  );
}

function MetricCard({
  label,
  note,
  value,
}: {
  label: string;
  note?: string;
  value: number;
}) {
  return (
    <article className="panel metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </article>
  );
}

function TogglePill({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle-pill">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

function Pagination({
  offset,
  total,
  onChange,
}: {
  offset: number;
  total: number;
  onChange: (value: number) => void;
}) {
  const nextOffset = offset + PAGE_SIZE;
  const previousDisabled = offset <= 0;
  const nextDisabled = nextOffset >= total;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="pagination-row">
      <button
        type="button"
        onClick={() => onChange(Math.max(0, offset - PAGE_SIZE))}
        disabled={previousDisabled}
      >
        Previous
      </button>
      <span>
        Showing {start}-{end} of {total}
      </span>
      <button
        type="button"
        onClick={() => onChange(nextOffset)}
        disabled={nextDisabled}
      >
        Next
      </button>
    </div>
  );
}
