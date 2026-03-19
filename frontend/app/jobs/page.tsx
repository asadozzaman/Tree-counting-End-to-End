import Link from "next/link";

export default function JobsIndexPage() {
  return (
    <section className="stack">
      <div className="card">
        <h1>Jobs</h1>
        <p className="muted">Open a project jobs table from your projects page.</p>
        <Link href="/projects" className="btn primary">
          Go to Projects
        </Link>
      </div>
    </section>
  );
}