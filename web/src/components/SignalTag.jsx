/**
 * components/SignalTag.jsx — 通用信号标签组件
 *
 * v3.5 更新：字号 13px，圆角 6px，内边距 5px 10px，最小宽度 100px
 * 中性状态透明度降低，减少视觉干扰
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
  const isNeutral = signal === 'neutral' || !signal

  return (
    <span style={{
      display:        'inline-flex',
      alignItems:     'center',
      justifyContent: 'center',
      padding:        '5px 10px',
      borderRadius:   '6px',
      fontSize:       '13px',
      fontWeight:     600,
      minWidth:       '100px',
      textAlign:      'center',
      background:     colors.bg,
      border:         `1px solid ${colors.border}`,
      color:          colors.text,
      whiteSpace:     'nowrap',
      userSelect:     'none',
      opacity:        isNeutral ? 0.7 : 1,
    }}>
      {label}
    </span>
  )
}
