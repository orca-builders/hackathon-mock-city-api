import { useState, useEffect, useCallback } from 'react'

const API = `${import.meta.env.BASE_URL}api`.replace('//', '/')
const API_KEY = new URLSearchParams(window.location.search).get('api_key') || ''
const authHeaders = API_KEY ? { 'X-API-Key': API_KEY } : {}
const apiFetch = (url, opts = {}) => fetch(url, { ...opts, headers: { ...authHeaders, ...opts.headers } })

function formatMoney(n) {
  return `$${Number(n).toFixed(2)}`
}

function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>
}

function CategoryBadge({ category }) {
  return <span className={`cat-badge cat-${category}`}>{category}</span>
}

// ─── Fleet Panel ────────────────────────────────────────────────────────────

function FleetPanel({ vehicles }) {
  return (
    <section className="panel">
      <h2>Fleet</h2>
      <table>
        <thead>
          <tr>
            <th>Plate</th>
            <th>Vehicle</th>
            <th>Category</th>
            <th>Seats</th>
            <th>Daily Rate</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {vehicles.map((v) => (
            <tr key={v.id}>
              <td className="mono">{v.plate_number}</td>
              <td>{v.make} {v.model} <small>{v.year}</small></td>
              <td><CategoryBadge category={v.category} /></td>
              <td>{v.seats}</td>
              <td>{formatMoney(v.daily_rate)}/day</td>
              <td><StatusBadge status={v.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

// ─── Rentals Panel ──────────────────────────────────────────────────────────

function RentalsPanel({ rentals, onRefresh }) {
  const cancel = async (id) => {
    if (!confirm('Cancel this rental?')) return
    await apiFetch(`${API}/rentals/${id}`, { method: 'DELETE' })
    onRefresh()
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Rentals</h2>
        <button className="btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      {rentals.length === 0 ? (
        <p className="empty">No rentals yet. AI agents or humans can rent below.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Vehicle</th>
              <th>Category</th>
              <th>Customer</th>
              <th>Pickup</th>
              <th>Return</th>
              <th>Total</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rentals.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td>
                <td>
                  <div className="mono">{r.plate_number}</div>
                  <small>{r.make} {r.model}</small>
                </td>
                <td><CategoryBadge category={r.category} /></td>
                <td>
                  <div>{r.customer_name}</div>
                  <small>{r.customer_email}</small>
                </td>
                <td>{r.pickup_date}</td>
                <td>{r.return_date}</td>
                <td>{formatMoney(r.total_price)}</td>
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

// ─── Quick Rent Form ────────────────────────────────────────────────────────

function RentForm({ vehicles, categories, onRented }) {
  const today = new Date().toISOString().slice(0, 10)
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10)

  const [form, setForm] = useState({
    vehicle_id: '',
    customer_name: '',
    customer_email: '',
    pickup_date: today,
    return_date: tomorrow,
    category: '',
  })
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [pricing, setPricing] = useState(null)
  const [availableVehicles, setAvailableVehicles] = useState(null)

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setError(null)
  }

  useEffect(() => {
    if (!form.pickup_date || !form.return_date) {
      setAvailableVehicles(null)
      return
    }
    const params = new URLSearchParams({
      pickup_date: form.pickup_date,
      return_date: form.return_date,
      ...(form.category ? { category: form.category } : {}),
    })
    apiFetch(`${API}/vehicles/available?${params}`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        setAvailableVehicles(data)
        setForm((f) => ({ ...f, vehicle_id: '' }))
      })
      .catch(() => setAvailableVehicles(null))
  }, [form.pickup_date, form.return_date, form.category])

  useEffect(() => {
    if (!form.vehicle_id || !form.pickup_date || !form.return_date) {
      setPricing(null)
      return
    }
    const params = new URLSearchParams({
      vehicle_id: form.vehicle_id,
      pickup_date: form.pickup_date,
      return_date: form.return_date,
    })
    apiFetch(`${API}/pricing?${params}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setPricing)
      .catch(() => setPricing(null))
  }, [form.vehicle_id, form.pickup_date, form.return_date])

  const vehicleOptions = availableVehicles !== null ? availableVehicles : vehicles

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(`${API}/rentals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vehicle_id: Number(form.vehicle_id),
          customer_name: form.customer_name,
          customer_email: form.customer_email,
          pickup_date: form.pickup_date,
          return_date: form.return_date,
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Rental failed')
      }
      setForm((f) => ({ ...f, customer_name: '', customer_email: '', vehicle_id: '' }))
      setPricing(null)
      onRented()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel">
      <h2>Quick Rent</h2>
      <form onSubmit={submit} className="book-form">
        <div className="form-row">
          <label>
            Pickup Date
            <input type="date" value={form.pickup_date} onChange={set('pickup_date')} required />
          </label>
          <label>
            Return Date
            <input type="date" value={form.return_date} onChange={set('return_date')} required />
          </label>
          <label>
            Category
            <select value={form.category} onChange={set('category')}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.category} value={c.category}>
                  {c.category} ({formatMoney(c.min_daily_rate)}-{formatMoney(c.max_daily_rate)}/day)
                </option>
              ))}
            </select>
          </label>
        </div>

        {availableVehicles !== null && (
          <div className="availability-hint">
            {availableVehicles.length} vehicle{availableVehicles.length !== 1 ? 's' : ''} available
            {form.category ? ` in ${form.category}` : ''} for {form.pickup_date} to {form.return_date}
          </div>
        )}

        <div className="form-row">
          <label>
            Vehicle
            <select value={form.vehicle_id} onChange={set('vehicle_id')} required>
              <option value="">Select a vehicle</option>
              {vehicleOptions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.plate_number} — {v.make} {v.model} {v.year} ({v.category}, {v.seats} seats) — {formatMoney(v.daily_rate)}/day
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-row">
          <label>
            Customer Name
            <input type="text" value={form.customer_name} onChange={set('customer_name')} required placeholder="Jane Smith" />
          </label>
          <label>
            Customer Email
            <input type="email" value={form.customer_email} onChange={set('customer_email')} required placeholder="jane@example.com" />
          </label>
        </div>

        {pricing && (
          <div className="pricing-preview">
            {pricing.num_days} day{pricing.num_days !== 1 ? 's' : ''} x {formatMoney(pricing.daily_rate)}/day
            = <strong>{formatMoney(pricing.total_price)}</strong>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Renting...' : 'Rent Now'}
        </button>
      </form>
    </section>
  )
}

// ─── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [vehicles, setVehicles] = useState([])
  const [rentals, setRentals] = useState([])
  const [categories, setCategories] = useState([])

  const fetchVehicles = useCallback(() => {
    apiFetch(`${API}/vehicles`).then((r) => r.json()).then(setVehicles).catch(() => {})
  }, [])

  const fetchRentals = useCallback(() => {
    apiFetch(`${API}/rentals`).then((r) => r.json()).then(setRentals).catch(() => {})
  }, [])

  const fetchCategories = useCallback(() => {
    apiFetch(`${API}/categories`).then((r) => r.json()).then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    fetchVehicles()
    fetchRentals()
    fetchCategories()
    const interval = setInterval(() => {
      fetchVehicles()
      fetchRentals()
    }, 30000)
    return () => clearInterval(interval)
  }, [fetchVehicles, fetchRentals, fetchCategories])

  return (
    <div className="app">
      <header>
        <h1>Car Rental Dashboard</h1>
        <p className="subtitle">Monitor fleet and rentals — auto-refreshes every 30s</p>
      </header>
      <main>
        <FleetPanel vehicles={vehicles} />
        <RentalsPanel rentals={rentals} onRefresh={() => { fetchRentals(); fetchVehicles() }} />
        <RentForm vehicles={vehicles} categories={categories} onRented={() => { fetchRentals(); fetchVehicles() }} />
      </main>
    </div>
  )
}
