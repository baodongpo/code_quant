/**
 * components/StockSelector.jsx — 股票下拉选择
 */
import React from 'react'

const styles = {
  label:  { fontSize: 13, color: '#8b949e', marginRight: 6 },
  select: {
    background: '#1c2128', border: '1px solid #30363d', color: '#e6edf3',
    padding: '4px 8px', borderRadius: 6, fontSize: 13, cursor: 'pointer',
    minWidth: 180,
  },
}

export default function StockSelector({ stocks, value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <span style={styles.label}>股票</span>
      <select
        style={styles.select}
        value={value || ''}
        onChange={e => onChange(e.target.value)}
      >
        {stocks.map(s => (
          <option key={s.stock_code} value={s.stock_code}>
            {s.stock_code}
          </option>
        ))}
      </select>
    </div>
  )
}
