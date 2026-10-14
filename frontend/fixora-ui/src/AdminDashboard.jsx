import { useEffect, useState } from "react";
import "./AdminDashboard.css";

const bookingMetrics = [
  { key: "total", label: "All bookings", tone: "green" },
  { key: "pending", label: "Pending", tone: "amber" },
  { key: "confirmed", label: "Confirmed", tone: "blue" },
  { key: "assigned", label: "Assigned", tone: "teal" },
  { key: "in_progress", label: "In progress", tone: "orange" },
  { key: "completed", label: "Completed", tone: "slate" },
];

const technicianMetrics = [
  { key: "total", label: "All technicians", tone: "green" },
  { key: "available", label: "Available", tone: "teal" },
  { key: "unavailable", label: "Unavailable", tone: "amber" },
];

const paymentMetrics = [
  { key: "total_collected", label: "Total collected", tone: "green", currency: true },
  { key: "pending_amount", label: "Pending amount", tone: "amber", currency: true },
  { key: "paid_invoices", label: "Paid invoices", tone: "blue" },
];

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function Breakdown({ title, rows, labelKey, emptyText }) {
  const largestCount = Math.max(...rows.map((row) => row.count), 0);

  return (
    <section className="dashboard-panel">
      <div className="dashboard-panel-heading">
        <div>
          <span className="dashboard-kicker">BOOKING MIX</span>
          <h2>{title}</h2>
        </div>
        <span className="panel-total">
          {rows.reduce((total, row) => total + row.count, 0)} total
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="dashboard-empty">{emptyText}</p>
      ) : (
        <div className="breakdown-list" role="img" aria-label={`${title} breakdown`}>
          {rows.map((row, index) => {
            const percentage = largestCount
              ? Math.max((row.count / largestCount) * 100, 3)
              : 0;
            return (
              <div className="breakdown-row" key={row[labelKey]}>
                <div className="breakdown-label">
                  <span>{row[labelKey]}</span>
                  <strong>{row.count}</strong>
                </div>
                <div className="breakdown-track" aria-hidden="true">
                  <span
                    className={`breakdown-bar breakdown-bar-${index % 5}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function MetricGroup({ title, metrics, values }) {
  return (
    <section className="metric-section" aria-label={title}>
      <div className="metric-section-heading">
        <h2>{title}</h2>
      </div>
      <div className="metric-grid">
        {metrics.map((metric) => (
          <article className={`metric-card metric-${metric.tone}`} key={metric.key}>
            <span>{metric.label}</span>
            <strong>{metric.currency ? formatCurrency(values[metric.key] ?? 0) : values[metric.key] ?? 0}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}

function AdminDashboard() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSummary() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/dashboard/summary/", {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
          signal: controller.signal,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const requestError = new Error(
            data.error || "Unable to load the dashboard."
          );
          requestError.status = response.status;
          throw requestError;
        }
        setSummary(data);
      } catch (requestError) {
        if (requestError.name !== "AbortError") {
          setError(requestError);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadSummary();
    return () => controller.abort();
  }, [refreshKey]);

  useEffect(() => {
    document.title = "Admin Dashboard | Fixora";
  }, []);

  if (loading && !summary) {
    return (
      <main className="admin-dashboard dashboard-state">
        <div className="dashboard-state-mark">F.</div>
        <h1>Loading dashboard</h1>
        <p>Checking your administrator session and retrieving service totals.</p>
        <div className="loading-line" aria-hidden="true" />
      </main>
    );
  }

  if (error?.status === 401 || error?.status === 403) {
    const isUnauthenticated = error.status === 401;
    return (
      <main className="admin-dashboard dashboard-state">
        <div className="dashboard-state-mark">F.</div>
        <span className="dashboard-kicker">FIXORA OPERATIONS</span>
        <h1>{isUnauthenticated ? "Administrator sign-in required" : "Dashboard access restricted"}</h1>
        <p>{error.message}</p>
        {isUnauthenticated ? (
          <a className="dashboard-primary-link" href="/admin/login/?next=/admin-dashboard">
            Sign in with Django Admin <span aria-hidden="true">↗</span>
          </a>
        ) : (
          <a className="dashboard-secondary-link" href="/admin/">
            Open Django Admin
          </a>
        )}
        <a className="dashboard-home-link" href="/">Return to Fixora home</a>
      </main>
    );
  }

  if (error) {
    return (
      <main className="admin-dashboard dashboard-state">
        <div className="dashboard-state-mark">F.</div>
        <span className="dashboard-kicker">FIXORA OPERATIONS</span>
        <h1>Dashboard unavailable</h1>
        <p role="alert">{error.message}</p>
        <button className="dashboard-primary-link" onClick={() => setRefreshKey((key) => key + 1)}>
          Try again
        </button>
        <a className="dashboard-home-link" href="/">Return to Fixora home</a>
      </main>
    );
  }

  const recentBookings = summary?.recent_bookings ?? [];

  return (
    <main className="admin-dashboard">
      <aside className="dashboard-sidebar">
        <a className="dashboard-brand" href="/" aria-label="Fixora home">
          <span className="dashboard-brand-mark">F</span>
          <span>fixora<span>.</span></span>
        </a>
        <div className="sidebar-caption">OPERATIONS</div>
        <nav className="dashboard-nav" aria-label="Admin navigation">
          <a className="dashboard-nav-link active" href="/admin-dashboard" aria-current="page">
            <span className="nav-symbol" aria-hidden="true">▦</span>Dashboard
          </a>
          <a className="dashboard-nav-link" href="/admin/bookings/booking/">
            <span className="nav-symbol" aria-hidden="true">▤</span>Bookings
          </a>
          <a className="dashboard-nav-link" href="/admin/bookings/technician/">
            <span className="nav-symbol" aria-hidden="true">⌁</span>Technicians
          </a>
          <a className="dashboard-nav-link" href="/admin/bookings/invoice/">
            <span className="nav-symbol" aria-hidden="true">▧</span>Invoices
          </a>
          <a className="dashboard-nav-link" href="/admin/bookings/payment/">
            <span className="nav-symbol" aria-hidden="true">₹</span>Payments
          </a>
        </nav>
        <div className="sidebar-bottom">
          <span className="sidebar-status-dot" /> Admin session protected
          <a href="/admin/">Django Admin ↗</a>
        </div>
      </aside>

      <div className="dashboard-content">
        <header className="dashboard-topbar">
          <div className="dashboard-breadcrumb">Fixora <span>/</span> Operations</div>
          <div className="dashboard-topbar-actions">
            <span className="session-indicator"><i /> Staff access</span>
            <button
              className="refresh-button"
              type="button"
              disabled={loading}
              onClick={() => setRefreshKey((key) => key + 1)}
            >
              {loading ? "Refreshing..." : "Refresh data"}
            </button>
          </div>
        </header>

        <div className="dashboard-main">
          <section className="dashboard-intro">
            <div>
              <span className="dashboard-kicker">SERVICE OVERVIEW</span>
              <h1>Good morning, operations.</h1>
              <p>A live view of bookings and technician availability.</p>
            </div>
            <a className="admin-console-link" href="/admin/">Open admin console <span aria-hidden="true">↗</span></a>
          </section>

          {loading && <p className="refresh-notice" role="status">Updating dashboard data…</p>}
          {error && <p className="refresh-error" role="alert">{error.message} <button onClick={() => setRefreshKey((key) => key + 1)}>Retry</button></p>}

          <MetricGroup title="Bookings" metrics={bookingMetrics} values={summary.bookings} />
          <MetricGroup title="Payments" metrics={paymentMetrics} values={summary.payments} />
          <MetricGroup title="Technicians" metrics={technicianMetrics} values={summary.technicians} />

          <div className="dashboard-analytics">
            <Breakdown
              title="Bookings by status"
              rows={summary.bookings_by_status}
              labelKey="status"
              emptyText="Status data will appear when the first booking is created."
            />
            <Breakdown
              title="Bookings by appliance"
              rows={summary.bookings_by_appliance}
              labelKey="appliance"
              emptyText="Appliance data will appear when the first booking is created."
            />
          </div>

          <section className="dashboard-panel recent-panel">
            <div className="dashboard-panel-heading">
              <div>
                <span className="dashboard-kicker">LATEST ACTIVITY</span>
                <h2>Recent bookings</h2>
              </div>
              <a href="/admin/bookings/booking/">Manage bookings <span aria-hidden="true">↗</span></a>
            </div>
            {recentBookings.length === 0 ? (
              <p className="dashboard-empty">No bookings yet. New service requests will appear here.</p>
            ) : (
              <div className="recent-table-wrap">
                <table className="recent-table">
                  <thead>
                    <tr>
                      <th scope="col">Reference</th>
                      <th scope="col">Appliance</th>
                      <th scope="col">Service</th>
                      <th scope="col">Date</th>
                      <th scope="col">Technician</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentBookings.map((booking) => (
                      <tr key={booking.id}>
                        <td className="reference-cell">{booking.reference}</td>
                        <td>{booking.appliance}</td>
                        <td>{booking.service}</td>
                        <td>{booking.preferred_date}</td>
                        <td>{booking.assigned_technician || "Unassigned"}</td>
                        <td><span className={`booking-status status-${booking.status.toLowerCase().replaceAll(" ", "-")}`}>{booking.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <footer className="dashboard-footer">Fixora operations <span>•</span> Booking data is visible to authorized staff only.</footer>
        </div>
      </div>
    </main>
  );
}

export default AdminDashboard;
