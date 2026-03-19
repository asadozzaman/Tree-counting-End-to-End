import Link from "next/link";

export default function ProjectLandingPage({ params }: { params: { projectId: string } }) {
  return (
    <section className="stack">
      <div className="card">
        <h1>Project Workspace</h1>
        <p className="muted">Project ID: {params.projectId}</p>
        <div className="row gap wrap">
          <Link href={`/projects/${params.projectId}/upload`} className="btn primary">
            Upload Image
          </Link>
          <Link href={`/projects/${params.projectId}/jobs`} className="btn secondary">
            Jobs Table
          </Link>
        </div>
      </div>
    </section>
  );
}