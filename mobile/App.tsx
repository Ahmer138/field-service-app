import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  AppState,
  type AppStateStatus,
  Image,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { ApiError, api } from './src/lib/api';
import {
  clearStoredToken,
  loadStoredToken,
  saveStoredToken,
} from './src/lib/session';
import type {
  Job,
  JobEvent,
  JobUpdate,
  TechnicianPresence,
  User,
} from './src/types';

type DraftPhoto = {
  uri: string;
  name: string;
  type: string;
};

const HEARTBEAT_INTERVAL_MS = 45000;
const JOB_REFRESH_INTERVAL_MS = 8000;

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

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [appState, setAppState] = useState<AppStateStatus>(
    AppState.currentState,
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [jobEvents, setJobEvents] = useState<JobEvent[]>([]);
  const [jobUpdates, setJobUpdates] = useState<JobUpdate[]>([]);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [jobDetailError, setJobDetailError] = useState<string | null>(null);

  const [updateMessage, setUpdateMessage] = useState('');
  const [draftPhoto, setDraftPhoto] = useState<DraftPhoto | null>(null);

  const [presence, setPresence] = useState<TechnicianPresence | null>(null);
  const [trackingNote, setTrackingNote] = useState<string | null>(null);
  const [lastLocationSentAt, setLastLocationSentAt] = useState<string | null>(
    null,
  );

  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobsTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const locationWatcherRef = useRef<Location.LocationSubscription | null>(null);

  const canCheckIn = selectedJob?.status === 'not_started';
  const canCheckOut = selectedJob?.status === 'in_progress';

  const selectedJobUpdatesCount = useMemo(
    () => jobUpdates.reduce((total, update) => total + update.photos.length, 0),
    [jobUpdates],
  );

  useEffect(() => {
    const subscription = AppState.addEventListener('change', setAppState);
    return () => {
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const storedToken = await loadStoredToken();
        if (!storedToken) {
          return;
        }

        const user = await api.me(storedToken);
        if (cancelled) {
          return;
        }
        if (user.role !== 'technician') {
          await clearStoredToken();
          if (!cancelled) {
            setAuthError('This mobile app is only for technician accounts.');
          }
          return;
        }

        setToken(storedToken);
        setCurrentUser(user);
      } catch (error) {
        await clearStoredToken();
        if (!cancelled) {
          setAuthError(formatApiError(error));
        }
      } finally {
        if (!cancelled) {
          setBooting(false);
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!token || !currentUser) {
      stopRealtimeWork();
      return;
    }
    const activeToken = token;

    if (appState !== 'active') {
      stopRealtimeWork();
      setTrackingNote('Realtime heartbeat and GPS pause while the app is backgrounded.');
      return;
    }

    let cancelled = false;

    setTrackingNote(null);

    async function startRealtimeWork() {
      stopRealtimeWork();
      try {
        await sendHeartbeat(activeToken);
        if (cancelled) {
          return;
        }

        heartbeatTimerRef.current = setInterval(() => {
          void sendHeartbeat(activeToken);
        }, HEARTBEAT_INTERVAL_MS);

        const permission = await Location.requestForegroundPermissionsAsync();
        if (cancelled) {
          return;
        }
        if (permission.status !== 'granted') {
          setTrackingNote(
            'Location permission was not granted. Heartbeat is active, but GPS is paused.',
          );
          return;
        }

        setTrackingNote('Foreground heartbeat and GPS are active while you stay logged in.');

        const currentPosition = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        if (!cancelled) {
          await sendDeviceLocation(activeToken, currentPosition);
        }

        locationWatcherRef.current = await Location.watchPositionAsync(
          {
            accuracy: Location.Accuracy.Balanced,
            timeInterval: HEARTBEAT_INTERVAL_MS,
            distanceInterval: 20,
          },
          (position) => {
            void sendDeviceLocation(activeToken, position);
          },
        );
      } catch (error) {
        if (!cancelled) {
          setTrackingNote(formatApiError(error));
        }
      }
    }

    void startRealtimeWork();

    return () => {
      cancelled = true;
      stopRealtimeWork();
    };
  }, [token, currentUser, appState]);

  useEffect(() => {
    if (!token || !currentUser) {
      return;
    }
    const activeToken = token;

    void loadJobs(activeToken);

    stopJobsRefresh();
    jobsTimerRef.current = setInterval(() => {
      void loadJobs(activeToken);
    }, JOB_REFRESH_INTERVAL_MS);

    return () => {
      stopJobsRefresh();
    };
  }, [token, currentUser]);

  useEffect(() => {
    if (!token || selectedJobId == null) {
      setSelectedJob(null);
      setJobEvents([]);
      setJobUpdates([]);
      return;
    }

    void loadJobDetail(token, selectedJobId);
  }, [token, selectedJobId]);

  async function runGuarded<T>(task: () => Promise<T>) {
    try {
      return await task();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        await clearLocalSession('Your session expired. Please log in again.');
      }
      throw error;
    }
  }

  async function clearLocalSession(nextMessage: string) {
    stopRealtimeWork();
    stopJobsRefresh();
    await clearStoredToken();
    setToken(null);
    setCurrentUser(null);
    setJobs([]);
    setSelectedJobId(null);
    setSelectedJob(null);
    setJobEvents([]);
    setJobUpdates([]);
    setPresence(null);
    setDraftPhoto(null);
    setUpdateMessage('');
    setAuthError(nextMessage);
  }

  function stopRealtimeWork() {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
    if (locationWatcherRef.current) {
      locationWatcherRef.current.remove();
      locationWatcherRef.current = null;
    }
  }

  function stopJobsRefresh() {
    if (jobsTimerRef.current) {
      clearInterval(jobsTimerRef.current);
      jobsTimerRef.current = null;
    }
  }

  async function sendHeartbeat(activeToken: string) {
    const snapshot = await runGuarded(() => api.heartbeat(activeToken));
    setPresence(snapshot);
  }

  async function sendDeviceLocation(
    activeToken: string,
    location: Location.LocationObject,
  ) {
    const recorded = await runGuarded(() =>
      api.sendLocation(activeToken, {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        accuracy_meters: location.coords.accuracy,
        recorded_at: new Date(location.timestamp).toISOString(),
      }),
    );
    setLastLocationSentAt(recorded.recorded_at);
  }

  async function loadJobs(activeToken: string) {
    setJobsLoading(true);
    setJobsError(null);
    try {
      const response = await runGuarded(() => api.jobs(activeToken));
      setJobs(response.items);
      if (response.items.length === 0) {
        setSelectedJobId(null);
      } else if (
        selectedJobId == null ||
        !response.items.some((job) => job.id === selectedJobId)
      ) {
        setSelectedJobId(response.items[0].id);
      }
    } catch (error) {
      setJobsError(formatApiError(error));
    } finally {
      setJobsLoading(false);
      setRefreshing(false);
    }
  }

  async function loadJobDetail(activeToken: string, jobId: number) {
    setJobDetailLoading(true);
    setJobDetailError(null);
    try {
      const [job, events, updates] = await Promise.all([
        runGuarded(() => api.job(activeToken, jobId)),
        runGuarded(() => api.events(activeToken, jobId)),
        runGuarded(() => api.updates(activeToken, jobId)),
      ]);
      setSelectedJob(job);
      setJobEvents(events);
      setJobUpdates(updates);
    } catch (error) {
      setJobDetailError(formatApiError(error));
    } finally {
      setJobDetailLoading(false);
    }
  }

  async function handleLogin() {
    setBusy('login');
    setAuthError(null);
    try {
      const auth = await api.login(email.trim(), password);
      const user = await api.me(auth.access_token);
      if (user.role !== 'technician') {
        setAuthError('This mobile app is only for technician accounts.');
        return;
      }
      await saveStoredToken(auth.access_token);
      setToken(auth.access_token);
      setCurrentUser(user);
      setPassword('');
      setMessage('Signed in. Heartbeat and GPS will run while the app remains active.');
    } catch (error) {
      setAuthError(formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleLogout() {
    if (!token) {
      await clearLocalSession('You have been logged out.');
      return;
    }

    setBusy('logout');
    try {
      await api.logout(token);
    } catch {
      // The session still has to be removed locally.
    } finally {
      await clearLocalSession('You have been logged out.');
      setBusy(null);
    }
  }

  async function handleRefresh() {
    if (!token) {
      return;
    }
    setRefreshing(true);
    await Promise.all([
      loadJobs(token),
      selectedJobId != null ? loadJobDetail(token, selectedJobId) : Promise.resolve(),
      sendHeartbeat(token).catch(() => undefined),
    ]);
  }

  async function handleCheckIn() {
    if (!token || !selectedJob) {
      return;
    }

    setBusy('check-in');
    try {
      await runGuarded(() => api.checkIn(token, selectedJob.id));
      await Promise.all([loadJobs(token), loadJobDetail(token, selectedJob.id)]);
      setMessage('Checked in successfully.');
    } catch (error) {
      Alert.alert('Check-in failed', formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleCheckOut() {
    if (!token || !selectedJob) {
      return;
    }

    setBusy('check-out');
    try {
      await runGuarded(() => api.checkOut(token, selectedJob.id));
      await Promise.all([loadJobs(token), loadJobDetail(token, selectedJob.id)]);
      setMessage('Checked out successfully.');
    } catch (error) {
      Alert.alert('Check-out failed', formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  async function handlePickPhoto() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (permission.status !== 'granted') {
      Alert.alert(
        'Photo permission required',
        'Allow photo access to attach a job update image.',
      );
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.85,
    });

    if (result.canceled || result.assets.length === 0) {
      return;
    }

    const asset = result.assets[0];
    setDraftPhoto({
      uri: asset.uri,
      name: asset.fileName || `job-update-${Date.now()}.jpg`,
      type: asset.mimeType || 'image/jpeg',
    });
  }

  async function handleSubmitUpdate() {
    if (!token || !selectedJob) {
      return;
    }
    if (!updateMessage.trim()) {
      Alert.alert('Message required', 'Enter a job update message before submitting.');
      return;
    }

    setBusy('submit-update');
    try {
      const createdUpdate = await runGuarded(() =>
        api.createUpdate(token, selectedJob.id, { message: updateMessage.trim() }),
      );

      if (draftPhoto) {
        const formData = new FormData();
        formData.append(
          'file',
          {
            uri: draftPhoto.uri,
            name: draftPhoto.name,
            type: draftPhoto.type,
          } as never,
        );
        await runGuarded(() => api.uploadPhoto(token, selectedJob.id, createdUpdate.id, formData));
      }

      await loadJobDetail(token, selectedJob.id);
      setUpdateMessage('');
      setDraftPhoto(null);
      setMessage('Job update submitted.');
    } catch (error) {
      Alert.alert('Update failed', formatApiError(error));
    } finally {
      setBusy(null);
    }
  }

  if (booting) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <StatusBar style="dark" />
        <View style={styles.centered}>
          <ActivityIndicator size="large" color="#0f6b65" />
          <Text style={styles.loadingTitle}>Restoring technician session</Text>
          <Text style={styles.loadingCopy}>
            Validating the stored token with GET /users/me.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!token || !currentUser) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <StatusBar style="dark" />
        <ScrollView contentContainerStyle={styles.authScroll}>
          <View style={styles.authCard}>
            <Text style={styles.eyebrow}>Field Service Mobile</Text>
            <Text style={styles.title}>Technician login</Text>
            <Text style={styles.copy}>
              Login uses POST /auth/login, then the app validates the session with GET /users/me before starting heartbeat and GPS.
            </Text>

            <TextInput
              style={styles.input}
              placeholder="technician@example.com"
              placeholderTextColor="#6b746d"
              autoCapitalize="none"
              keyboardType="email-address"
              value={email}
              onChangeText={setEmail}
            />
            <TextInput
              style={styles.input}
              placeholder="Password"
              placeholderTextColor="#6b746d"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />
            <Pressable
              style={[styles.primaryButton, busy === 'login' && styles.buttonDisabled]}
              onPress={() => void handleLogin()}
              disabled={busy === 'login'}
            >
              <Text style={styles.primaryButtonText}>
                {busy === 'login' ? 'Signing in...' : 'Sign in'}
              </Text>
            </Pressable>
            {authError ? <Text style={styles.errorText}>{authError}</Text> : null}
            <Text style={styles.caption}>API base URL: {api.baseUrl}</Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={styles.screen}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => void handleRefresh()} />
        }
      >
        <View style={styles.headerCard}>
          <Text style={styles.eyebrow}>Asia/Dubai mobile session</Text>
          <Text style={styles.title}>{currentUser.full_name}</Text>
          <Text style={styles.copy}>
            Logged in as technician {currentUser.technician_code || 'without code'}.
          </Text>
          <View style={styles.chipRow}>
            <View style={styles.chip}>
              <Text style={styles.chipText}>
                {presence?.is_online ? 'Online' : 'Awaiting heartbeat'}
              </Text>
            </View>
            <View style={styles.chip}>
              <Text style={styles.chipText}>
                Last GPS {formatDubaiTime(lastLocationSentAt)}
              </Text>
            </View>
          </View>
          <Text style={styles.caption}>
            {trackingNote || 'Heartbeat and GPS start only while the app is active and logged in.'}
          </Text>
          <Pressable
            style={[styles.secondaryButton, busy === 'logout' && styles.buttonDisabled]}
            onPress={() => void handleLogout()}
            disabled={busy === 'logout'}
          >
            <Text style={styles.secondaryButtonText}>
              {busy === 'logout' ? 'Logging out...' : 'Logout'}
            </Text>
          </Pressable>
        </View>

        {message ? <Text style={styles.successText}>{message}</Text> : null}
        {jobsError ? <Text style={styles.errorText}>{jobsError}</Text> : null}

        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Assigned jobs</Text>
          <Text style={styles.copy}>
            The mobile app reads the technician-scoped GET /jobs list and selected job detail.
          </Text>
          {jobsLoading ? (
            <ActivityIndicator size="small" color="#0f6b65" />
          ) : null}
          {!jobsLoading && jobs.length === 0 ? (
            <Text style={styles.emptyText}>No assigned jobs are visible right now.</Text>
          ) : null}
          {jobs.map((job) => (
            <Pressable
              key={job.id}
              style={[
                styles.jobCard,
                selectedJobId === job.id && styles.jobCardSelected,
              ]}
              onPress={() => setSelectedJobId(job.id)}
            >
              <View style={styles.rowBetween}>
                <View style={styles.jobTextWrap}>
                  <Text style={styles.jobTitle}>{job.title}</Text>
                  <Text style={styles.jobMeta}>
                    {job.city}, {job.country}
                  </Text>
                </View>
                <View style={styles.badgeColumn}>
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{job.status.replace('_', ' ')}</Text>
                  </View>
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{job.priority}</Text>
                  </View>
                </View>
              </View>
            </Pressable>
          ))}
        </View>

        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Selected job</Text>
          {jobDetailLoading ? (
            <ActivityIndicator size="small" color="#0f6b65" />
          ) : null}
          {!jobDetailLoading && jobDetailError ? (
            <Text style={styles.errorText}>{jobDetailError}</Text>
          ) : null}
          {!jobDetailLoading && !jobDetailError && !selectedJob ? (
            <Text style={styles.emptyText}>Choose a job to inspect details and activity.</Text>
          ) : null}
          {!jobDetailLoading && !jobDetailError && selectedJob ? (
            <>
              <View style={styles.jobDetailCard}>
                <Text style={styles.jobTitle}>{selectedJob.title}</Text>
                <Text style={styles.jobMeta}>
                  {selectedJob.address_line1}
                  {selectedJob.address_line2 ? `, ${selectedJob.address_line2}` : ''}
                  , {selectedJob.city}, {selectedJob.state}
                </Text>
                <Text style={styles.copy}>
                  Scheduled {formatDubaiTime(selectedJob.scheduled_start)} to{' '}
                  {formatDubaiTime(selectedJob.scheduled_end)}
                </Text>
                {selectedJob.technician_instructions ? (
                  <Text style={styles.copy}>
                    Instructions: {selectedJob.technician_instructions}
                  </Text>
                ) : null}
              </View>

              <View style={styles.actionRow}>
                <Pressable
                  style={[
                    styles.primaryButton,
                    (!canCheckIn || busy === 'check-in') && styles.buttonDisabled,
                  ]}
                  onPress={() => void handleCheckIn()}
                  disabled={!canCheckIn || busy === 'check-in'}
                >
                  <Text style={styles.primaryButtonText}>
                    {busy === 'check-in' ? 'Checking in...' : 'Check in'}
                  </Text>
                </Pressable>
                <Pressable
                  style={[
                    styles.secondaryButton,
                    (!canCheckOut || busy === 'check-out') && styles.buttonDisabled,
                  ]}
                  onPress={() => void handleCheckOut()}
                  disabled={!canCheckOut || busy === 'check-out'}
                >
                  <Text style={styles.secondaryButtonText}>
                    {busy === 'check-out' ? 'Checking out...' : 'Check out'}
                  </Text>
                </Pressable>
              </View>

              <View style={styles.composerCard}>
                <Text style={styles.sectionTitle}>New update</Text>
                <TextInput
                  style={[styles.input, styles.multilineInput]}
                  placeholder="Describe the work completed, parts used, or site notes"
                  placeholderTextColor="#6b746d"
                  multiline
                  value={updateMessage}
                  onChangeText={setUpdateMessage}
                />
                <View style={styles.actionRow}>
                  <Pressable style={styles.secondaryButton} onPress={() => void handlePickPhoto()}>
                    <Text style={styles.secondaryButtonText}>
                      {draftPhoto ? 'Change photo' : 'Attach photo'}
                    </Text>
                  </Pressable>
                  <Pressable
                    style={[
                      styles.primaryButton,
                      busy === 'submit-update' && styles.buttonDisabled,
                    ]}
                    onPress={() => void handleSubmitUpdate()}
                    disabled={busy === 'submit-update'}
                  >
                    <Text style={styles.primaryButtonText}>
                      {busy === 'submit-update' ? 'Submitting...' : 'Submit update'}
                    </Text>
                  </Pressable>
                </View>
                {draftPhoto ? (
                  <View style={styles.photoPreviewCard}>
                    <Image source={{ uri: draftPhoto.uri }} style={styles.photoPreview} />
                    <Text style={styles.caption}>{draftPhoto.name}</Text>
                  </View>
                ) : null}
              </View>

              <View style={styles.statsRow}>
                <View style={styles.statCard}>
                  <Text style={styles.statValue}>{jobEvents.length}</Text>
                  <Text style={styles.statLabel}>Events</Text>
                </View>
                <View style={styles.statCard}>
                  <Text style={styles.statValue}>{jobUpdates.length}</Text>
                  <Text style={styles.statLabel}>Updates</Text>
                </View>
                <View style={styles.statCard}>
                  <Text style={styles.statValue}>{selectedJobUpdatesCount}</Text>
                  <Text style={styles.statLabel}>Photos</Text>
                </View>
              </View>

              <Text style={styles.sectionTitle}>Recent activity</Text>
              {jobEvents.map((eventItem) => (
                <View key={`event-${eventItem.id}`} style={styles.timelineCard}>
                  <Text style={styles.timelineTitle}>
                    Event: {eventItem.event_type.replace('_', ' ')}
                  </Text>
                  <Text style={styles.timelineMeta}>
                    {formatDubaiTime(eventItem.occurred_at)}
                  </Text>
                </View>
              ))}
              {jobUpdates.map((update) => (
                <View key={`update-${update.id}`} style={styles.timelineCard}>
                  <Text style={styles.timelineTitle}>{update.message}</Text>
                  <Text style={styles.timelineMeta}>
                    {formatDubaiTime(update.created_at)} - {update.photos.length} photo(s)
                  </Text>
                </View>
              ))}
            </>
          ) : null}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#f5ecda',
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  authScroll: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 20,
  },
  screen: {
    padding: 18,
    gap: 16,
  },
  authCard: {
    backgroundColor: '#fffaf3',
    borderRadius: 24,
    padding: 22,
    gap: 14,
    borderWidth: 1,
    borderColor: 'rgba(29, 37, 32, 0.08)',
  },
  headerCard: {
    backgroundColor: '#fffaf3',
    borderRadius: 24,
    padding: 22,
    gap: 12,
    borderWidth: 1,
    borderColor: 'rgba(29, 37, 32, 0.08)',
  },
  sectionCard: {
    backgroundColor: '#fffdf8',
    borderRadius: 24,
    padding: 18,
    gap: 14,
    borderWidth: 1,
    borderColor: 'rgba(29, 37, 32, 0.08)',
  },
  composerCard: {
    backgroundColor: '#f6f0e3',
    borderRadius: 18,
    padding: 14,
    gap: 12,
  },
  jobDetailCard: {
    backgroundColor: '#f7f0e4',
    borderRadius: 18,
    padding: 14,
    gap: 8,
  },
  photoPreviewCard: {
    gap: 8,
  },
  photoPreview: {
    width: '100%',
    height: 180,
    borderRadius: 16,
  },
  eyebrow: {
    color: '#0f6b65',
    textTransform: 'uppercase',
    letterSpacing: 1.6,
    fontSize: 12,
    fontWeight: '700',
  },
  title: {
    fontSize: 28,
    lineHeight: 31,
    fontWeight: '800',
    color: '#1d2520',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1d2520',
  },
  copy: {
    color: '#576159',
    lineHeight: 21,
  },
  caption: {
    color: '#6b746d',
    fontSize: 12,
    lineHeight: 18,
  },
  input: {
    width: '100%',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(29, 37, 32, 0.12)',
    backgroundColor: '#ffffff',
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#1d2520',
  },
  multilineInput: {
    minHeight: 110,
    textAlignVertical: 'top',
  },
  primaryButton: {
    backgroundColor: '#0f6b65',
    borderRadius: 999,
    paddingHorizontal: 18,
    paddingVertical: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryButton: {
    backgroundColor: 'rgba(29, 37, 32, 0.08)',
    borderRadius: 999,
    paddingHorizontal: 18,
    paddingVertical: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: {
    opacity: 0.55,
  },
  primaryButtonText: {
    color: '#ffffff',
    fontWeight: '700',
  },
  secondaryButtonText: {
    color: '#1d2520',
    fontWeight: '700',
  },
  successText: {
    color: '#216748',
    fontWeight: '600',
  },
  errorText: {
    color: '#a5402d',
    lineHeight: 20,
  },
  emptyText: {
    color: '#6b746d',
    lineHeight: 20,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    borderRadius: 999,
    backgroundColor: 'rgba(29, 37, 32, 0.08)',
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipText: {
    color: '#1d2520',
    fontSize: 12,
    fontWeight: '600',
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  jobTextWrap: {
    flex: 1,
    gap: 4,
  },
  badgeColumn: {
    alignItems: 'flex-end',
    gap: 8,
  },
  badge: {
    borderRadius: 999,
    backgroundColor: 'rgba(15, 107, 101, 0.12)',
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  badgeText: {
    color: '#0f6b65',
    fontWeight: '700',
    fontSize: 12,
  },
  jobCard: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(29, 37, 32, 0.08)',
    backgroundColor: '#fffaf3',
    padding: 14,
  },
  jobCardSelected: {
    borderColor: 'rgba(15, 107, 101, 0.3)',
    backgroundColor: '#eef7f4',
  },
  jobTitle: {
    color: '#1d2520',
    fontSize: 17,
    fontWeight: '700',
  },
  jobMeta: {
    color: '#576159',
    lineHeight: 20,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  statsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  statCard: {
    flexGrow: 1,
    minWidth: 90,
    borderRadius: 16,
    backgroundColor: '#f6f0e3',
    padding: 12,
    gap: 4,
  },
  statValue: {
    fontSize: 24,
    fontWeight: '800',
    color: '#1d2520',
  },
  statLabel: {
    color: '#6b746d',
  },
  timelineCard: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: 'rgba(29, 37, 32, 0.08)',
    backgroundColor: '#fffaf3',
    padding: 14,
    gap: 6,
  },
  timelineTitle: {
    color: '#1d2520',
    fontWeight: '700',
    lineHeight: 21,
  },
  timelineMeta: {
    color: '#6b746d',
    lineHeight: 19,
  },
  loadingTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#1d2520',
  },
  loadingCopy: {
    color: '#576159',
    textAlign: 'center',
  },
});
