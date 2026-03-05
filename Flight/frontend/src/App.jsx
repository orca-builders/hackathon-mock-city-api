import { useState, useEffect, useCallback } from 'react'

const API = `${import.meta.env.BASE_URL}api`.replace('//', '/')

function formatMoney(n) {
  return `$${Number(n).toFixed(2)}`
}

function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>
}

function SeatClassBadge({ seatClass }) {
  return <span className={`class-badge class-${seatClass}`}>{seatClass}</span>
}

// ─── Flights Panel ──────────────────────────────────────────────────────────

function FlightsPanel({ flights }) {
  return (
    <section className="panel">
      <h2>Flights</h2>
      <table>
        <thead>
          <tr>
            <th>Flight</th>
            <th>Route</th>
            <th>Date</th>
            <th>Departure</th>
            <th>Arrival</th>
            <th>Seats</th>
            <th>Base Price</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {flights.map((f) => (
            <tr key={f.id}>
              <td className="mono">{f.flight_number}</td>
              <td>{f.origin} → {f.destination}</td>
              <td>{f.departure_date}</td>
              <td>{f.departure_time}</td>
              <td>{f.arrival_time}</td>
              <td>
                <span className={f.available_seats < 10 ? 'seats-low' : ''}>
                  {f.available_seats}
                </span>
                <small> / {f.total_seats}</small>
              </td>
              <td>{formatMoney(f.base_price)}</td>
              <td><StatusBadge status={f.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

// ─── Bookings Panel ─────────────────────────────────────────────────────────

function BookingsPanel({ bookings, onRefresh }) {
  const cancel = async (id) => {
    if (!confirm('Cancel this booking?')) return
    await fetch(`${API}/bookings/${id}`, { method: 'DELETE' })
    onRefresh()
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Bookings</h2>
        <button className="btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      {bookings.length === 0 ? (
        <p className="empty">No bookings yet. AI agents or humans can book below.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Flight</th>
              <th>Route</th>
              <th>Date</th>
              <th>Passenger</th>
              <th>Pax</th>
              <th>Class</th>
              <th>Total</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {bookings.map((b) => (
              <tr key={b.id}>
                <td>#{b.id}</td>
                <td className="mono">{b.flight_number}</td>
                <td>{b.origin} → {b.destination}</td>
                <td>{b.departure_date}</td>
                <td>
                  <div>{b.passenger_name}</div>
                  <small>{b.passenger_email}</small>
                </td>
                <td>{b.num_passengers}</td>
                <td><SeatClassBadge seatClass={b.seat_class} /></td>
                <td>{formatMoney(b.total_price)}</td>
                <td><StatusBadge status={b.status} /></td>
                <td>
                  {b.status === 'confirmed' && (
                    <button className="btn-cancel" onClick={() => cancel(b.id)}>Cancel</button>
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

function BookingForm({ flights, cities, onBooked }) {
  const [form, setForm] = useState({
    origin: '',
    destination: '',
    flight_id: '',
    passenger_name: '',
    passenger_email: '',
    num_passengers: 1,
    seat_class: 'economy',
  })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [pricing, setPricing] = useState(null)
  const [searchResults, setSearchResults] = useState(null)

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setError(null)
  }

  useEffect(() => {
    if (!form.origin || !form.destination) {
      setSearchResults(null)
      setForm((f) => ({ ...f, flight_id: '' }))
      return
    }
    const params = new URLSearchParams({
      origin: form.origin,
      destination: form.destination,
      ...(form.num_passengers > 0 ? { passengers: form.num_passengers } : {}),
    })
    fetch(`${API}/flights/search?${params}`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        setSearchResults(data)
        setForm((f) => ({ ...f, flight_id: '' }))
      })
      .catch(() => setSearchResults(null))
  }, [form.origin, form.destination, form.num_passengers])

  useEffect(() => {
    if (!form.flight_id) {
      setPricing(null)
      return
    }
    const params = new URLSearchParams({
      flight_id: form.flight_id,
      seat_class: form.seat_class,
      passengers: String(form.num_passengers),
    })
    fetch(`${API}/pricing?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setPricing)
      .catch(() => setPricing(null))
  }, [form.flight_id, form.seat_class, form.num_passengers])

  const flightOptions = searchResults !== null ? searchResults : flights

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          flight_id: Number(form.flight_id),
          passenger_name: form.passenger_name,
          passenger_email: form.passenger_email,
          num_passengers: Number(form.num_passengers),
          seat_class: form.seat_class,
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Booking failed')
      }
      setForm((f) => ({ ...f, passenger_name: '', passenger_email: '', num_passengers: 1 }))
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
            From
            <select value={form.origin} onChange={set('origin')} required>
              <option value="">Select origin</option>
              {cities.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            To
            <select value={form.destination} onChange={set('destination')} required>
              <option value="">Select destination</option>
              {cities.filter((c) => c !== form.origin).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            Passengers
            <input type="number" min="1" value={form.num_passengers} onChange={set('num_passengers')} required />
          </label>
        </div>

        {searchResults !== null && (
          <div className="availability-hint">
            {searchResults.length} flight{searchResults.length !== 1 ? 's' : ''} found {form.origin} → {form.destination}
          </div>
        )}

        <div className="form-row">
          <label>
            Flight
            <select value={form.flight_id} onChange={set('flight_id')} required>
              <option value="">Select a flight</option>
              {flightOptions.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.flight_number} — {f.departure_date} {f.departure_time}→{f.arrival_time} ({f.available_seats} seats) — {formatMoney(f.base_price)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Class
            <select value={form.seat_class} onChange={set('seat_class')}>
              <option value="economy">Economy (1x)</option>
              <option value="business">Business (2.5x)</option>
              <option value="first">First (5x)</option>
            </select>
          </label>
        </div>

        <div className="form-row">
          <label>
            Passenger Name
            <input type="text" value={form.passenger_name} onChange={set('passenger_name')} required placeholder="John Doe" />
          </label>
          <label>
            Passenger Email
            <input type="email" value={form.passenger_email} onChange={set('passenger_email')} required placeholder="john@example.com" />
          </label>
        </div>

        {pricing && (
          <div className="pricing-preview">
            {pricing.num_passengers} passenger{pricing.num_passengers !== 1 ? 's' : ''} ×{' '}
            {formatMoney(pricing.price_per_passenger)} ({pricing.seat_class}) = <strong>{formatMoney(pricing.total_price)}</strong>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Booking...' : 'Book Flight'}
        </button>
      </form>
    </section>
  )
}

// ─── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [flights, setFlights] = useState([])
  const [bookings, setBookings] = useState([])
  const [cities, setCities] = useState([])

  const fetchFlights = useCallback(() => {
    fetch(`${API}/flights`).then((r) => r.json()).then(setFlights).catch(() => {})
  }, [])

  const fetchBookings = useCallback(() => {
    fetch(`${API}/bookings`).then((r) => r.json()).then(setBookings).catch(() => {})
  }, [])

  const fetchCities = useCallback(() => {
    fetch(`${API}/destinations`)
      .then((r) => r.json())
      .then((data) => setCities(data.cities || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchFlights()
    fetchBookings()
    fetchCities()
    const interval = setInterval(() => {
      fetchFlights()
      fetchBookings()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchFlights, fetchBookings, fetchCities])

  return (
    <div className="app">
      <header>
        <h1>SkyMock Air — Flight Dashboard</h1>
        <p className="subtitle">Monitor flights and bookings — auto-refreshes every 30s</p>
      </header>
      <main>
        <FlightsPanel flights={flights} />
        <BookingsPanel bookings={bookings} onRefresh={() => { fetchBookings(); fetchFlights() }} />
        <BookingForm flights={flights} cities={cities} onBooked={() => { fetchBookings(); fetchFlights() }} />
      </main>
    </div>
  )
}
