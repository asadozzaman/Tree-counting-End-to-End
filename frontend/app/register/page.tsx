"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { getToken, setToken } from "../lib/auth";

type AuthResponse = { access_token: string; token_type: string };

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getToken()) {
      router.replace("/projects");
    }
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await apiRequest<AuthResponse>("/auth/register", {
        method: "POST",
        body: { email, password, full_name: fullName || null }
      });
      setToken(response.access_token);
      router.push("/projects");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="auth-wrap">
      <div className="card auth-card">
        <h1>Register</h1>
        <form onSubmit={onSubmit} className="stack">
          <label className="field">
            <span>Full Name</span>
            <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </label>

          <label className="field">
            <span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>

          <label className="field">
            <span>Password</span>
            <input type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>

          {error && <p className="error-text">{error}</p>}

          <button type="submit" className="btn primary" disabled={loading}>
            {loading ? "Creating account..." : "Create Account"}
          </button>
        </form>
        <p className="muted">
          Already have an account? <Link href="/login">Login</Link>
        </p>
      </div>
    </section>
  );
}