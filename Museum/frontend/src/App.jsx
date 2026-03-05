import { useState, useEffect, useCallback } from 'react'

const API = `${import.meta.env.BASE_URL}api`.replace('//', '/')

function formatMoney(n) {
  return `$${Number(n).toFixed(2)}`
}

function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>
}

function TypeBadge({ type }) {
  return <span className={`type-badge type-${type}`}>{type}</span>
}

// ─── Availability Panel ─────────────────────────────────────────────────────

function AvailabilityPanel({ selectedDate, onDateChange }) {
  const [slots, setSlots] = useState([])

  useEffect(() => {
    if (!selectedDate) return
    fetch(`${API}/availability?date=${selectedDate}`)
      .then((r) => r.ok ? r.json() : [])
      .then(setSlots)
      .catch(() => setSlots([]))
  }, [selectedDate])

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Availability</h2>
        <input
          type="date"
          className="date-input"
          value={selectedDate}
          onChange={(e) => onDateChange(e.target.value)}
        />
      </div>
      <div className="slots-grid">
        {slots.map((s) => (
          <div key={s.time_slot_id} className={`slot-card ${s.remaining_spots < 10 ? 'slot-low' : ''} ${s.remaining_spots === 0 ? 'slot-full' : ''}`}>
            <div className="slot-time">{s.label}</div>
            <div className="slot-spots">
              <span className="spot-count">{s.remaining_spots}</span>
              <span className="spot-label">/ {s.max_visitors} spots</span>
            </div>
            <div className="slot-bar">
              <div
                className="slot-bar-fill"
                style={{ width: `${((s.max_visitors - s.remaining_spots) / s.max_visitors) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ─── Tickets Panel ──────────────────────────────────────────────────────────

function TicketsPanel({ tickets, onRefresh }) {
  const cancel = async (id) => {
    if (!confirm('Cancel this ticket?')) return
    await fetch(`${API}/tickets/${id}`, { method: 'DELETE' })
    onRefresh()
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Tickets</h2>
        <button className="btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      {tickets.length === 0 ? (
        <p className="empty">No tickets yet. AI agents or humans can book below.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Date</th>
              <th>Time Slot</th>
              <th>Visitor</th>
              <th>Count</th>
              <th>Type</th>
              <th>Total</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id}>
                <td>#{t.id}</td>
                <td>{t.visit_date}</td>
                <td>{t.time_slot_label}</td>
                <td>
                  <div>{t.visitor_name}</div>
                  <small>{t.visitor_email}</small>
                </td>
                <td>{t.num_visitors}</td>
                <td><TypeBadge type={t.ticket_type} /></td>
                <td>{formatMoney(t.total_price)}</td>
                <td><StatusBadge status={t.status} /></td>
                <td>
                  {t.status === 'confirmed' && (
                    <button className="btn-cancel" onClick={() => cancel(t.id)}>Cancel</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

// ─── Quick Book Form ────────────────────────────────────────────────────────

function BookingForm({ timeSlots, onBooked }) {
  const today = new Date().toISOString().slice(0, 10)

  const [form, setForm] = useState({
    time_slot_id: '',
    visit_date: today,
    visitor_name: '',
    visitor_email: '',
    num_visitors: 2,
    ticket_type: 'adult',
  })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [pricing, setPricing] = useState(null)
  const [availability, setAvailability] = useState(null)

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setError(null)
  }

  useEffect(() => {
    const params = new URLSearchParams({
      ticket_type: form.ticket_type,
      visitors: String(form.num_visitors),
    })
    fetch(`${API}/pricing?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setPricing)
      .catch(() => setPricing(null))
  }, [form.ticket_type, form.num_visitors])

  useEffect(() => {
    if (!form.time_slot_id || !form.visit_date) {
      setAvailability(null)
      return
    }
    const params = new URLSearchParams({
      date: form.visit_date,
      time_slot_id: form.time_slot_id,
      visitors: String(form.num_visitors),
    })
    fetch(`${API}/availability?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setAvailability)
      .catch(() => setAvailability(null))
  }, [form.time_slot_id, form.visit_date, form.num_visitors])

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          time_slot_id: Number(form.time_slot_id),
          visit_date: form.visit_date,
          visitor_name: form.visitor_name,
          visitor_email: form.visitor_email,
          num_visitors: Number(form.num_visitors),
          ticket_type: form.ticket_type,
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Booking failed')
      }
      setForm((f) => ({ ...f, visitor_name: '', visitor_email: '', num_visitors: 2 }))
      setAvailability(null)
      onBooked()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel">
      <h2>Quick Book</h2>
      <form onSubmit={submit} className="book-form">
        <div className="form-row">
          <label>
            Visit Date
            <input type="date" value={form.visit_date} onChange={set('visit_date')} required />
          </label>
          <label>
            Time Slot
            <select value={form.time_slot_id} onChange={set('time_slot_id')} required>
              <option value="">Select a time slot</option>
              {timeSlots.map((s) => (
                <option key={s.id} value={s.id}>{s.label} (max {s.max_visitors})</option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-row">
          <label>
            Ticket Type
            <select value={form.ticket_type} onChange={set('ticket_type')}>
              <option value="adult">Adult — $25</option>
              <option value="child">Child — $12</option>
              <option value="senior">Senior — $18</option>
              <option value="student">Student — $15</option>
            </select>
          </label>
          <label>
            Visitors
            <input type="number" min="1" value={form.num_visitors} onChange={set('num_visitors')} required />
          </label>
        </div>

        {availability && (
          <div className={`availability-hint ${availability.available ? '' : 'availability-full'}`}>
            {availability.remaining_spots} of {availability.max_visitors} spots remaining for {availability.label}
            {!availability.available && ' — not enough spots!'}
          </div>
        )}

        <div className="form-row">
          <label>
            Visitor Name
            <input type="text" value={form.visitor_name} onChange={set('visitor_name')} required placeholder="Jane Smith" />
          </label>
          <label>
            Visitor Email
            <input type="email" value={form.visitor_email} onChange={set('visitor_email')} required placeholder="jane@example.com" />
          </label>
        </div>

        {pricing && (
          <div className="pricing-preview">
            {pricing.num_visitors} x {formatMoney(pricing.price_per_person)} ({pricing.ticket_type})
            = <strong>{formatMoney(pricing.total_price)}</strong>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Booking...' : 'Book Tickets'}
        </button>
      </form>
    </section>
  )
}

// ─── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const today = new Date().toISOString().slice(0, 10)
  const [selectedDate, setSelectedDate] = useState(today)
  const [tickets, setTickets] = useState([])
  const [timeSlots, setTimeSlots] = useState([])

  const fetchTickets = useCallback(() => {
    fetch(`${API}/tickets`).then((r) => r.json()).then(setTickets).catch(() => {})
  }, [])

  const fetchTimeSlots = useCallback(() => {
    fetch(`${API}/time-slots`).then((r) => r.json()).then(setTimeSlots).catch(() => {})
  }, [])

  useEffect(() => {
    fetchTickets()
    fetchTimeSlots()
    const interval = setInterval(fetchTickets, 30000)
    return () => clearInterval(interval)
  }, [fetchTickets, fetchTimeSlots])

  return (
    <div className="app">
      <header>
        <h1>Museum Ticket Dashboard</h1>
        <p className="subtitle">Monitor availability and tickets — auto-refreshes every 30s</p>
      </header>
      <main>
        <AvailabilityPanel selectedDate={selectedDate} onDateChange={setSelectedDate} />
        <TicketsPanel tickets={tickets} onRefresh={() => { fetchTickets(); setSelectedDate((d) => d) }} />
        <BookingForm timeSlots={timeSlots} onBooked={() => { fetchTickets(); setSelectedDate((d) => '' + d) }} />
      </main>
    </div>
  )
}
