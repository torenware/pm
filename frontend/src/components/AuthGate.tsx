"use client";

import { FormEvent, useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

type Session = {
  username: string;
};

export function AuthGate() {
  const [session, setSession] = useState<Session | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;

    void fetch("/api/session").then(async (response) => {
      if (!active) return;
      if (response.ok) {
        setSession((await response.json()) as Session);
      }
      setCheckingSession(false);
    });

    return () => {
      active = false;
    };
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: form.get("username"),
        password: form.get("password"),
      }),
    });

    if (response.ok) {
      setSession((await response.json()) as Session);
    } else {
      setError("Invalid username or password");
    }
    setSubmitting(false);
  }

  async function handleLogout() {
    await fetch("/api/logout", { method: "POST" });
    setSession(null);
  }

  if (checkingSession) {
    return (
      <main className="grid min-h-screen place-items-center" aria-busy="true">
        <p className="text-sm font-semibold text-[var(--gray-text)]">
          Opening your workspace...
        </p>
      </main>
    );
  }

  if (session) {
    return (
      <KanbanBoard
        username={session.username}
        onLogout={handleLogout}
        onSessionExpired={() => setSession(null)}
      />
    );
  }

  return (
    <main className="auth-layout min-h-screen">
      <section className="auth-intro">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--primary-blue)]">
          Single Board Kanban
        </p>
        <h1 className="mt-5 max-w-lg font-display text-5xl font-semibold leading-[1.05] text-[var(--navy-dark)] sm:text-6xl">
          Make the next move visible.
        </h1>
        <p className="mt-6 max-w-md text-base leading-7 text-[var(--gray-text)]">
          Sign in to return to your focused project workspace.
        </p>
        <div className="mt-10 h-1 w-20 bg-[var(--accent-yellow)]" />
      </section>

      <section className="auth-form-panel" aria-labelledby="sign-in-title">
        <div className="w-full max-w-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
            Kanban Studio
          </p>
          <h2
            id="sign-in-title"
            className="mt-3 font-display text-3xl font-semibold text-[var(--navy-dark)]"
          >
            Sign in
          </h2>

          <form className="mt-8 space-y-5" onSubmit={handleLogin}>
            <label className="block text-sm font-semibold text-[var(--navy-dark)]">
              Username
              <input
                className="auth-input mt-2"
                name="username"
                autoComplete="username"
                required
              />
            </label>
            <label className="block text-sm font-semibold text-[var(--navy-dark)]">
              Password
              <input
                className="auth-input mt-2"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            {error ? (
              <p role="alert" className="text-sm font-semibold text-red-700">
                {error}
              </p>
            ) : null}
            <button
              className="w-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[var(--navy-dark)] disabled:cursor-wait disabled:opacity-60"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}