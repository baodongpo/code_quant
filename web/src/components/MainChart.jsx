/**
 * components/MainChart.jsx — K线主图
 *
 * 包含：
 *   - K线蜡烛图（前复权）
 *   - MA5 / MA20 / MA60 叠加线
 *   - BOLL 三轨（上轨红虚线 / 中轨灰虚线 / 下轨绿虚线）
 *   - BOLL 上轨以上区域浅红背景，下轨以下区域浅绿背景
 *   - 成交量柱（涨红跌绿）+ MAVOL5 / MAVOL10 叠加线
 *   - MACD 金叉/死叉买卖标记（圆形 symbolSize=12，买▲/卖▼）
 *   - 多子图 X 轴联动 + 十字线
 *
 * v3.5 变更：
 *   - 高度 440 → 500px
 *   - 移除 inside dataZoom（禁止滚轮缩放）
 *   - 移除 ECharts 内置 legend（改由 ChartSidebar HTML 图例）
 *   - 新增 MACD 金叉/死叉圆形 markPoint（symbolSize=12，17px加粗文字）
 *   - 配色统一引用 colors.js
 *   - 改为 forwardRef，暴露 ECharts 实例给 useChartSync
 *   - 支持 showMarkers prop 控制标记点显示/隐藏
 */
import React, { useMemo, forwardRef } from 'react'
import ReactECharts from 'echarts-for-react'
import { C } from '../utils/colors.js'

const MainChart = forwardRef(function MainChart({ bars, indicators, showMarkers = true }, ref) {
  const option = useMemo(() => {
    if (!bars || bars.length === 0) return {}

    const dates  = bars.map(b => b.date)
    const candle = bars.map(b => [b.open, b.close, b.low, b.high])
    const vol    = bars.map(b => b.volume)

    // 涨跌颜色
    const volColors = bars.map((b, i) => {
      const prev = i > 0 ? bars[i - 1].close : b.open
      return b.close >= prev ? C.candleUp : C.candleDown
    })

    const ma5  = indicators?.MA?.MA5  || []
    const ma20 = indicators?.MA?.MA20 || []
    const ma60 = indicators?.MA?.MA60 || []

    const bUpper = indicators?.BOLL?.upper || []
    const bMid   = indicators?.BOLL?.mid   || []
    const bLower = indicators?.BOLL?.lower || []

    const mavol5  = indicators?.MAVOL?.MAVOL5  || []
    const mavol10 = indicators?.MAVOL?.MAVOL10 || []

    // ── MACD 金叉/死叉标记点 ──
    const dif = indicators?.MACD?.dif || []
    const dea = indicators?.MACD?.dea || []
    const buyMarks  = []
    const sellMarks = []

    if (showMarkers) {
      // 密度保护：同一根K线最多1个标记
      const markedIdx = new Set()
      for (let i = 1; i < dif.length; i++) {
        if (dif[i] == null || dea[i] == null || dif[i-1] == null || dea[i-1] == null) continue
        if (markedIdx.has(i)) continue
        if (dif[i-1] <= dea[i-1] && dif[i] > dea[i]) {
          // 金叉 → 买入标记（红圈）
          const bar = candle[i]
          if (bar) {
            markedIdx.add(i)
            buyMarks.push({
              coord:  [dates[i], bar[2] * 0.998],  // K线最低价下方
              symbol: 'circle',
              symbolSize: 12,
              itemStyle: { color: C.buyBg, borderColor: C.buy, borderWidth: 2 },
              label: {
                show:       true,
                formatter:  '买▲',
                color:      C.buyText,
                fontSize:   17,
                fontWeight: 700,
                position:   'bottom',
                distance:   2,
              },
              tooltip: {
                formatter: `<b>📅 ${dates[i]}</b><br/>MACD 金叉信号（买入参考）<br/>DIF: ${dif[i]?.toFixed(4)}&nbsp;&nbsp;DEA: ${dea[i]?.toFixed(4)}<br/><small style="color:#8b949e">⚠️ 技术指标参考，非投资建议</small>`,
              },
            })
          }
        } else if (dif[i-1] >= dea[i-1] && dif[i] < dea[i]) {
          // 死叉 → 卖出标记（绿圈）
          const bar = candle[i]
          if (bar) {
            markedIdx.add(i)
            sellMarks.push({
              coord:  [dates[i], bar[3] * 1.002],  // K线最高价上方
              symbol: 'circle',
              symbolSize: 12,
              itemStyle: { color: C.sellBg, borderColor: C.sell, borderWidth: 2 },
              label: {
                show:       true,
                formatter:  '卖▼',
                color:      C.sellText,
                fontSize:   17,
                fontWeight: 700,
                position:   'top',
                distance:   2,
              },
              tooltip: {
                formatter: `<b>📅 ${dates[i]}</b><br/>MACD 死叉信号（卖出参考）<br/>DIF: ${dif[i]?.toFixed(4)}&nbsp;&nbsp;DEA: ${dea[i]?.toFixed(4)}<br/><small style="color:#8b949e">⚠️ 技术指标参考，非投资建议</small>`,
              },
            })
          }
        }
      }
    }

    const zoomStart = Math.max(0, 100 - Math.round(120 / bars.length * 100))

    return {
      backgroundColor: C.chartBg,
      animation: false,
      tooltip: {
        trigger:    'axis',
        axisPointer: {
          type: 'cross',
          crossStyle: { color: '#8b949e', width: 0.8, type: 'dashed' },
          label: { backgroundColor: '#1c2128', color: C.text, fontSize: 10 },
        },
        backgroundColor: C.panelBg,
        borderColor:     C.border2,
        textStyle:       { color: C.text, fontSize: 11 },
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
          // FEAT-02：数据更新时间（null 时不显示），DB 存 UTC，显示转为 UTC+8
          if (bar.updated_at != null) {
            const pad = n => String(n).padStart(2, '0')
            const t = new Date(bar.updated_at.replace(' ', 'T') + 'Z')
            if (!isNaN(t)) {
              const t8 = new Date(t.getTime() + 8 * 3600 * 1000)
              const displayStr = `${t8.getUTCFullYear()}-${pad(t8.getUTCMonth()+1)}-${pad(t8.getUTCDate())} ${pad(t8.getUTCHours())}:${pad(t8.getUTCMinutes())}:${pad(t8.getUTCSeconds())}`
              lines.push('─────────────────')
              lines.push(`数据更新：${displayStr}`)
            }
          }
          return lines.filter(Boolean).join('<br/>')
        },
      },
      // 不使用 ECharts 内置 legend（改由 ChartSidebar HTML 图例）
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      // 仅保留 slider 底部滑动条，移除 inside（禁止滚轮缩放）
      dataZoom: [
        {
          type:        'slider',
          xAxisIndex:  [0, 1],
          height:      18,
          bottom:      0,
          borderColor: C.border2,
          fillerColor: C.accentBg,
          handleStyle: { color: C.accent },
          textStyle:   { color: C.textMuted, fontSize: 10 },
          start:       zoomStart,
          end:         100,
        },
      ],
      // 迭代8 BUG-align: 统一 left:60, right:60，去掉 containLabel
      grid: [
        { left: 60, right: 60, top: 28,    height: '56%' },  // K线主图
        { left: 60, right: 60, top: '74%', height: '16%' },  // 成交量
      ],
      xAxis: [
        {
          type: 'category', data: dates, gridIndex: 0,
          axisLine:  { lineStyle: { color: C.axisLine } },
          axisLabel: { show: false },
          axisTick:  { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category', data: dates, gridIndex: 1,
          axisLine:  { lineStyle: { color: C.axisLine } },
          axisLabel: { color: C.textMuted, fontSize: 10 },
          axisTick:  { lineStyle: { color: C.axisLine } },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        // 迭代8 BUG-align: axisLabel 加 width:52, overflow:'truncate'
        // 迭代8.3 FEAT-axis-name: 新增价格轴名称
        {
          scale: true, gridIndex: 0,
          name: '元', nameLocation: 'end', nameGap: 4,
          nameTextStyle: { color: C.textMuted, fontSize: 10 },
          splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
          axisLabel: { color: C.textMuted, fontSize: 10, width: 52, overflow: 'truncate' },
          axisLine:  { lineStyle: { color: C.axisLine } },
        },
        // 迭代8.3 FEAT-axis-name: 新增成交量轴名称
        {
          scale: true, gridIndex: 1,
          name: '万股', nameLocation: 'end', nameGap: 4,
          nameTextStyle: { color: C.textMuted, fontSize: 10 },
          splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
          axisLabel: { color: C.textMuted, fontSize: 10, width: 52, overflow: 'truncate' },
          axisLine:  { lineStyle: { color: C.axisLine } },
          splitNumber: 2,
        },
      ],
      series: [
        // K线蜡烛图（含买卖标记点）
        {
          name:        'K线',
          type:        'candlestick',
          data:        candle,
          xAxisIndex:  0, yAxisIndex: 0,
          itemStyle: {
            color:        C.candleUp,
            color0:       C.candleDown,
            borderColor:  C.candleUp,
            borderColor0: C.candleDown,
          },
          markPoint: {
            data: [...buyMarks, ...sellMarks],
            animation: false,
          },
        },
        // MA 均线
        {
          name: 'MA5', type: 'line', data: ma5,
          xAxisIndex: 0, yAxisIndex: 0,
          smooth: false, symbol: 'none',
          lineStyle: { color: C.ma5, width: 1 },
        },
        {
          name: 'MA20', type: 'line', data: ma20,
          xAxisIndex: 0, yAxisIndex: 0,
          smooth: false, symbol: 'none',
          lineStyle: { color: C.ma20, width: 1 },
        },
        {
          name: 'MA60', type: 'line', data: ma60,
          xAxisIndex: 0, yAxisIndex: 0,
          smooth: false, symbol: 'none',
          lineStyle: { color: C.ma60, width: 1 },
        },
        // BOLL 三轨
        {
          name: 'BOLL上轨', type: 'line', data: bUpper,
          xAxisIndex: 0, yAxisIndex: 0,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.bollUpper, width: 1, type: 'dashed' },
          areaStyle: { color: 'rgba(239,83,80,0.05)', origin: 'end' },
        },
        {
          name: 'BOLL中轨', type: 'line', data: bMid,
          xAxisIndex: 0, yAxisIndex: 0,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.bollMid, width: 1, type: 'dashed' },
        },
        {
          name: 'BOLL下轨', type: 'line', data: bLower,
          xAxisIndex: 0, yAxisIndex: 0,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.bollLower, width: 1, type: 'dashed' },
          areaStyle: { color: 'rgba(38,166,154,0.05)', origin: 'start' },
        },
        // 成交量柱
        {
          name:       '成交量',
          type:       'bar',
          data:       vol.map((v, i) => ({
            value:     v,
            itemStyle: { color: volColors[i] + '99' },
          })),
          xAxisIndex: 1, yAxisIndex: 1,
          barMaxWidth: 6,
        },
        // MAVOL 均线
        {
          name: 'MAVOL5', type: 'line', data: mavol5,
          xAxisIndex: 1, yAxisIndex: 1,
          symbol: 'none',
          lineStyle: { color: C.ma5, width: 1 },
        },
        {
          name: 'MAVOL10', type: 'line', data: mavol10,
          xAxisIndex: 1, yAxisIndex: 1,
          symbol: 'none',
          lineStyle: { color: C.ma20, width: 1 },
        },
      ],
    }
  }, [bars, indicators, showMarkers])

  return (
    <div style={{ flex: 1, minWidth: 0, background: C.chartBg }}>
      <ReactECharts
        ref={ref}
        option={option}
        style={{ height: 500 }}
        notMerge={true}
        lazyUpdate={false}
      />
    </div>
  )
})

export default MainChart
