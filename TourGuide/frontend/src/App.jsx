import { useState, useEffect, useCallback } from 'react'

const API = `${import.meta.env.BASE_URL}api`.replace('//', '/')

function formatMoney(n) {
  return `$${Number(n).toFixed(2)}`
}

function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>
}

function CategoryBadge({ category }) {
  return <span className={`cat-badge cat-${category}`}>{category}</span>
}

function DifficultyBadge({ difficulty }) {
  return <span className={`diff-badge diff-${difficulty}`}>{difficulty}</span>
}

// ─── Tours Catalog ──────────────────────────────────────────────────────────

function ToursCatalog({ tours }) {
  return (
    <section className="panel">
      <h2>Tours Catalog</h2>
      <table>
        <thead>
          <tr>
            <th>Tour</th>
            <th>Category</th>
            <th>Difficulty</th>
            <th>Duration</th>
            <th>Group Size</th>
            <th>Price / Person</th>
            <th>Location</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {tours.map((t) => (
            <tr key={t.id}>
              <td>
                <div className="tour-name">{t.name}</div>
                <small>{t.description.slice(0, 60)}...</small>
              </td>
              <td><CategoryBadge category={t.category} /></td>
              <td><DifficultyBadge difficulty={t.difficulty} /></td>
              <td>{t.duration_hours}h</td>
              <td>{t.max_group_size}</td>
              <td>{formatMoney(t.price_per_person)}</td>
              <td>{t.location}</td>
              <td><StatusBadge status={t.status} /></td>
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
              <th>Tour</th>
              <th>Category</th>
              <th>Date</th>
              <th>Guest</th>
              <th>Party</th>
              <th>Total</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {bookings.map((b) => (
              <tr key={b.id}>
                <td>#{b.id}</td>
                <td>{b.tour_name}</td>
                <td><CategoryBadge category={b.tour_category} /></td>
                <td>{b.tour_date}</td>
                <td>
                  <div>{b.guest_name}</div>
                  <small>{b.guest_email}</small>
                </td>
                <td>{b.num_guests}</td>
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

function BookingForm({ tours, categories, onBooked }) {
  const today = new Date().toISOString().slice(0, 10)

  const [form, setForm] = useState({
    tour_id: '',
    tour_date: today,
    guest_name: '',
    guest_email: '',
    num_guests: 2,
    category: '',
  })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [pricing, setPricing] = useState(null)
  const [availability, setAvailability] = useState(null)

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setError(null)
  }

  const filteredTours = form.category
    ? tours.filter((t) => t.category === form.category)
    : tours

  useEffect(() => {
    if (!form.tour_id) {
      setPricing(null)
      return
    }
    const params = new URLSearchParams({
      tour_id: form.tour_id,
      guests: String(form.num_guests),
    })
    fetch(`${API}/pricing?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setPricing)
      .catch(() => setPricing(null))
  }, [form.tour_id, form.num_guests])

  useEffect(() => {
    if (!form.tour_id || !form.tour_date) {
      setAvailability(null)
      return
    }
    const params = new URLSearchParams({
      tour_id: form.tour_id,
      date: form.tour_date,
      guests: String(form.num_guests),
    })
    fetch(`${API}/tours/available?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setAvailability)
      .catch(() => setAvailability(null))
  }, [form.tour_id, form.tour_date, form.num_guests])

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tour_id: Number(form.tour_id),
          tour_date: form.tour_date,
          guest_name: form.guest_name,
          guest_email: form.guest_email,
          num_guests: Number(form.num_guests),
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Booking failed')
      }
      setForm((f) => ({ ...f, guest_name: '', guest_email: '', num_guests: 2 }))
      setPricing(null)
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
            Category
            <select value={form.category} onChange={(e) => { set('category')(e); setForm((f) => ({ ...f, tour_id: '' })) }}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.category} value={c.category}>{c.category} ({c.tour_count})</option>
              ))}
            </select>
          </label>
          <label>
            Tour
            <select value={form.tour_id} onChange={set('tour_id')} required>
              <option value="">Select a tour</option>
              {filteredTours.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} — {t.difficulty} — {formatMoney(t.price_per_person)}/person
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-row">
          <label>
            Date
            <input type="date" value={form.tour_date} onChange={set('tour_date')} required />
          </label>
          <label>
            Guests
            <input type="number" min="1" value={form.num_guests} onChange={set('num_guests')} required />
          </label>
        </div>

        {availability && (
          <div className={`availability-hint ${availability.available ? '' : 'availability-full'}`}>
            {availability.remaining_spots} of {availability.max_group_size} spots remaining on {form.tour_date}
            {!availability.available && ' — not enough spots!'}
          </div>
        )}

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

        {pricing && (
          <div className="pricing-preview">
            {pricing.num_guests} guest{pricing.num_guests !== 1 ? 's' : ''} x {formatMoney(pricing.price_per_person)}/person
            = <strong>{formatMoney(pricing.total_price)}</strong>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Booking...' : 'Book Tour'}
        </button>
      </form>
    </section>
  )
}

// ─── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [tours, setTours] = useState([])
  const [bookings, setBookings] = useState([])
  const [categories, setCategories] = useState([])

  const fetchTours = useCallback(() => {
    fetch(`${API}/tours`).then((r) => r.json()).then(setTours).catch(() => {})
  }, [])

  const fetchBookings = useCallback(() => {
    fetch(`${API}/bookings`).then((r) => r.json()).then(setBookings).catch(() => {})
  }, [])

  const fetchCategories = useCallback(() => {
    fetch(`${API}/categories`).then((r) => r.json()).then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    fetchTours()
    fetchBookings()
    fetchCategories()
    const interval = setInterval(() => {
      fetchTours()
      fetchBookings()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchTours, fetchBookings, fetchCategories])

  return (
    <div className="app">
      <header>
        <h1>Tour Guide Dashboard</h1>
        <p className="subtitle">Monitor tours and bookings — auto-refreshes every 30s</p>
      </header>
      <main>
        <ToursCatalog tours={tours} />
        <BookingsPanel bookings={bookings} onRefresh={() => { fetchBookings(); fetchTours() }} />
        <BookingForm tours={tours} categories={categories} onBooked={() => { fetchBookings(); fetchTours() }} />
      </main>
    </div>
  )
}
