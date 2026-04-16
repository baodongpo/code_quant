/**
 * components/PeriodSelector.jsx — 周期切换（1D/1W/1M）
 *
 * 美股周期控制：
 * - usStockSource === 'futu' 时，美股显示完整 1D/1W/1M
 * - 其他数据源（akshare 等）时，美股仅显示 1D
 */
import React from 'react'

const PERIODS = [
  { value: '1D', label: '日K' },
  { value: '1W', label: '周K' },
  { value: '1M', label: '月K' },
]

export default function PeriodSelector({ value, onChange, stockCode, usStockSource }) {
  const isUS = stockCode?.startsWith('US.')
  // 仅当美股且数据源不是 futu 时才隐藏周K/月K
  const periods = (isUS && usStockSource !== 'futu')
    ? PERIODS.filter(p => p.value === '1D')
    : PERIODS

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {periods.map(p => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          style={{
            padding:      '4px 12px',
            borderRadius: 6,
            border:       '1px solid',
            borderColor:  value === p.value ? '#388bfd' : '#30363d',
            background:   value === p.value ? '#1f3a5e' : '#1c2128',
            color:        value === p.value ? '#79c0ff' : '#8b949e',
            cursor:       'pointer',
            fontSize:     13,
            fontWeight:   value === p.value ? 600 : 400,
            transition:   'all 0.15s',
          }}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
