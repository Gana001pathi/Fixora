import "./InvoiceDocument.css";

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(Number(value));
}

function formatDate(value) {
  if (!value) return "Not specified";
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function InvoiceDocument({ invoice, onClose }) {
  const subtotal =
    Number(invoice.labour_charges) +
    Number(invoice.spare_parts_charges) +
    Number(invoice.additional_charges);

  return (
    <article className="invoice-document" aria-labelledby="invoice-title">
      <div className="invoice-toolbar">
        <span>Customer invoice</span>
        <div>
          <button type="button" className="invoice-print-button" onClick={() => window.print()}>
            <span aria-hidden="true">▣</span> Print invoice
          </button>
          <button type="button" className="invoice-close-button" onClick={onClose} aria-label="Close invoice">
            ×
          </button>
        </div>
      </div>

      <header className="invoice-heading">
        <a className="invoice-brand" href="/" aria-label="Fixora home">
          <span>F</span> fixora<span className="invoice-brand-dot">.</span>
        </a>
        <div className="invoice-heading-title">
          <span>PAYMENT RECORD</span>
          <h2 id="invoice-title">Service invoice</h2>
        </div>
      </header>

      <div className="invoice-reference-grid">
        <div><span>Invoice number</span><strong>{invoice.invoice_number}</strong></div>
        <div><span>Booking reference</span><strong>{invoice.booking_reference}</strong></div>
      </div>

      <div className="invoice-parties">
        <section>
          <span className="invoice-label">BILLED TO</span>
          <h3>{invoice.customer_name}</h3>
          <p>{invoice.customer_phone}</p>
          <address>{invoice.service_address}</address>
        </section>
        <section>
          <span className="invoice-label">SERVICE DETAILS</span>
          <dl>
            <div><dt>Appliance</dt><dd>{invoice.appliance}</dd></div>
            <div><dt>Service</dt><dd>{invoice.service}</dd></div>
            <div><dt>Service date</dt><dd>{formatDate(invoice.service_date)}</dd></div>
            <div><dt>Technician</dt><dd>{invoice.technician || "Not assigned"}</dd></div>
          </dl>
        </section>
      </div>

      <div className="invoice-table-wrap">
        <table className="invoice-table">
          <thead>
            <tr><th scope="col">Description</th><th scope="col">Amount</th></tr>
          </thead>
          <tbody>
            <tr><td>Labour charges</td><td>{formatCurrency(invoice.labour_charges)}</td></tr>
            <tr><td>Spare-parts charges</td><td>{formatCurrency(invoice.spare_parts_charges)}</td></tr>
            <tr><td>Additional charges</td><td>{formatCurrency(invoice.additional_charges)}</td></tr>
          </tbody>
          <tfoot>
            <tr><th scope="row">Subtotal</th><td>{formatCurrency(subtotal)}</td></tr>
            <tr className="invoice-discount"><th scope="row">Discount</th><td>−{formatCurrency(invoice.discount)}</td></tr>
            <tr className="invoice-total"><th scope="row">Total due</th><td>{formatCurrency(invoice.total_amount)}</td></tr>
          </tfoot>
        </table>
      </div>

      <section className="invoice-payment-summary" aria-label="Payment summary">
        <div>
          <span>Payment status</span>
          <strong className={`invoice-payment-status status-${invoice.payment_status.toLowerCase().replaceAll(" ", "-")}`}>
            {invoice.payment_status}
          </strong>
        </div>
        <div><span>Amount paid</span><strong>{formatCurrency(invoice.amount_paid)}</strong></div>
        <div><span>Balance due</span><strong>{formatCurrency(invoice.balance_due)}</strong></div>
      </section>

      {invoice.payments?.length > 0 && (
        <section className="invoice-payment-history" aria-labelledby="payment-history-title">
          <h3 id="payment-history-title">Payment history</h3>
          <div className="invoice-table-wrap">
            <table className="invoice-table">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Method / reference</th>
                  <th scope="col">Status</th>
                  <th scope="col">Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoice.payments.map((payment) => (
                  <tr key={payment.id}>
                    <td>{formatDate(payment.payment_date.slice(0, 10))}</td>
                    <td>{payment.payment_method}{payment.transaction_reference ? ` · ${payment.transaction_reference}` : ""}</td>
                    <td>{payment.status}</td>
                    <td>{formatCurrency(payment.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <footer className="invoice-footer">
        <span>Thank you for choosing Fixora.</span>
        <span>Issued {formatDate(invoice.created_at?.slice(0, 10))}</span>
      </footer>
    </article>
  );
}

export default InvoiceDocument;