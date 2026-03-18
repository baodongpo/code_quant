/**
 * components/RSIPanel.jsx — RSI 副图
 *
 * 包含：
 *   - RSI14 曲线
 *   - 70~100 浅红区域背景 + "超买"文字
 *   - 0~30 浅绿区域背景 + "超卖"文字
 *   - 30/70 参考线（水平虚线）
 *   - 右上角信号标签
 */
import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'

export default function RSIPanel({ dates, rsi, signal }) {
  const rsi14 = rsi?.RSI14 || []

  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}

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
          const v = rsi14[idx]
          const signal = v == null ? '' : v > 70 ? '🔴超买' : v < 30 ? '🟢超卖' : '⚖️中性'
          return `<b>${dates[idx]}</b><br/>RSI14: ${v != null ? v.toFixed(2) : '-'}  ${signal}`
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
        min: 0, max: 100,
        splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
        axisLabel: { color: '#8b949e', fontSize: 10 },
        axisLine:  { lineStyle: { color: '#30363d' } },
      }],
      series: [
        {
          name: 'RSI14', type: 'line', data: rsi14,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#79c0ff', width: 1.5 },
          // 超买超卖区间着色通过 markArea 实现
          markArea: {
            silent: true,
            data: [
              // 超买区 70~100 浅红背景
              [{
                yAxis: 70,
                label: { show: true, position: 'insideTopLeft', formatter: '超买', color: '#f85149', fontSize: 10 },
                itemStyle: { color: 'rgba(239,83,80,0.08)' },
              }, { yAxis: 100 }],
              // 超卖区 0~30 浅绿背景
              [{
                yAxis: 0,
                label: { show: true, position: 'insideBottomLeft', formatter: '超卖', color: '#3fb950', fontSize: 10 },
                itemStyle: { color: 'rgba(63,185,80,0.08)' },
              }, { yAxis: 30 }],
            ],
          },
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              { yAxis: 70, lineStyle: { color: '#f85149', type: 'dashed', width: 1 } },
              { yAxis: 30, lineStyle: { color: '#3fb950', type: 'dashed', width: 1 } },
            ],
            label: { show: true, color: '#8b949e', fontSize: 10,
                     formatter: params => params.value === 70 ? '70' : '30' },
          },
        },
      ],
    }
  }, [dates, rsi14])

  return (
    <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 0', position: 'relative' }}>
      <div style={{ position: 'absolute', top: 10, right: 16, zIndex: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: '#8b949e', fontWeight: 600 }}>RSI(14)</span>
        <SignalTag indicator="RSI" signal={signal || 'neutral'} />
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
