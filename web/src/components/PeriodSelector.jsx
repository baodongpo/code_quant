/**
 * components/PeriodSelector.jsx — 周期切换（1D/1W/1M）
 *
 * Midnight Amber 主题：方角按钮、等宽字体、琥珀 accent
 *
 * 美股周期控制：
 * - usStockSource === 'futu' 或未加载（null/undefined/空）时，美股显示完整 1D/1W/1M
 * - 明确配置为其他数据源（akshare 等）时，美股仅显示 1D
 *
 * 注意：usStockSource 初始为 null（/api/health 未返回），此时不应屏蔽周K/月K，
 * 等价于 futu（后端默认值）。只有明确拿到非 futu 值时才降级。
 */
import React from 'react'
import { C } from '../utils/colors.js'

const PERIODS = [
  { value: '1D', label: '1D' },
  { value: '1W', label: '1W' },
  { value: '1M', label: '1M' },
]

export default function PeriodSelector({ value, onChange, stockCode, usStockSource }) {
  const isUS = stockCode?.startsWith('US.')
  const isNonFutu = usStockSource != null && usStockSource !== '' && usStockSource !== 'futu'
  const periods = (isUS && isNonFutu)
    ? PERIODS.filter(p => p.value === '1D')
    : PERIODS

  return (
    <div style={{ display: 'flex', gap: 2 }}>
      {periods.map(p => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          style={{
            padding:       '4px 12px',
            borderRadius:  2,
            border:        '1px solid',
            borderColor:   value === p.value ? C.accent : C.border2,
            background:    value === p.value ? C.accentBg : 'transparent',
            color:         value === p.value ? C.accentText : C.textDim,
            cursor:        'pointer',
            fontSize:      11,
            fontFamily:    C.fontData,
            fontWeight:    value === p.value ? 700 : 400,
            letterSpacing: '0.08em',
            transition:    'all 0.12s',
          }}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
