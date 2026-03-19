const TOKEN_KEY = "tree_saas_token";

export function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function projectJobKey(projectId: string): string {
  return `tree_project_jobs_${projectId}`;
}

export function getTrackedJobs(projectId: string): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  const raw = localStorage.getItem(projectJobKey(projectId));
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((id): id is string => typeof id === "string");
  } catch {
    return [];
  }
}

export function trackJob(projectId: string, jobId: string): void {
  const current = getTrackedJobs(projectId);
  if (current.includes(jobId)) {
    return;
  }
  const updated = [jobId, ...current].slice(0, 100);
  localStorage.setItem(projectJobKey(projectId), JSON.stringify(updated));
}