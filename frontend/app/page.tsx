"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getToken } from "./lib/auth";

export default function HomePage() {
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setHasToken(Boolean(getToken()));
  }, []);

  return (
    <section className="stack">
      <div className="card hero">
        <h1>Tree Counting Dashboard</h1>
        <p>
          Upload drone images, track inference jobs, and review tree detection metrics with downloadable CSV/JSON
          outputs.
        </p>
        <div className="row gap">
          <Link href={hasToken ? "/projects" : "/login"} className="btn primary">
            {hasToken ? "Open Projects" : "Login"}
          </Link>
          <Link href="/register" className="btn secondary">
            Create Account
          </Link>
        </div>
      </div>
    </section>
  );
}