import { useState, useEffect, useCallback } from 'react'

const API = '/api'

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString()
}

function formatMoney(n) {
  return `$${Number(n).toFixed(2)}`
}

function StatusBadge({ status }) {
  return (
    <span className={`badge ${status}`}>
      {status}
    </span>
  )
}

// ─── Rooms Table ────────────────────────────────────────────────────────────

function RoomsPanel({ rooms }) {
  return (
    <section className="panel">
      <h2>Rooms</h2>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Type</th>
            <th>Capacity</th>
            <th>Base Price / Night</th>
          </tr>
        </thead>
        <tbody>
          {rooms.map((r) => (
            <tr key={r.id}>
              <td>{r.room_number}</td>
              <td className="capitalize">{r.room_type}</td>
              <td>{r.capacity} guest{r.capacity > 1 ? 's' : ''}</td>
              <td>{formatMoney(r.base_price_per_night)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

// ─── Reservations Table ─────────────────────────────────────────────────────

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
              <th>Room</th>
              <th>Guest</th>
              <th>Check-in</th>
              <th>Check-out</th>
              <th>Guests</th>
              <th>Total</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {reservations.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td>
                <td>{r.room_number}</td>
                <td>
                  <div>{r.guest_name}</div>
                  <small>{r.guest_email}</small>
                </td>
                <td>{formatDate(r.check_in)}</td>
                <td>{formatDate(r.check_out)}</td>
                <td>{r.num_guests}</td>
                <td>{formatMoney(r.total_price)}</td>
                <td><StatusBadge status={r.status} /></td>
                <td>
                  {r.status === 'confirmed' && (
                    <button className="btn-cancel" onClick={() => cancel(r.id)}>
                      Cancel
                    </button>
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

function BookingForm({ rooms, onBooked }) {
  const today = new Date().toISOString().slice(0, 10)
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10)

  const [form, setForm] = useState({
    room_id: '',
    guest_name: '',
    guest_email: '',
    check_in: today,
    check_out: tomorrow,
    num_guests: 1,
  })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [pricing, setPricing] = useState(null)

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setError(null)
  }

  useEffect(() => {
    if (!form.room_id || !form.check_in || !form.check_out) {
      setPricing(null)
      return
    }
    const params = new URLSearchParams({
      room_id: form.room_id,
      check_in: form.check_in,
      check_out: form.check_out,
    })
    fetch(`${API}/pricing?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setPricing)
      .catch(() => setPricing(null))
  }, [form.room_id, form.check_in, form.check_out])

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/reservations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, room_id: Number(form.room_id), num_guests: Number(form.num_guests) }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Booking failed')
      }
      setForm((f) => ({ ...f, guest_name: '', guest_email: '', num_guests: 1 }))
      setPricing(null)
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
            Room
            <select value={form.room_id} onChange={set('room_id')} required>
              <option value="">Select a room</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.room_number} — {r.room_type} ({r.capacity}p) — {formatMoney(r.base_price_per_night)}/n
                </option>
              ))}
            </select>
          </label>
          <label>
            Guests
            <input type="number" min="1" value={form.num_guests} onChange={set('num_guests')} required />
          </label>
        </div>
        <div className="form-row">
          <label>
            Check-in
            <input type="date" value={form.check_in} onChange={set('check_in')} required />
          </label>
          <label>
            Check-out
            <input type="date" value={form.check_out} onChange={set('check_out')} required />
          </label>
        </div>
        <div className="form-row">
          <label>
            Guest Name
            <input type="text" value={form.guest_name} onChange={set('guest_name')} required placeholder="John Doe" />
          </label>
          <label>
            Guest Email
            <input type="email" value={form.guest_email} onChange={set('guest_email')} required placeholder="john@example.com" />
          </label>
        </div>

        {pricing && (
          <div className="pricing-preview">
            {pricing.num_nights} night{pricing.num_nights !== 1 ? 's' : ''} — Total: <strong>{formatMoney(pricing.total_price)}</strong>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Booking...' : 'Book Now'}
        </button>
      </form>
    </section>
  )
}

// ─── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [rooms, setRooms] = useState([])
  const [reservations, setReservations] = useState([])

  const fetchRooms = useCallback(() => {
    fetch(`${API}/rooms`).then((r) => r.json()).then(setRooms).catch(() => {})
  }, [])

  const fetchReservations = useCallback(() => {
    fetch(`${API}/reservations`).then((r) => r.json()).then(setReservations).catch(() => {})
  }, [])

  useEffect(() => {
    fetchRooms()
    fetchReservations()
    const interval = setInterval(() => {
      fetchRooms()
      fetchReservations()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchRooms, fetchReservations])

  return (
    <div className="app">
      <header>
        <h1>Hotel Reservation Dashboard</h1>
        <p className="subtitle">Monitor rooms and reservations — auto-refreshes every 30s</p>
      </header>
      <main>
        <RoomsPanel rooms={rooms} />
        <ReservationsPanel reservations={reservations} onRefresh={fetchReservations} />
        <BookingForm rooms={rooms} onBooked={() => { fetchReservations(); fetchRooms() }} />
      </main>
    </div>
  )
}
