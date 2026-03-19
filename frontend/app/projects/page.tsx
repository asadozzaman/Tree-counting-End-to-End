"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Project, apiRequest } from "../lib/api";
import { getToken } from "../lib/auth";

export default function ProjectsPage() {
  const router = useRouter();
  const [token, setAuthToken] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadProjects(authToken: string) {
    setLoading(true);
    setError(null);
    try {
      const rows = await apiRequest<Project[]>("/projects", { token: authToken });
      setProjects(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const storedToken = getToken();
    if (!storedToken) {
      router.replace("/login");
      return;
    }
    setAuthToken(storedToken);
    loadProjects(storedToken);
  }, [router]);

  async function onCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await apiRequest<Project>("/projects", {
        method: "POST",
        token,
        body: { name, description: description || null }
      });
      setName("");
      setDescription("");
      await loadProjects(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(projectId: string) {
    if (!token) {
      return;
    }

    setError(null);
    try {
      await apiRequest<{ deleted: boolean; id: string }>(`/projects/${projectId}`, { method: "DELETE", token });
      setProjects((current) => current.filter((project) => project.id !== projectId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete project");
    }
  }

  return (
    <section className="stack">
      <div className="card">
        <h1>Projects</h1>
        <p className="muted">Create a project, upload images, and track inference jobs.</p>

        <form onSubmit={onCreateProject} className="grid-form">
          <label className="field">
            <span>Project Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="field">
            <span>Description</span>
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <button type="submit" className="btn primary" disabled={saving}>
            {saving ? "Creating..." : "Create Project"}
          </button>
        </form>

        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="card">
        <div className="section-head">
          <h2>Project List</h2>
          <button className="btn secondary" type="button" onClick={() => token && loadProjects(token)} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {loading ? (
          <p className="muted">Loading projects...</p>
        ) : projects.length === 0 ? (
          <p className="muted">No projects yet.</p>
        ) : (
          <div className="cards-grid">
            {projects.map((project) => (
              <article key={project.id} className="project-card">
                <h3>{project.name}</h3>
                <p>{project.description || "No description"}</p>
                <p className="muted small">Created: {new Date(project.created_at).toLocaleString()}</p>
                <div className="row gap wrap">
                  <Link href={`/projects/${project.id}/upload`} className="btn secondary">
                    Upload
                  </Link>
                  <Link href={`/projects/${project.id}/jobs`} className="btn secondary">
                    Jobs
                  </Link>
                  <button type="button" className="btn danger" onClick={() => onDelete(project.id)}>
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}