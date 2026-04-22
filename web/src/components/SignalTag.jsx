/**
 * components/SignalTag.jsx — 通用信号标签组件
 *
 * Midnight Amber 主题：方形角 + 等宽字体 + 细边框
 */
import React from 'react'
import { getSignalLabel, getSignalColor } from '../utils/signals.js'
import { C } from '../utils/colors.js'

/**
 * @param {string} indicator  - 指标名称（BOLL/MACD/RSI/KDJ/MA/MAVOL/composite）
 * @param {string} signal     - 信号值（bullish/bearish/neutral/volume_high/volume_low）
 * @param {string} [override] - 覆盖标签文字（不传则自动从映射表取）
 */
export default function SignalTag({ indicator, signal, override }) {
  const colors = getSignalColor(signal)
  const label  = override || getSignalLabel(indicator, signal)
  const isNeutral = signal === 'neutral' || !signal

  return (
    <span style={{
      display:        'inline-flex',
      alignItems:     'center',
      justifyContent: 'center',
      padding:        '3px 8px',
      borderRadius:   '2px',
      fontSize:       '11px',
      fontFamily:     C.fontData,
      fontWeight:     500,
      letterSpacing:  '0.02em',
      minWidth:       '90px',
      textAlign:      'center',
      background:     colors.bg,
      border:         `1px solid ${colors.border}`,
      color:          colors.text,
      whiteSpace:     'nowrap',
      userSelect:     'none',
      opacity:        isNeutral ? 0.65 : 1,
    }}>
      {label}
    </span>
  )
}
