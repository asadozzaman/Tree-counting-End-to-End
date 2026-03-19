"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { JobDetail, apiRequest, downloadArtifact, fetchImageBlobUrl } from "../../lib/api";
import { getToken } from "../../lib/auth";

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;

  const [token, setToken] = useState<string | null>(null);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  useEffect(() => {
    const storedToken = getToken();
    setToken(storedToken);

    async function load() {
      if (!storedToken) {
        setError("Please login first.");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const detail = await apiRequest<JobDetail>(`/jobs/${jobId}`, { token: storedToken });
        setJob(detail);

        if (detail.status === "done") {
          const blobUrl = await fetchImageBlobUrl(`/jobs/${jobId}/annotated-image`, storedToken);
          setImageUrl((prev) => {
            if (prev) {
              URL.revokeObjectURL(prev);
            }
            return blobUrl;
          });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job detail");
      } finally {
        setLoading(false);
      }
    }

    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [jobId]);

  async function onDownload(type: "csv" | "json") {
    if (!token) {
      setError("Please login first.");
      return;
    }
    setDownloading(type);
    setError(null);
    try {
      await downloadArtifact(`/jobs/${jobId}/download/${type}`, token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <section className="stack">
      <div className="card">
        <h1>Job Result Detail</h1>
        <p>
          Job ID: <code>{jobId}</code>
        </p>

        {loading ? (
          <p className="muted">Loading result...</p>
        ) : error ? (
          <p className="error-text">{error}</p>
        ) : job ? (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <span>Status</span>
                <strong className={`status status-${job.status}`}>{job.status}</strong>
              </div>
              <div className="stat-card">
                <span>Tree Count</span>
                <strong>{job.metrics?.tree_count ?? "-"}</strong>
              </div>
              <div className="stat-card">
                <span>Avg Confidence</span>
                <strong>{job.metrics?.avg_confidence?.toFixed(3) ?? "-"}</strong>
              </div>
              <div className="stat-card">
                <span>Duration (ms)</span>
                <strong>{job.metrics?.duration_ms ?? "-"}</strong>
              </div>
            </div>

            <div className="row gap wrap">
              <button className="btn secondary" onClick={() => onDownload("csv")} disabled={downloading !== null}>
                {downloading === "csv" ? "Downloading..." : "Download CSV"}
              </button>
              <button className="btn secondary" onClick={() => onDownload("json")} disabled={downloading !== null}>
                {downloading === "json" ? "Downloading..." : "Download JSON"}
              </button>
              <Link href={`/projects/${job.project_id}/jobs`} className="btn primary">
                Back to Jobs Table
              </Link>
            </div>

            {job.error_message && <p className="error-text">{job.error_message}</p>}
          </>
        ) : null}
      </div>

      <div className="card">
        <h2>Annotated Image</h2>
        {!job || job.status !== "done" ? (
          <p className="muted">Annotated image is available after job status becomes done.</p>
        ) : imageUrl ? (
          <img src={imageUrl} alt="Annotated detection result" className="annotated-image" />
        ) : (
          <p className="muted">Loading annotated image...</p>
        )}
      </div>
    </section>
  );
}