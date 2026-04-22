/**
 * components/TimeRangeSelector.jsx — 时间范围选择
 *
 * Midnight Amber 主题：方角按钮、等宽字体、琥珀 accent
 * 预设按钮 + 自定义日期区间
 */
import React, { useState } from 'react'
import { C } from '../utils/colors.js'

const PRESETS = [
  { label: '3M',  days: 90  },
  { label: '6M',  days: 180 },
  { label: '1Y',  days: 365 },
  { label: '3Y',  days: 1095},
]

function toDateStr(d) {
  return d.toISOString().slice(0, 10)
}

function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return toDateStr(d)
}

export default function TimeRangeSelector({ start, end, onChange }) {
  const [customMode, setCustomMode] = useState(false)
  const [customStart, setCustomStart] = useState(start || daysAgo(365))
  const [customEnd,   setCustomEnd]   = useState(end   || toDateStr(new Date()))

  const today = toDateStr(new Date())

  function handlePreset(days) {
    setCustomMode(false)
    onChange(daysAgo(days), today)
  }

  function handleCustomApply() {
    if (customStart && customEnd && customStart <= customEnd) {
      onChange(customStart, customEnd)
    }
  }

  const btnBase = {
    padding:       '4px 10px',
    borderRadius:  2,
    border:        '1px solid',
    fontSize:      11,
    fontFamily:    C.fontData,
    letterSpacing: '0.06em',
    cursor:        'pointer',
    transition:    'all 0.12s',
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
      {PRESETS.map(p => {
        const presetStart = daysAgo(p.days)
        const active = !customMode && start === presetStart && end === today
        return (
          <button
            key={p.label}
            onClick={() => handlePreset(p.days)}
            style={{
              ...btnBase,
              borderColor: active ? C.accent : C.border2,
              background:  active ? C.accentBg : 'transparent',
              color:       active ? C.accentText : C.textDim,
              fontWeight:  active ? 700 : 400,
            }}
          >
            {p.label}
          </button>
        )
      })}
      <button
        onClick={() => setCustomMode(m => !m)}
        style={{
          ...btnBase,
          borderColor: customMode ? C.accent : C.border2,
          background:  customMode ? C.accentBg : 'transparent',
          color:       customMode ? C.accentText : C.textDim,
          fontWeight:  customMode ? 700 : 400,
        }}
      >
        CUSTOM
      </button>
      {customMode && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 4 }}>
          <input
            type="date"
            value={customStart}
            max={customEnd}
            onChange={e => setCustomStart(e.target.value)}
            style={{
              background:  C.panelBg,
              border:      `1px solid ${C.border2}`,
              color:       C.text,
              padding:     '3px 6px',
              borderRadius: 2,
              fontSize:    11,
              fontFamily:  C.fontData,
            }}
          />
          <span style={{ color: C.textDim, fontSize: 11, fontFamily: C.fontData }}>—</span>
          <input
            type="date"
            value={customEnd}
            min={customStart}
            max={today}
            onChange={e => setCustomEnd(e.target.value)}
            style={{
              background:  C.panelBg,
              border:      `1px solid ${C.border2}`,
              color:       C.text,
              padding:     '3px 6px',
              borderRadius: 2,
              fontSize:    11,
              fontFamily:  C.fontData,
            }}
          />
          <button
            onClick={handleCustomApply}
            style={{
              ...btnBase,
              borderColor: C.accent,
              background:  C.accentBg,
              color:       C.accentText,
              fontWeight:  700,
            }}
          >
            OK
          </button>
        </div>
      )}
    </div>
  )
}
