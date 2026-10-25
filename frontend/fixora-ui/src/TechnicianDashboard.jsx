import { useEffect, useState } from "react";
import "./TechnicianDashboard.css";
import { apiFetch } from "./api.js";

const sessionUrl = "/api/bookings/technician/session/";
const todayLabel = new Date().toLocaleDateString(undefined, {
  weekday: "long",
  day: "numeric",
  month: "long",
});

async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || "The request could not be completed.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function formatDate(value) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function TechnicianDashboard() {
  const [technician, setTechnician] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [csrfToken, setCsrfToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyJobId, setBusyJobId] = useState(null);
  const [error, setError] = useState("");
  const [accountNeedsLink, setAccountNeedsLink] = useState(false);
  const [filter, setFilter] = useState("Active");

  useEffect(() => {
    let isMounted = true;
    apiFetch(sessionUrl)
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!isMounted) return;
        setCsrfToken(data.csrf_token || "");
        if (response.ok) {
          setTechnician(data.technician);
          setJobs(data.jobs || []);
        } else if (response.status !== 401) {
          setError(data.error || "This account cannot access the technician dashboard.");
          setAccountNeedsLink(response.status === 403);
        }
      })
      .catch(() => {
        if (isMounted) setError("Unable to reach Fixora. Check that Django is running.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleLogin(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setAccountNeedsLink(false);
    try {
      const response = await apiFetch("/api/bookings/technician/login/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await readResponse(response);
      setTechnician(data.technician);
      setJobs(data.jobs || []);
      setCsrfToken(data.csrf_token || csrfToken);
      setAccountNeedsLink(false);
      setPassword("");
    } catch (requestError) {
      setError(requestError.message || "Unable to sign in.");
      setAccountNeedsLink(requestError.status === 403);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLogout() {
    setSubmitting(true);
    setError("");
    try {
      await readResponse(await apiFetch("/api/bookings/technician/logout/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
      }));
      setTechnician(null);
      setJobs([]);
    } catch (requestError) {
      setError(requestError.message || "Unable to sign out.");
    } finally {
      setSubmitting(false);
    }
  }

  async function updateStatus(job) {
    const nextStatus = job.status === "In Progress" ? "Completed" : "In Progress";
    setBusyJobId(job.id);
    setError("");
    try {
      const response = await apiFetch(`/api/bookings/technician/jobs/${job.id}/status/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ status: nextStatus }),
      });
      const data = await readResponse(response);
      setJobs((current) => current.map((item) => item.id === job.id ? data.job : item));
    } catch (requestError) {
      setError(requestError.message || "Unable to update this job.");
    } finally {
      setBusyJobId(null);
    }
  }

  const activeCount = jobs.filter((job) => job.status !== "Completed").length;
  const inProgressCount = jobs.filter((job) => job.status === "In Progress").length;
  const completedCount = jobs.filter((job) => job.status === "Completed").length;
  const visibleJobs = jobs.filter((job) => {
    if (filter === "Active") return job.status !== "Completed";
    if (filter === "Completed") return job.status === "Completed";
    return true;
  });

  useEffect(() => {
    document.title = "Technician Dashboard | Fixora";
  }, []);

  return (
    <main className="technician-dashboard">
      <header className="tech-topbar">
        <a className="tech-brand" href="/" aria-label="Fixora home">
          <span className="tech-brand-mark">F</span>
          <span>fixora<span>.</span></span>
        </a>
        <div className="tech-topbar-right">
          <span className="tech-session-state"><i /> Technician workspace</span>
          {technician && (
            <button className="tech-logout" type="button" onClick={handleLogout} disabled={submitting}>
              Sign out
            </button>
          )}
        </div>
      </header>

      {loading ? (
        <section className="tech-state">
          <span className="tech-kicker">FIXORA FIELD SERVICE</span>
          <h1>Opening your workspace</h1>
          <div className="tech-loading-bar" />
        </section>
      ) : technician ? (
        <div className="tech-main">
          <section className="tech-welcome">
            <div>
              <span className="tech-kicker">FIELD SERVICE / MY WORK</span>
              <h1>Good day, {technician.full_name.split(" ")[0]}.</h1>
              <p>Here are the service visits assigned to you.</p>
            </div>
            <div className="tech-work-date">
              <span>Today</span>
              <strong>{todayLabel}</strong>
            </div>
          </section>

          <section className="tech-metrics" aria-label="Job totals">
            <article><span>Active jobs</span><strong>{activeCount}</strong><i className="metric-green" /></article>
            <article><span>In progress</span><strong>{inProgressCount}</strong><i className="metric-amber" /></article>
            <article><span>Completed</span><strong>{completedCount}</strong><i className="metric-blue" /></article>
          </section>

          <section className="tech-jobs-section">
            <div className="tech-jobs-heading">
              <div>
                <span className="tech-kicker">ASSIGNED TO YOU</span>
                <h2>Service jobs <span>{jobs.length}</span></h2>
              </div>
              <div className="tech-filter" role="group" aria-label="Filter jobs">
                {["Active", "All", "Completed"].map((option) => (
                  <button
                    type="button"
                    key={option}
                    className={filter === option ? "selected" : ""}
                    aria-pressed={filter === option}
                    onClick={() => setFilter(option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>

            {error && <div className="tech-error" role="alert">{error}</div>}
            {visibleJobs.length === 0 ? (
              <div className="tech-empty">
                <span aria-hidden="true">✓</span>
                <h3>{jobs.length === 0 ? "No jobs assigned" : "Nothing in this view"}</h3>
                <p>{jobs.length === 0 ? "New assignments will appear here." : "Choose another filter to see your jobs."}</p>
              </div>
            ) : (
              <div className="tech-job-list">
                {visibleJobs.map((job) => {
                  const isCompleted = job.status === "Completed";
                  const buttonLabel = job.status === "In Progress" ? "Complete job" : "Start job";
                  return (
                    <article className="tech-job" key={job.id}>
                      <div className="tech-job-head">
                        <div>
                          <span className="tech-job-ref">{job.reference}</span>
                          <h3>{job.customer_name}</h3>
                        </div>
                        <span className={`tech-status status-${job.status.toLowerCase().replaceAll(" ", "-")}`}>
                          {job.status}
                        </span>
                      </div>
                      <dl className="tech-job-details">
                        <div><dt>Appliance</dt><dd>{job.appliance}</dd></div>
                        <div><dt>Service</dt><dd>{job.service}</dd></div>
                        <div><dt>Preferred date</dt><dd>{formatDate(job.preferred_date)}</dd></div>
                        <div className="tech-address"><dt>Service address</dt><dd>{job.address}</dd></div>
                      </dl>
                      <div className="tech-job-actions">
                        {isCompleted ? (
                          <span className="tech-complete-label">Visit completed</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => updateStatus(job)}
                            disabled={busyJobId === job.id}
                          >
                            {busyJobId === job.id ? "Saving..." : buttonLabel}
                            <span aria-hidden="true">↗</span>
                          </button>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
          <footer className="tech-footer"><a href="/">← Fixora home</a><span>Secure technician access</span></footer>
        </div>
      ) : (
        <section className="tech-login-layout">
          <div className="tech-login-intro">
            <span className="tech-kicker">FIXORA FIELD SERVICE</span>
            <h1>Your workday,<br /><em>in one place.</em></h1>
            <p>Sign in to view your assigned service visits and keep customers up to date.</p>
            <div className="tech-login-rule"><span /> JOBS · ROUTES · SERVICE</div>
          </div>
          <form className="tech-login-form" onSubmit={handleLogin}>
            <span className="tech-kicker">TECHNICIAN ACCESS</span>
            <h2>Sign in</h2>
            <p>Use the account linked to your technician profile.</p>
            {error && <div className="tech-error" role="alert">{error}</div>}
            {accountNeedsLink && (
              <p className="tech-link-help">
                Ask an administrator to link this Django user to the correct technician record, then sign in again.
                <a href="/admin/bookings/technician/"> Open technician records ↗</a>
              </p>
            )}
            <label htmlFor="tech-username">Username</label>
            <input
              id="tech-username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
            <label htmlFor="tech-password">Password</label>
            <input
              id="tech-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <button type="submit" disabled={submitting || !csrfToken}>
              {submitting ? "Signing in..." : "Open my dashboard"}<span aria-hidden="true">↗</span>
            </button>
            <a className="tech-home-link" href="/">Return to Fixora home</a>
          </form>
        </section>
      )}
    </main>
  );
}

export default TechnicianDashboard;