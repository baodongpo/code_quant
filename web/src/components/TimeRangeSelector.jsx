/**
 * components/TimeRangeSelector.jsx — 时间范围选择
 * 预设按钮 + 自定义日期区间
 */
import React, { useState } from 'react'

const PRESETS = [
  { label: '近3月', days: 90  },
  { label: '近6月', days: 180 },
  { label: '近1年', days: 365 },
  { label: '近3年', days: 1095},
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
    padding: '4px 10px', borderRadius: 6, border: '1px solid',
    fontSize: 12, cursor: 'pointer', transition: 'all 0.15s',
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
      {PRESETS.map(p => {
        const presetStart = daysAgo(p.days)
        const active = !customMode && start === presetStart && end === today
        return (
          <button
            key={p.label}
            onClick={() => handlePreset(p.days)}
            style={{
              ...btnBase,
              borderColor: active ? '#388bfd' : '#30363d',
              background:  active ? '#1f3a5e' : '#1c2128',
              color:       active ? '#79c0ff' : '#8b949e',
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
          borderColor: customMode ? '#388bfd' : '#30363d',
          background:  customMode ? '#1f3a5e' : '#1c2128',
          color:       customMode ? '#79c0ff' : '#8b949e',
        }}
      >
        自定义
      </button>
      {customMode && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 4 }}>
          <input
            type="date"
            value={customStart}
            max={customEnd}
            onChange={e => setCustomStart(e.target.value)}
            style={{ background: '#1c2128', border: '1px solid #30363d', color: '#e6edf3',
                     padding: '3px 6px', borderRadius: 4, fontSize: 12 }}
          />
          <span style={{ color: '#8b949e', fontSize: 12 }}>~</span>
          <input
            type="date"
            value={customEnd}
            min={customStart}
            max={today}
            onChange={e => setCustomEnd(e.target.value)}
            style={{ background: '#1c2128', border: '1px solid #30363d', color: '#e6edf3',
                     padding: '3px 6px', borderRadius: 4, fontSize: 12 }}
          />
          <button
            onClick={handleCustomApply}
            style={{ ...btnBase, borderColor: '#388bfd', background: '#1f3a5e',
                     color: '#79c0ff', fontWeight: 600 }}
          >
            确认
          </button>
        </div>
      )}
    </div>
  )
}
