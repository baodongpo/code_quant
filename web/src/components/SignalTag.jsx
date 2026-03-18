/**
 * components/SignalTag.jsx — 通用信号标签组件
 */
import React from 'react'
import { getSignalLabel, getSignalColor } from '../utils/signals.js'

/**
 * @param {string} indicator  - 指标名称（BOLL/MACD/RSI/KDJ/MA/MAVOL/composite）
 * @param {string} signal     - 信号值（bullish/bearish/neutral/volume_high/volume_low）
 * @param {string} [override] - 覆盖标签文字（不传则自动从映射表取）
 */
export default function SignalTag({ indicator, signal, override }) {
  const colors = getSignalColor(signal)
  const label  = override || getSignalLabel(indicator, signal)

  return (
    <span style={{
      display:        'inline-flex',
      alignItems:     'center',
      padding:        '2px 8px',
      borderRadius:   '12px',
      fontSize:       '12px',
      fontWeight:     600,
      background:     colors.bg,
      border:         `1px solid ${colors.border}`,
      color:          colors.text,
      whiteSpace:     'nowrap',
      userSelect:     'none',
    }}>
      {label}
    </span>
  )
}
