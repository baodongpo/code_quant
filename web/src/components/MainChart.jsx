/**
 * components/MainChart.jsx — K线主图
 *
 * 包含：
 *   - K线蜡烛图（前复权）
 *   - MA5 / MA20 / MA60 叠加线
 *   - BOLL 三轨（上轨红虚线 / 中轨灰虚线 / 下轨绿虚线）
 *   - BOLL 上轨以上区域浅红背景，下轨以下区域浅绿背景
 *   - 成交量柱（涨红跌绿）+ MAVOL5 / MAVOL10 叠加线
 *   - 多子图 X 轴联动 + 十字线
 */
import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'

export default function MainChart({ bars, indicators }) {
  const option = useMemo(() => {
    if (!bars || bars.length === 0) return {}

    const dates  = bars.map(b => b.date)
    const candle = bars.map(b => [b.open, b.close, b.low, b.high])
    const vol    = bars.map(b => b.volume)

    // 涨跌颜色
    const volColors = bars.map((b, i) => {
      const prev = i > 0 ? bars[i - 1].close : b.open
      return b.close >= prev ? '#ef5350' : '#26a69a'
    })

    const ma5  = indicators?.MA?.MA5  || []
    const ma20 = indicators?.MA?.MA20 || []
    const ma60 = indicators?.MA?.MA60 || []

    const bUpper = indicators?.BOLL?.upper || []
    const bMid   = indicators?.BOLL?.mid   || []
    const bLower = indicators?.BOLL?.lower || []

    const mavol5  = indicators?.MAVOL?.MAVOL5  || []
    const mavol10 = indicators?.MAVOL?.MAVOL10 || []

    return {
      backgroundColor: '#0d1117',
      animation: false,
      tooltip: {
        trigger:    'axis',
        axisPointer: { type: 'cross', crossStyle: { color: '#555' } },
        backgroundColor: '#161b22',
        borderColor:     '#30363d',
        textStyle:       { color: '#e6edf3', fontSize: 12 },
        formatter(params) {
          if (!params || params.length === 0) return ''
          const idx = params[0].dataIndex
          const bar = bars[idx]
          if (!bar) return ''
          const lines = [
            `<b>${bar.date}</b>`,
            `开: ${bar.open}  高: ${bar.high}  低: ${bar.low}  收: <b>${bar.close}</b>`,
            `量: ${(bar.volume / 10000).toFixed(0)}万股`,
            bar.pe_ratio != null ? `PE: ${bar.pe_ratio}` : '',
            bar.pb_ratio != null ? `PB: ${bar.pb_ratio}` : '',
          ]
          const maLine = [
            ma5[idx]  != null ? `MA5:${ma5[idx]}`   : '',
            ma20[idx] != null ? `MA20:${ma20[idx]}`  : '',
            ma60[idx] != null ? `MA60:${ma60[idx]}`  : '',
          ].filter(Boolean).join('  ')
          if (maLine) lines.push(maLine)
          return lines.filter(Boolean).join('<br/>')
        },
      },
      legend: {
        data: ['MA5', 'MA20', 'MA60', 'BOLL上轨', 'BOLL中轨', 'BOLL下轨'],
        top: 4, right: 12,
        textStyle: { color: '#8b949e', fontSize: 11 },
        itemWidth: 14, itemHeight: 2,
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      dataZoom: [
        {
          type:       'inside',
          xAxisIndex: [0, 1],
          start:      Math.max(0, 100 - Math.round(120 / bars.length * 100)),
          end:        100,
        },
        {
          type:        'slider',
          xAxisIndex:  [0, 1],
          height:      18,
          bottom:      0,
          borderColor: '#30363d',
          fillerColor: 'rgba(56,139,253,0.15)',
          handleStyle: { color: '#388bfd' },
          textStyle:   { color: '#8b949e', fontSize: 10 },
        },
      ],
      grid: [
        { left: 60, right: 16, top: 36,  height: '54%' },  // K线主图
        { left: 60, right: 16, top: '68%', height: '18%' }, // 成交量
      ],
      xAxis: [
        {
          type: 'category', data: dates, gridIndex: 0,
          axisLine:  { lineStyle: { color: '#30363d' } },
          axisLabel: { show: false },
          axisTick:  { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category', data: dates, gridIndex: 1,
          axisLine:  { lineStyle: { color: '#30363d' } },
          axisLabel: { color: '#8b949e', fontSize: 10 },
          axisTick:  { lineStyle: { color: '#30363d' } },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          scale: true, gridIndex: 0,
          splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
          axisLabel: { color: '#8b949e', fontSize: 10 },
          axisLine:  { lineStyle: { color: '#30363d' } },
        },
        {
          scale: true, gridIndex: 1,
          splitLine: { lineStyle: { color: '#21262d', type: 'dashed' } },
          axisLabel: { color: '#8b949e', fontSize: 10 },
          axisLine:  { lineStyle: { color: '#30363d' } },
          splitNumber: 2,
        },
      ],
      series: [
        // K线蜡烛图
        {
          name:        'K线',
          type:        'candlestick',
          data:        candle,
          xAxisIndex:  0, yAxisIndex: 0,
          itemStyle: {
            color:        '#ef5350',
            color0:       '#26a69a',
            borderColor:  '#ef5350',
            borderColor0: '#26a69a',
          },
        },
        // MA 均线
        {
          name: 'MA5', type: 'line', data: ma5,
          xAxisIndex: 0, yAxisIndex: 0,
          smooth: false, symbol: 'none',
          lineStyle: { color: '#f0c040', width: 1 },
        },
        {
          name: 'MA20', type: 'line', data: ma20,
          xAxisIndex: 0, yAxisIndex: 0,
          smooth: false, symbol: 'none',
          lineStyle: { color: '#388bfd', width: 1 },
        },
        {
          name: 'MA60', type: 'line', data: ma60,
          xAxisIndex: 0, yAxisIndex: 0,
          smooth: false, symbol: 'none',
          lineStyle: { color: '#ff9500', width: 1 },
        },
        // BOLL 三轨
        {
          name: 'BOLL上轨', type: 'line', data: bUpper,
          xAxisIndex: 0, yAxisIndex: 0,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#f85149', width: 1, type: 'dashed' },
          // 上轨以上区域：areaStyle 用 stack 技巧，下面配合下轨一起做夹层
          areaStyle: {
            color: 'rgba(239,83,80,0.06)',
            origin: 'end',   // 填充到 yAxis 上边界
          },
        },
        {
          name: 'BOLL中轨', type: 'line', data: bMid,
          xAxisIndex: 0, yAxisIndex: 0,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#8b949e', width: 1, type: 'dashed' },
        },
        {
          name: 'BOLL下轨', type: 'line', data: bLower,
          xAxisIndex: 0, yAxisIndex: 0,
          symbol: 'none', smooth: false,
          lineStyle: { color: '#3fb950', width: 1, type: 'dashed' },
          areaStyle: {
            color: 'rgba(63,185,80,0.06)',
            origin: 'start',  // 填充到 yAxis 下边界
          },
        },
        // 成交量柱
        {
          name:       '成交量',
          type:       'bar',
          data:       vol.map((v, i) => ({
            value:     v,
            itemStyle: { color: volColors[i] + '99' },  // 半透明
          })),
          xAxisIndex: 1, yAxisIndex: 1,
          barMaxWidth: 6,
        },
        // MAVOL 均线
        {
          name: 'MAVOL5', type: 'line', data: mavol5,
          xAxisIndex: 1, yAxisIndex: 1,
          symbol: 'none',
          lineStyle: { color: '#f0c040', width: 1 },
        },
        {
          name: 'MAVOL10', type: 'line', data: mavol10,
          xAxisIndex: 1, yAxisIndex: 1,
          symbol: 'none',
          lineStyle: { color: '#388bfd', width: 1 },
        },
      ],
    }
  }, [bars, indicators])

  return (
    <div style={{ background: '#0d1117', borderRadius: 8, padding: '8px 0' }}>
      <ReactECharts
        option={option}
        style={{ height: 440 }}
        notMerge={true}
        lazyUpdate={false}
      />
    </div>
  )
}
