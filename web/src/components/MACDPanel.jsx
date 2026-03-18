/**
 * components/MACDPanel.jsx — MACD 副图
 *
 * 包含：
 *   - DIF 线（蓝）/ DEA 线（橙）
 *   - MACD 柱（正值红 / 负值绿）
 *   - 金叉/死叉交叉点标记（▲▼）
 *   - 右上角信号标签
 */
import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'

export default function MACDPanel({ dates, macd, signal }) {
  const { dif = [], dea = [], macd: macdBar = [] } = macd || {}

  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}

    // 标记金叉/死叉交叉点
    const crossPoints = []
    for (let i = 1; i < dif.length; i++) {
      if (dif[i] == null || dea[i] == null || dif[i - 1] == null || dea[i - 1] == null) continue
      const wasBelow = dif[i - 1] <= dea[i - 1]
      const isAbove  = dif[i] > dea[i]
      const wasAbove = dif[i - 1] >= dea[i - 1]
      const isBelow  = dif[i] < dea[i]

      if (wasBelow && isAbove) {
        // 金叉
        crossPoints.push({
          xAxis: dates[i],
          yAxis: dif[i],
          value: dif[i],
          symbol: 'triangle',
          symbolSize: 10,
          itemStyle: { color: '#3fb950' },
          label: { show: true, formatter: '▲', color: '#3fb950', fontSize: 10, position: 'bottom' },
        })
      } else if (wasAbove && isBelow) {
        // 死叉
        crossPoints.push({
          xAxis: dates[i],
          yAxis: dif[i],
          value: dif[i],
          symbol: 'triangle',
          symbolRotate: 180,
          symbolSize: 10,
          itemStyle: { color: '#f85149' },
          label: { show: true, formatter: '▼', color: '#f85149', fontSize: 10, position: 'top' },
        })
      }
    }

    return {
      backgroundColor: '#0d1117',
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: '#161b22',
        borderColor:     '#30363d',
        textStyle:       { color: '#e6edf3', fontSize: 12 },
        formatter(params) {
          if (!params || params.length === 0) return ''
          const idx = params[0].dataIndex
          const lines = [`<b>${dates[idx]}</b>`]
          if (dif[idx]     != null) lines.push(`DIF: ${dif[idx]?.toFixed(4)}`)
          if (dea[idx]     != null) lines.push(`DEA: ${dea[idx]?.toFixed(4)}`)
          if (macdBar[idx] != null) lines.push(`MACD柱: ${macdBar[idx]?.toFixed(4)}`)
          return lines.join('<br/>')
        },
      },
      grid: [{ left: 60, right: 16, top: 12, bottom: 24 }],
      xAxis: [{
        type: 'category', data: dates,
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisTick:  { lineStyle: { color: '#30363d' } },
        splitLine: { show: false },
      }],
      yAxis: [{
        scale: true,
        splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisLine:  { lineStyle: { color: '#30363d' } },
      }],
      series: [
        // MACD 柱
        {
          name: 'MACD柱',
          type: 'bar',
          data: macdBar.map(v => ({
            value:     v,
            itemStyle: { color: v == null ? 'transparent' : v >= 0 ? '#ef5350cc' : '#26a69acc' },
          })),
          barMaxWidth: 6,
        },
        // DIF 线
        {
          name: 'DIF', type: 'line', data: dif,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#388bfd', width: 1.5 },
          markPoint: { data: crossPoints },
        },
        // DEA 线
        {
          name: 'DEA', type: 'line', data: dea,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#ff9500', width: 1.5 },
        },
      ],
    }
  }, [dates, dif, dea, macdBar])

  return (
    <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 0', position: 'relative' }}>
      <div style={{ position: 'absolute', top: 10, right: 16, zIndex: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: '#8b949e', fontWeight: 600 }}>MACD(12,26,9)</span>
        <SignalTag indicator="MACD" signal={signal || 'neutral'} />
      </div>
      <ReactECharts
        option={option}
        style={{ height: 140 }}
        notMerge={true}
        lazyUpdate={false}
      />
    </div>
  )
}
