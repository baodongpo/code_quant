/**
 * components/KDJPanel.jsx — KDJ 副图
 *
 * 包含：
 *   - K线（蓝）/ D线（橙）/ J线（紫）
 *   - 80~100 区域浅红背景 + "超买"标注
 *   - 0~20 区域浅绿背景 + "超卖"标注
 *   - 20/80 参考线（水平虚线）
 *   - K/D 金叉/死叉交叉点标记
 *   - 右上角信号标签
 */
import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'

export default function KDJPanel({ dates, kdj, signal }) {
  const K = kdj?.K || []
  const D = kdj?.D || []
  const J = kdj?.J || []

  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}

    // 标记 K/D 交叉点
    const crossPoints = []
    for (let i = 1; i < K.length; i++) {
      if (K[i] == null || D[i] == null || K[i - 1] == null || D[i - 1] == null) continue
      if (K[i - 1] <= D[i - 1] && K[i] > D[i]) {
        // 金叉
        crossPoints.push({
          xAxis: dates[i], yAxis: K[i], value: K[i],
          symbol: 'triangle', symbolSize: 8,
          itemStyle: { color: '#3fb950' },
          label: { show: true, formatter: '▲', color: '#3fb950', fontSize: 9, position: 'bottom' },
        })
      } else if (K[i - 1] >= D[i - 1] && K[i] < D[i]) {
        // 死叉
        crossPoints.push({
          xAxis: dates[i], yAxis: K[i], value: K[i],
          symbol: 'triangle', symbolRotate: 180, symbolSize: 8,
          itemStyle: { color: '#f85149' },
          label: { show: true, formatter: '▼', color: '#f85149', fontSize: 9, position: 'top' },
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
          if (K[idx] != null) lines.push(`K: ${K[idx]?.toFixed(2)}`)
          if (D[idx] != null) lines.push(`D: ${D[idx]?.toFixed(2)}`)
          if (J[idx] != null) lines.push(`J: ${J[idx]?.toFixed(2)}`)
          return lines.join('<br/>')
        },
      },
      grid: [{ left: 60, right: 16, top: 12, bottom: 24 }],
      xAxis: [{
        type: 'category', data: dates,
        axisLine:  { lineStyle: { color: '#30363d' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisTick:  { lineStyle: { color: '#30363d' } },
        splitLine: { show: false },
      }],
      yAxis: [{
        min: -10, max: 110,
        splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisLine:  { lineStyle: { color: '#30363d' } },
      }],
      series: [
        // K 线
        {
          name: 'K', type: 'line', data: K,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#388bfd', width: 1.5 },
          markPoint: { data: crossPoints },
          markArea: {
            silent: true,
            data: [
              // 超买区 80~100 浅红
              [{
                yAxis: 80,
                label: { show: true, position: 'insideTopLeft', formatter: '超买', color: '#f85149', fontSize: 10 },
                itemStyle: { color: 'rgba(239,83,80,0.08)' },
              }, { yAxis: 100 }],
              // 超卖区 0~20 浅绿
              [{
                yAxis: 0,
                label: { show: true, position: 'insideBottomLeft', formatter: '超卖', color: '#3fb950', fontSize: 10 },
                itemStyle: { color: 'rgba(63,185,80,0.08)' },
              }, { yAxis: 20 }],
            ],
          },
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              { yAxis: 80, lineStyle: { color: '#f85149', type: 'dashed', width: 1 } },
              { yAxis: 20, lineStyle: { color: '#3fb950', type: 'dashed', width: 1 } },
            ],
            label: { show: true, color: '#8b949e', fontSize: 10,
                     formatter: params => params.value === 80 ? '80' : '20' },
          },
        },
        // D 线
        {
          name: 'D', type: 'line', data: D,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#ff9500', width: 1.5 },
        },
        // J 线
        {
          name: 'J', type: 'line', data: J,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#bc8cff', width: 1 },
        },
      ],
    }
  }, [dates, K, D, J])

  return (
    <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 0', position: 'relative' }}>
      <div style={{ position: 'absolute', top: 10, right: 16, zIndex: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: '#8b949e', fontWeight: 600 }}>KDJ(9)</span>
        <SignalTag indicator="KDJ" signal={signal || 'neutral'} />
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
