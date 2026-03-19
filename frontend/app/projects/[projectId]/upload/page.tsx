"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { UploadResponse, apiRequest } from "../../../lib/api";
import { getToken, trackJob } from "../../../lib/auth";

export default function UploadPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [token, setToken] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [confThreshold, setConfThreshold] = useState("0.25");
  const [iouThreshold, setIouThreshold] = useState("0.45");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedJob, setUploadedJob] = useState<UploadResponse | null>(null);

  useEffect(() => {
    setToken(getToken());
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setError("Please login first.");
      return;
    }
    if (!file) {
      setError("Select an image file first.");
      return;
    }

    setLoading(true);
    setError(null);
    setUploadedJob(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("conf_threshold", confThreshold);
    formData.append("iou_threshold", iouThreshold);

    try {
      const response = await apiRequest<UploadResponse>(`/projects/${projectId}/upload`, {
        method: "POST",
        token,
        formData
      });
      setUploadedJob(response);
      trackJob(projectId, response.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="stack">
      <div className="card">
        <h1>Upload Image</h1>
        <p className="muted">Project: {projectId}</p>

        <form onSubmit={onSubmit} className="grid-form">
          <label className="field">
            <span>Image (JPG/PNG)</span>
            <input type="file" accept="image/png,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
          </label>

          <label className="field">
            <span>Confidence Threshold</span>
            <input type="number" min="0" max="1" step="0.01" value={confThreshold} onChange={(e) => setConfThreshold(e.target.value)} />
          </label>

          <label className="field">
            <span>IoU Threshold</span>
            <input type="number" min="0" max="1" step="0.01" value={iouThreshold} onChange={(e) => setIouThreshold(e.target.value)} />
          </label>

          <button className="btn primary" disabled={loading} type="submit">
            {loading ? "Uploading..." : "Upload and Queue Job"}
          </button>
        </form>

        {error && <p className="error-text">{error}</p>}
      </div>

      {uploadedJob && (
        <div className="card">
          <h2>Upload Complete</h2>
          <p>
            Job ID: <code>{uploadedJob.job_id}</code>
          </p>
          <div className="row gap wrap">
            <Link href={`/jobs/${uploadedJob.job_id}`} className="btn secondary">
              Open Result Page
            </Link>
            <Link href={`/projects/${projectId}/jobs`} className="btn secondary">
              Open Jobs Table
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}