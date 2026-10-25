
import { useEffect, useState } from "react";
import "./App.css";
import InvoiceDocument from "./InvoiceDocument.jsx";
import { apiFetch } from "./api.js";

const appliances = [
  { icon: "❄️", name: "Air Conditioner", detail: "AC service & repair" },
  { icon: "🧊", name: "Refrigerator", detail: "Cooling & gas issues" },
  { icon: "🫧", name: "Washing Machine", detail: "Wash & spin problems" },
  { icon: "🔥", name: "Microwave", detail: "Heating & electrical" },
  { icon: "📺", name: "Television", detail: "Display & sound repair" },
  { icon: "⚡", name: "Other Appliances", detail: "Tell us what you need" },
];
const bookingServices = ["Repair", "Installation", "Maintenance"];

const services = [
  {
    icon: "🔧",
    title: "Appliance Repair",
    type: "Repair",
    description: "Expert troubleshooting and repairs for household appliances.",
  },
  {
    icon: "🧰",
    title: "Installation",
    type: "Installation",
    description: "Professional installation and setup at your home.",
  },
  {
    icon: "✨",
    title: "Maintenance",
    type: "Maintenance",
    description: "Routine servicing to keep your appliances running smoothly.",
  },
];

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function App() {
  const [form, setForm] = useState({
    name: "",
    phone: "",
    appliance: "Air Conditioner",
    service: "Repair",
    date: "",
    address: "",
    issue: "",
  });

  const [message, setMessage] = useState("");
const [showTracking, setShowTracking] = useState(false);
const [trackingReference, setTrackingReference] = useState("");
const [trackingPhone, setTrackingPhone] = useState("");
const [trackingResult, setTrackingResult] = useState(null);
const [trackingError, setTrackingError] = useState("");
const [isTracking, setIsTracking] = useState(false);
const [notifications, setNotifications] = useState([]);
const [notificationUnreadCount, setNotificationUnreadCount] = useState(0);
const [notificationCsrfToken, setNotificationCsrfToken] = useState("");
const [isLoadingNotifications, setIsLoadingNotifications] = useState(false);
const [notificationError, setNotificationError] = useState("");
const [updatingNotificationId, setUpdatingNotificationId] = useState(null);
const [servicePricing, setServicePricing] = useState([]);
const [pricingError, setPricingError] = useState("");
const [invoice, setInvoice] = useState(null);
const [isLoadingInvoice, setIsLoadingInvoice] = useState(false);
const [invoiceError, setInvoiceError] = useState("");

  const [isSubmitting, setIsSubmitting] = useState(false);
const [messageType, setMessageType] = useState("");

  useEffect(() => {
    let isMounted = true;
    apiFetch("/api/bookings/pricing/")
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "Unable to load service prices.");
        if (isMounted) setServicePricing(data.pricing || []);
      })
      .catch((error) => {
        if (isMounted) setPricingError(error.message || "Unable to load service prices.");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  function startingPrice(serviceType) {
    const prices = servicePricing
      .filter((item) => item.service === serviceType)
      .map((item) => Number(item.amount))
      .filter(Number.isFinite);
    return prices.length ? `From ${formatCurrency(Math.min(...prices))}` : "Price on request";
  }

  function updateForm(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
    setMessage("");
  }

  
async function handleBooking(event) {
  event.preventDefault();

  if (isSubmitting) return;

  setIsSubmitting(true);
  setMessage("");
  setMessageType("");

  try {
    const response = await apiFetch(
     "/api/bookings/",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: form.name.trim(),
          phone: form.phone,
          appliance: form.appliance,
          service: form.service,
          date: form.date,
          address: form.address.trim(),
          issue: form.issue.trim(),
        }),
      }
    );

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const details = Object.entries(data)
        .map(([field, errors]) => {
          const message = Array.isArray(errors)
            ? errors.join(", ")
            : typeof errors === "string"
              ? errors
              : JSON.stringify(errors);

          return `${field}: ${message}`;
        })
        .join(" | ");

      throw new Error(
        details || `Booking failed (${response.status}).`
      );
    }

    const bookingId =
      data.id ?? data.booking?.id ?? data.booking_id ?? "Confirmed";

    setMessage(
      `Thank you, ${form.name}! Your booking was saved successfully. Reference: FX-${bookingId}.`
    );
    setMessageType("success");

    setForm({
      name: "",
      phone: "",
      appliance: "Air Conditioner",
      service: "Repair",
      date: "",
      address: "",
      issue: "",
    });
  } catch (error) {
    setMessage(
      error instanceof TypeError
        ? "Could not connect to the server. Check that Django is running and CORS is configured."
        : error.message || "Unable to submit your booking."
    );
    setMessageType("error");
  } finally {
    setIsSubmitting(false);
  }
}

async function handleTrackBooking(event) {
  event.preventDefault();

  setTrackingError("");
  setTrackingResult(null);
  setInvoice(null);
  setInvoiceError("");
  setNotifications([]);
  setNotificationUnreadCount(0);
  setNotificationError("");
  setIsTracking(true);

  try {
    const reference = trackingReference.trim().toUpperCase();
    const match = reference.match(/^FX-(\d+)$/);

    if (!match) {
      setTrackingError("Enter a valid reference, such as FX-000006.");
      return;
    }

    const bookingId = Number(match[1]);

    const response = await apiFetch(
      `/api/bookings/track/?booking_id=${bookingId}&phone=${encodeURIComponent(trackingPhone.trim())}`
    );

    const data = await response.json();

    if (!response.ok) {
      setTrackingError(
        data.error || "Unable to find your booking."
      );
      return;
    }

    setTrackingResult(data);
    void loadCustomerNotifications(bookingId, trackingPhone.trim());
  } catch {
    setTrackingError("Cannot connect to the server. Please try again.");
  } finally {
    setIsTracking(false);
  }
}

async function loadCustomerInvoice() {
  const match = trackingResult?.reference.match(/^FX-(\d+)$/);
  if (!match) return;

  setIsLoadingInvoice(true);
  setInvoiceError("");
  setInvoice(null);
  try {
    const response = await apiFetch(
      `/api/bookings/invoices/customer/?reference=${encodeURIComponent(trackingResult.reference)}&phone=${encodeURIComponent(trackingPhone.trim())}`
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Unable to load this invoice.");
    setInvoice(data.invoice);
  } catch (error) {
    setInvoiceError(error.message || "Unable to load this invoice.");
  } finally {
    setIsLoadingInvoice(false);
  }
}

async function loadCustomerNotifications(bookingId, phone) {
  setIsLoadingNotifications(true);
  setNotificationError("");

  try {
    const response = await apiFetch(
      `/api/bookings/notifications/?booking_id=${bookingId}&phone=${encodeURIComponent(phone)}`,
    );
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.error || "Unable to load booking notifications.");
    }

    setNotifications(data.notifications || []);
    setNotificationUnreadCount(data.unread_count || 0);
    setNotificationCsrfToken(data.csrf_token || "");
  } catch (error) {
    setNotificationError(error.message || "Unable to load booking notifications.");
  } finally {
    setIsLoadingNotifications(false);
  }
}

async function markNotificationRead(notificationId) {
  const match = trackingResult?.reference.match(/^FX-(\d+)$/);
  if (!match || !notificationCsrfToken) {
    setNotificationError("Refresh your booking details before updating notifications.");
    return;
  }

  setUpdatingNotificationId(notificationId);
  setNotificationError("");

  try {
    const response = await apiFetch(
      `/api/bookings/notifications/${notificationId}/read/`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": notificationCsrfToken,
        },
        body: JSON.stringify({
          booking_id: Number(match[1]),
          phone: trackingPhone.trim(),
        }),
      }
    );
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.error || "Unable to update this notification.");
    }

    setNotifications((current) =>
      current.map((notification) =>
        notification.id === notificationId
          ? data.notification
          : notification
      )
    );
    setNotificationUnreadCount(data.unread_count || 0);
  } catch (error) {
    setNotificationError(error.message || "Unable to update this notification.");
  } finally {
    setUpdatingNotificationId(null);
  }
}

  return (
    <div className="site-shell">
      <div className="announcement">
        Reliable home appliance care, right at your doorstep.
        <a href="#booking"> Book a service ↗</a>
      </div>

      <header className="navbar">
        <a className="brand" href="#home" aria-label="Fixora home">
          <span className="brand-icon">F</span>
          <span>fixora<span className="brand-dot">.</span></span>
        </a>

        <nav className="nav-links" aria-label="Main navigation">
          <a href="#home">Home</a>
          <a href="#appliances">Appliances</a>
          <a href="#services">Our Services</a>
          <a href="#booking">Book a Repair</a>
          <a href="/technician-dashboard">Technician sign-in</a>
        </nav>

        <a className="nav-cta" href="#booking">
          Book a service <span>↗</span>
        </a>
      </header>

      <main>
        <section className="hero" id="home">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="eyebrow-dot" />
              YOUR HOME, IN GOOD HANDS
            </div>

            <h1>
              Home repairs,
              <br />
              <span>made simple.</span>
            </h1>

            <p className="hero-description">
              From a warm refrigerator to an AC that won't cool,
              get trusted appliance care without the hassle.
            </p>

            <div className="hero-actions">
              <a className="button button-primary" href="#booking">
                Book a repair <span>↗</span>
              </a>
              <a className="text-link" href="#services">
                Explore services <span>→</span>
              </a>
            </div>

            <div className="hero-trust">
              <div className="trust-avatars" aria-hidden="true">
                <span>R</span><span>K</span><span>A</span>
              </div>
              <div>
                <div className="trust-stars">★★★★★</div>
                <p>Here to make home care easier</p>
              </div>
            </div>
          </div>

          <div className="hero-visual">
            <div className="visual-orb orb-one" />
            <div className="visual-orb orb-two" />

            <div className="hero-image-card">
              <img
                src="https://images.unsplash.com/photo-1621905251918-48416bd8575a?auto=format&fit=crop&w=1000&q=85"
                alt="Professional technician working on a home repair"
              />
              <div className="image-label">
                <span className="label-check">✓</span>
                <div>
                  <strong>Care you can count on</strong>
                  <small>Service at your doorstep</small>
                </div>
              </div>
            </div>

            <div className="floating-card">
              <span className="floating-icon">🛠️</span>
              <div>
                <strong>One simple booking</strong>
                <small>Tell us what needs fixing</small>
              </div>
            </div>

            <div className="hero-number">
              <span>01</span>
              <span className="number-line" />
              <span>HOME CARE</span>
            </div>
          </div>
        </section>

        <section className="benefit-strip" aria-label="Service benefits">
          <div><span>✓</span> Convenient home service</div>
          <div><span>✓</span> Upfront service estimates</div>
          <div><span>✓</span> Simple online booking</div>
          <div><span>✓</span> Multiple appliance services</div>
        </section>

        <section className="section appliances-section" id="appliances">
          <div className="section-heading">
            <div>
              <span className="section-kicker">WHAT NEEDS FIXING?</span>
              <h2>We've got your home covered.</h2>
              <p>Choose an appliance to get started.</p>
            </div>
            <a className="section-link" href="#booking">
              Book a service <span>↗</span>
            </a>
          </div>

          <div className="appliance-grid">
            {appliances.map((item) => (
              <button
                className="appliance-card"
                key={item.name}
                onClick={() => {
                  setForm((previous) => ({
                    ...previous,
                    appliance: item.name,
                  }));
                  setMessage("");
                  document
                    .getElementById("booking")
                    .scrollIntoView({ behavior: "smooth" });
                }}
              >
                <span className="appliance-icon">{item.icon}</span>
                <strong>{item.name}</strong>
                <small>{item.detail}</small>
                <span className="card-arrow">↗</span>
              </button>
            ))}
          </div>

          <section className="service-pricing" aria-labelledby="pricing-heading">
            <div className="pricing-heading">
              <div>
                <span className="section-kicker">CURRENT SERVICE CHARGES</span>
                <h3 id="pricing-heading">Transparent starting prices.</h3>
              </div>
              <p>Final invoices include approved parts, additional charges, and any discount.</p>
            </div>
            {pricingError ? (
              <p className="pricing-message" role="alert">{pricingError}</p>
            ) : servicePricing.length === 0 ? (
              <p className="pricing-message">Service prices are being updated. Please check back soon.</p>
            ) : (
              <div className="pricing-table-wrap">
                <table className="pricing-table">
                  <thead>
                    <tr>
                      <th scope="col">Appliance</th>
                      {bookingServices.map((service) => (
                        <th scope="col" key={service}>{service}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {appliances.map((appliance) => (
                      <tr key={appliance.name}>
                        <th scope="row">{appliance.name}</th>
                        {bookingServices.map((service) => {
                          const price = servicePricing.find(
                            (item) => item.appliance === appliance.name && item.service === service
                          );
                          return <td key={service}>{price ? formatCurrency(price.amount) : "—"}</td>;
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </section>

        <section className="services-section" id="services">
          <div className="section services-inner">
            <div className="section-heading">
              <div>
                <span className="section-kicker">HOW WE CAN HELP</span>
                <h2>Good service. Less stress.</h2>
                <p>Choose the kind of help you need.</p>
              </div>
            </div>

            <div className="service-grid">
              {services.map((service) => (
                <article className="service-card" key={service.title}>
                  <span className="service-icon">{service.icon}</span>
                  <h3>{service.title}</h3>
                  <p>{service.description}</p>
                  <div className="service-card-bottom">
                    <strong>{startingPrice(service.type)}</strong>
                    <button
                      onClick={() => {
                        const serviceType =
                          service.title === "Installation"
                            ? "Installation"
                            : service.title === "Maintenance"
                              ? "Maintenance"
                              : "Repair";

                        setForm((previous) => ({
                          ...previous,
                          service: serviceType,
                        }));
                        setMessage("");
                        document
                          .getElementById("booking")
                          .scrollIntoView({ behavior: "smooth" });
                      }}
                      aria-label={`Book ${service.title}`}
                    >
                      →
                    </button>
                  </div>
                  <small className="price-note">
                    Indicative starting price; final cost may vary.
                  </small>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="booking-section" id="booking">
          <div className="booking-intro">
            <span className="section-kicker">LET'S GET IT FIXED</span>
            <h2>Your repair starts with a simple hello.</h2>
            <p>
              Share a few details. We'll use them to prepare your
              service request.
            </p>

            <div className="booking-note">
              <span>✳</span>
              <div>
                <strong>No complicated process.</strong>
                <p>Just tell us what needs attention and where you are.</p>
              </div>
            </div>

            <div className="booking-note">
              <span>⌂</span>
              <div>
                <strong>Home appliance care, made easier.</strong>
                <p>Choose your appliance and preferred service date.</p>
              </div>
            </div>
          </div>

          <form className="booking-form" onSubmit={handleBooking}>
            <div className="form-heading">
              <div>
                <span className="section-kicker">SERVICE REQUEST</span>
                <h3>Book your service</h3>
              </div>
              <span className="form-step">01 / 01</span>
            </div>

           {message && (
  <div
    className={`booking-message ${messageType}`}
    role={messageType === "error" ? "alert" : "status"}
  >
    {message}
  </div>
)}

            <div className="form-grid">
              <label>
                Full name *
                <input
                  name="name"
                  value={form.name}
                  onChange={updateForm}
                  placeholder="Enter your name"
                  autoComplete="name"
                  required
                />
              </label>

              <label>
                Phone number *
                <input
                  name="phone"
                  type="tel"
                  value={form.phone}
                 onChange={(event) => {
  const digits = event.target.value.replace(/\D/g, "").slice(0, 10);
  setForm((previous) => ({ ...previous, phone: digits }));
  setMessage("");
}}
                  placeholder="10-digit mobile number"
                  autoComplete="tel"
                  pattern="[6-9][0-9]{9}"
                  maxLength={10}
                  inputMode="numeric"
                  title="Enter a valid 10-digit Indian mobile number"
                  required
                />
              </label>

              <label>
                Appliance *
                <select
                  name="appliance"
                  value={form.appliance}
                  onChange={updateForm}
                  required
                >
                  {appliances.map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Service type *
                <select
                  name="service"
                  value={form.service}
                  onChange={updateForm}
                  required
                >
                  <option value="Repair">Repair</option>
                  <option value="Installation">Installation</option>
                  <option value="Maintenance">Maintenance</option>
                </select>
              </label>

              <label>
                Preferred date *
                <input
                  name="date"
                  type="date"
                  value={form.date}
                  onChange={updateForm}
                  min={new Date().toLocaleDateString("en-CA")}
                  required
                />
              </label>

              <label>
                Service address *
                <input
                  name="address"
                  value={form.address}
                  onChange={updateForm}
                  placeholder="Area, street or locality"
                  autoComplete="street-address"
                  required
                />
              </label>

              <label className="full-width">
                Describe the problem
                <textarea
                  name="issue"
                  value={form.issue}
                  onChange={updateForm}
                  placeholder="Tell us what happened (optional)"
                  rows="3"
                />
              </label>
            </div>

            <button
  className="button button-primary submit-button"
  type="submit"
  disabled={isSubmitting}
>
  {isSubmitting ? "Submitting..." : "Submit service request"}
  {!isSubmitting && <span> ↗</span>}
</button>

           <p className="form-disclaimer">
  Your request will be sent to the Fixora booking system.
</p>
          </form>
        </section>

        <section className="closing-banner">
          <div>
            <span className="section-kicker">A LITTLE HELP GOES A LONG WAY</span>
            <h2>Let's make home feel like home again.</h2>
          </div>
          <a className="button button-light" href="#booking">
            Get started <span>↗</span>
          </a>
        </section>
              <section className="tracking-section" id="track-booking">
        <h2>Track Your Booking</h2>
        <p>Enter your booking reference and registered mobile number.</p>

        <form onSubmit={handleTrackBooking} className="tracking-form">
          <input
            type="text"
            placeholder="Booking reference (e.g. FX-000006)"
            value={trackingReference}
            onChange={(event) => setTrackingReference(event.target.value)}
            required
          />

          <input
            type="tel"
            placeholder="Registered mobile number"
            value={trackingPhone}
            onChange={(event) => setTrackingPhone(event.target.value)}
            required
          />

          <button type="submit" disabled={isTracking}>
            {isTracking ? "Checking..." : "Track Booking"}
          </button>
        </form>

        {trackingError && (
          <p className="tracking-error" role="alert">{trackingError}</p>
        )}

        {trackingResult && (
          <div className="tracking-result">
            <h3>Booking Found: {trackingResult.reference}</h3>
            <p><strong>Appliance:</strong> {trackingResult.appliance}</p>
            <p><strong>Service:</strong> {trackingResult.service}</p>
            <p><strong>Service Date:</strong> {trackingResult.preferred_date}</p>
            <section className="customer-notifications" aria-labelledby="notifications-heading">
              <div className="notifications-heading">
                <div>
                  <span className="assigned-technician-label">BOOKING UPDATES</span>
                  <h4 id="notifications-heading">Notifications</h4>
                </div>
                <span className="notification-count" aria-live="polite">
                  {notificationUnreadCount} unread
                </span>
              </div>

              {isLoadingNotifications && (
                <p className="notification-status" role="status">
                  Loading notifications...
                </p>
              )}
              {notificationError && (
                <div className="notification-error" role="alert">
                  <span>{notificationError}</span>
                  <button
                    type="button"
                    onClick={() => {
                      const match = trackingResult.reference.match(/^FX-(\d+)$/);
                      if (match) {
                        void loadCustomerNotifications(Number(match[1]), trackingPhone.trim());
                      }
                    }}
                  >
                    Retry
                  </button>
                </div>
              )}
              {!isLoadingNotifications && !notificationError && notifications.length === 0 && (
                <p className="notification-status">
                  No updates yet. Booking changes will appear here.
                </p>
              )}
              {notifications.length > 0 && (
                <ul className="notification-list">
                  {notifications.map((notification) => (
                    <li
                      className={`notification-item ${notification.is_read ? "is-read" : "is-unread"}`}
                      key={notification.id}
                    >
                      <span className="notification-dot" aria-hidden="true" />
                      <div className="notification-copy">
                        <strong className="notification-type">{notification.type_label}</strong>
                        <p>{notification.message}</p>
                        <time dateTime={notification.created_at}>
                          {new Date(notification.created_at).toLocaleString()}
                        </time>
                      </div>
                      {notification.is_read ? (
                        <span className="notification-read-label">Read</span>
                      ) : (
                        <button
                          type="button"
                          className="notification-read-button"
                          disabled={updatingNotificationId === notification.id}
                          onClick={() => markNotificationRead(notification.id)}
                        >
                          {updatingNotificationId === notification.id ? "Saving..." : "Mark read"}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
            {trackingResult.technician ? (
              <div className="assigned-technician">
                <span className="assigned-technician-label">Assigned technician</span>
                <strong>{trackingResult.technician.full_name}</strong>
                <p>{trackingResult.technician.skills}</p>
                <small>Service area: {trackingResult.technician.service_area}</small>
              </div>
            ) : (
              <p className="technician-pending" role="status">
                Technician not assigned yet.
              </p>
            )}
           <div className="booking-timeline">
  <h4>Service Progress</h4>

  {[
    "Pending",
    "Confirmed",
    "Assigned",
    "In Progress",
    "Completed",
  ].map((step, index, steps) => {
    const statusOrder = {
      Pending: 0,
      Confirmed: 1,
      Assigned: 2,
      "In Progress": 3,
      Completed: 4,
    };

    const currentStep = statusOrder[trackingResult.status];

    return (
      <div
        key={step}
        className={`timeline-step ${
          currentStep !== undefined && index <= currentStep
            ? "timeline-step-done"
            : ""
        }`}
      >
        <span className="timeline-dot">
          {currentStep !== undefined && index <= currentStep ? "✓" : index + 1}
        </span>

        <span className="timeline-label">{step}</span>
      </div>
    );
  })}
</div>
<p>
  <strong>Current Status:</strong> {trackingResult.status}
</p>
{trackingResult.invoice_available && (
  <div className="customer-invoice-actions">
    <button type="button" onClick={loadCustomerInvoice} disabled={isLoadingInvoice}>
      {isLoadingInvoice ? "Loading invoice..." : "View invoice"}
      {!isLoadingInvoice && <span aria-hidden="true">↗</span>}
    </button>
    <p>Invoice access is verified with your registered mobile number.</p>
  </div>
)}
{invoiceError && <p className="tracking-error" role="alert">{invoiceError}</p>}
{invoice && <InvoiceDocument invoice={invoice} onClose={() => setInvoice(null)} />}
          </div>
        )}
      </section>
      </main>

      <footer className="footer">
        <a className="brand footer-brand" href="#home">
          <span className="brand-icon">F</span>
          <span>fixora<span className="brand-dot">.</span></span>
        </a>
        <p>Thoughtful appliance care for everyday living.</p>
        <div className="footer-links">
          <a href="#appliances">Appliances</a>
          <a href="#services">Services</a>
          <a href="#booking">Book a service</a>
        </div>
        <small>© {new Date().getFullYear()} Fixora. Demo website.</small>
      </footer>
    </div>
  );
}

export default App;
