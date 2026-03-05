import { useState, useEffect, useCallback } from 'react'

const API = `${import.meta.env.BASE_URL}api`.replace('//', '/')

function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>
}

function LocationBadge({ location }) {
  return <span className={`loc-badge loc-${location}`}>{location}</span>
}

// ─── Tables Panel ───────────────────────────────────────────────────────────

function TablesPanel({ tables }) {
  return (
    <section className="panel">
      <h2>Tables</h2>
      <table>
        <thead>
          <tr>
            <th>Table</th>
            <th>Capacity</th>
            <th>Location</th>
          </tr>
        </thead>
        <tbody>
          {tables.map((t) => (
            <tr key={t.id}>
              <td>{t.table_number}</td>
              <td>{t.capacity} seat{t.capacity > 1 ? 's' : ''}</td>
              <td><LocationBadge location={t.location} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

// ─── Reservations Panel ─────────────────────────────────────────────────────

function ReservationsPanel({ reservations, onRefresh }) {
  const cancel = async (id) => {
    if (!confirm('Cancel this reservation?')) return
    await fetch(`${API}/reservations/${id}`, { method: 'DELETE' })
    onRefresh()
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Reservations</h2>
        <button className="btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      {reservations.length === 0 ? (
        <p className="empty">No reservations yet. AI agents or humans can book below.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Table</th>
              <th>Date</th>
              <th>Time</th>
              <th>Guest</th>
              <th>Party</th>
              <th>Requests</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {reservations.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td>
                <td>{r.table_number} <small>{r.location}</small></td>
                <td>{r.date}</td>
                <td>{r.time_slot}</td>
                <td>
                  <div>{r.guest_name}</div>
                  <small>{r.guest_email}</small>
                </td>
                <td>{r.party_size}</td>
                <td className="requests-cell">{r.special_requests || '—'}</td>
                <td><StatusBadge status={r.status} /></td>
                <td>
                  {r.status === 'confirmed' && (
                    <button className="btn-cancel" onClick={() => cancel(r.id)}>Cancel</button>
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

// ─── Booking Form ───────────────────────────────────────────────────────────

function BookingForm({ tables, timeSlots, onBooked }) {
  const today = new Date().toISOString().slice(0, 10)

  const [form, setForm] = useState({
    table_id: '',
    guest_name: '',
    guest_email: '',
    date: today,
    time_slot: '',
    party_size: 2,
    special_requests: '',
  })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [availableTables, setAvailableTables] = useState(null)

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setError(null)
  }

  useEffect(() => {
    if (!form.date || !form.time_slot) {
      setAvailableTables(null)
      return
    }
    const params = new URLSearchParams({
      date: form.date,
      time_slot: form.time_slot,
      ...(form.party_size ? { party_size: form.party_size } : {}),
    })
    fetch(`${API}/tables/available?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setAvailableTables)
      .catch(() => setAvailableTables(null))
  }, [form.date, form.time_slot, form.party_size])

  const tablesToShow = availableTables !== null ? availableTables : tables

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/reservations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...form,
          table_id: Number(form.table_id),
          party_size: Number(form.party_size),
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Booking failed')
      }
      setForm((f) => ({ ...f, guest_name: '', guest_email: '', party_size: 2, special_requests: '' }))
      setAvailableTables(null)
      onBooked()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel">
      <h2>Quick Reserve</h2>
      <form onSubmit={submit} className="book-form">
        <div className="form-row">
          <label>
            Date
            <input type="date" value={form.date} onChange={set('date')} required />
          </label>
          <label>
            Time Slot
            <select value={form.time_slot} onChange={set('time_slot')} required>
              <option value="">Select a time</option>
              {timeSlots.map((ts) => (
                <option key={ts} value={ts}>{ts}</option>
              ))}
            </select>
          </label>
          <label>
            Party Size
            <input type="number" min="1" value={form.party_size} onChange={set('party_size')} required />
          </label>
        </div>

        {availableTables !== null && (
          <div className="availability-hint">
            {availableTables.length} table{availableTables.length !== 1 ? 's' : ''} available for {form.date} at {form.time_slot}
          </div>
        )}

        <div className="form-row">
          <label>
            Table
            <select value={form.table_id} onChange={set('table_id')} required>
              <option value="">Select a table</option>
              {tablesToShow.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.table_number} — {t.location} ({t.capacity} seats)
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-row">
          <label>
            Guest Name
            <input type="text" value={form.guest_name} onChange={set('guest_name')} required placeholder="Jane Smith" />
          </label>
          <label>
            Guest Email
            <input type="email" value={form.guest_email} onChange={set('guest_email')} required placeholder="jane@example.com" />
          </label>
        </div>

        <div className="form-row">
          <label className="full-width">
            Special Requests
            <input type="text" value={form.special_requests} onChange={set('special_requests')} placeholder="Allergies, high chair, birthday..." />
          </label>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Reserving...' : 'Reserve Now'}
        </button>
      </form>
    </section>
  )
}

// ─── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [tables, setTables] = useState([])
  const [reservations, setReservations] = useState([])
  const [timeSlots, setTimeSlots] = useState([])

  const fetchTables = useCallback(() => {
    fetch(`${API}/tables`).then((r) => r.json()).then(setTables).catch(() => {})
  }, [])

  const fetchReservations = useCallback(() => {
    fetch(`${API}/reservations`).then((r) => r.json()).then(setReservations).catch(() => {})
  }, [])

  const fetchTimeSlots = useCallback(() => {
    fetch(`${API}/time-slots`)
      .then((r) => r.json())
      .then((data) => setTimeSlots(data.time_slots || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchTables()
    fetchReservations()
    fetchTimeSlots()
    const interval = setInterval(() => {
      fetchTables()
      fetchReservations()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchTables, fetchReservations, fetchTimeSlots])

  return (
    <div className="app">
      <header>
        <h1>Restaurant Reservation Dashboard</h1>
        <p className="subtitle">Monitor tables and reservations — auto-refreshes every 30s</p>
      </header>
      <main>
        <TablesPanel tables={tables} />
        <ReservationsPanel reservations={reservations} onRefresh={fetchReservations} />
        <BookingForm tables={tables} timeSlots={timeSlots} onBooked={() => { fetchReservations(); fetchTables() }} />
      </main>
    </div>
  )
}
