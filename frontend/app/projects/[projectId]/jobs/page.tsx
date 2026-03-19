"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { JobDetail, apiRequest } from "../../../lib/api";
import { getToken, getTrackedJobs, trackJob } from "../../../lib/auth";

export default function JobsPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [token, setToken] = useState<string | null>(null);
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [jobs, setJobs] = useState<JobDetail[]>([]);
  const [jobInput, setJobInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const sortedJobs = useMemo(
    () => [...jobs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [jobs]
  );

  useEffect(() => {
    const storedToken = getToken();
    setToken(storedToken);
    if (!storedToken) {
      setError("Please login first.");
      setLoading(false);
      return;
    }

    const ids = getTrackedJobs(projectId);
    setJobIds(ids);
  }, [projectId]);

  useEffect(() => {
    let active = true;
    const authToken = token;
    if (!authToken) {
      return;
    }

    async function refresh() {
      if (jobIds.length === 0) {
        setJobs([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const results = await Promise.all(
          jobIds.map(async (id) => {
            try {
              return await apiRequest<JobDetail>(`/jobs/${id}`, { token: authToken ?? undefined });
            } catch {
              return null;
            }
          })
        );

        if (!active) {
          return;
        }

        const ownedJobs = results.filter((job): job is JobDetail => Boolean(job && job.project_id === projectId));
        setJobs(ownedJobs);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to fetch jobs");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [token, jobIds, projectId]);

  function onTrackJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const jobId = jobInput.trim();
    if (!jobId) {
      return;
    }
    trackJob(projectId, jobId);
    const refreshed = getTrackedJobs(projectId);
    setJobIds(refreshed);
    setJobInput("");
  }

  return (
    <section className="stack">
      <div className="card">
        <h1>Jobs Table</h1>
        <p className="muted">Project: {projectId}</p>

        <form className="row gap wrap" onSubmit={onTrackJob}>
          <input
            className="inline-input"
            placeholder="Paste existing job id"
            value={jobInput}
            onChange={(e) => setJobInput(e.target.value)}
          />
          <button className="btn secondary" type="submit">
            Track Job ID
          </button>
          <Link href={`/projects/${projectId}/upload`} className="btn primary">
            New Upload
          </Link>
        </form>

        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="card">
        {loading ? (
          <p className="muted">Loading jobs...</p>
        ) : sortedJobs.length === 0 ? (
          <p className="muted">No tracked jobs yet. Upload an image first or add an existing job ID.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Status</th>
                  <th>Tree Count</th>
                  <th>Avg Confidence</th>
                  <th>Duration (ms)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sortedJobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <code>{job.id.slice(0, 8)}...</code>
                    </td>
                    <td>
                      <span className={`status status-${job.status}`}>{job.status}</span>
                    </td>
                    <td>{job.metrics?.tree_count ?? "-"}</td>
                    <td>{job.metrics?.avg_confidence?.toFixed(3) ?? "-"}</td>
                    <td>{job.metrics?.duration_ms ?? "-"}</td>
                    <td>
                      <Link href={`/jobs/${job.id}`} className="btn secondary small-btn">
                        Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
