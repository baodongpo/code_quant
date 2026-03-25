/**
 * components/RSIPanel.jsx — RSI 副图
 *
 * 包含：
 *   - RSI14 曲线
 *   - 70~100 浅绿背景（超买=卖出信号=绿底）
 *   - 0~30 浅红背景（超卖=买入信号=红底）
 *   - 30/70 参考线（水平虚线）
 *   - 右侧侧边说明栏（由父组件 ChartSidebar 提供）
 *
 * 迭代8变更：
 *   - BUG-align: grid 改为 left:60, right:60，去掉 containLabel，yAxis axisLabel 加 width:52
 *   - FEAT-guide-top: 新增 [?] 按钮 + showHelp 状态 + HELP_ITEMS 说明浮层
 *   - FEAT-collapse-btn: PanelInner 标题行移除折叠按钮（改由 ChartSidebar 统一渲染）
 *   - FEAT-guide-icon: HELP_ITEMS 各条目含 iconType，图标与图例形状一致
 */
import React, { useState, useMemo, forwardRef } from 'react'
import ReactECharts from 'echarts-for-react'
import SignalTag from './SignalTag.jsx'
import { LegendMark } from './ChartSidebar.jsx'
import { C } from '../utils/colors.js'

// 说明浮层内容（迭代8 FEAT-guide-top + FEAT-guide-icon）
const HELP_ITEMS = [
  { iconType: 'line', color: C.dif,  text: '<b>RSI 曲线</b>：相对强弱指数，衡量一段时间内价格上涨与下跌力量的比例，取值范围 0~100。' },
  { iconType: 'bar',  color: C.sell, text: '<b>超买区（RSI &gt; 70，绿色区域）</b>：价格短期涨幅较大，动能偏强，上涨速度可能放缓。' },
  { iconType: 'bar',  color: C.buy,  text: '<b>超卖区（RSI &lt; 30，红色区域）</b>：价格短期跌幅较大，动能偏弱，下跌速度可能放缓。' },
  { iconType: 'dot',  color: C.neutralText, text: '<b>中性区间（30~70）</b>：多空力量相对均衡，价格波动在正常范围内，无明显趋势偏向。' },
]

const RSIPanel = forwardRef(function RSIPanel({ dates, rsi, signal, collapsed, onToggle }, ref) {
  const rsi14 = rsi?.RSI14 || []

  // 折叠状态：仅显示标题行
  if (collapsed) {
    const latestRSI = rsi14.slice().reverse().find(v => v != null)
    return (
      <div style={{
        height:       32,
        background:   C.chartBg,
        borderRadius: 8,
        display:      'flex',
        alignItems:   'center',
        padding:      '0 12px',
        gap:          10,
        border:       `1px solid ${C.border}`,
      }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: C.textMuted }}>RSI(14)</span>
        {latestRSI != null && (
          <span style={{ fontSize: 12, color: C.text, fontWeight: 600 }}>{latestRSI.toFixed(1)}</span>
        )}
        <SignalTag indicator="RSI" signal={signal || 'neutral'} />
        <button
          onClick={onToggle}
          style={{
            marginLeft:   'auto',
            background:   'none',
            border:       `1px solid ${C.border2}`,
            borderRadius: 4,
            color:        C.textMuted,
            fontSize:     12,
            cursor:       'pointer',
            padding:      '2px 8px',
          }}
          title="展开 RSI"
        >∨</button>
      </div>
    )
  }

  return (
    <RSIPanelInner
      ref={ref}
      dates={dates}
      rsi14={rsi14}
      signal={signal}
      onToggle={onToggle}
    />
  )
})

const RSIPanelInner = forwardRef(function RSIPanelInner({ dates, rsi14, signal, onToggle }, ref) {
  const [showHelp, setShowHelp] = useState(false)

  const option = useMemo(() => {
    if (!dates || dates.length === 0) return {}

    const zoomStart = Math.max(0, 100 - Math.round(120 / dates.length * 100))

    return {
      backgroundColor: C.chartBg,
      animation: false,
      legend: { show: false, data: ['RSI14'] },
      tooltip: {
        trigger: 'axis',
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
          const v = rsi14[idx]
          // 遵循红买绿卖
          const label = v == null ? '—'
            : v > 70 ? `${v.toFixed(2)} 🟢超买（留意卖出）`
            : v < 30 ? `${v.toFixed(2)} 🔴超卖（关注买入）`
            : `${v.toFixed(2)} ⚖️中性`
          return `<b>${dates[idx]}</b><br/>RSI(14): <b>${label}</b>`
        },
      },
      // 仅保留 slider，不使用 inside（禁止滚轮缩放）
      dataZoom: [
        {
          type:        'slider',
          xAxisIndex:  [0],
          height:      16,
          bottom:      2,
          borderColor: C.border2,
          fillerColor: C.accentBg,
          handleStyle: { color: C.accent },
          textStyle:   { color: C.textMuted, fontSize: 10 },
          start:       zoomStart,
          end:         100,
        },
      ],
      // 迭代8 BUG-align: 统一 left:60, right:60，去掉 containLabel
      grid: [{ left: 60, right: 60, top: 20, bottom: 28 }],
      xAxis: [{
        type: 'category', data: dates,
        axisLine:  { lineStyle: { color: C.axisLine } },
        axisLabel: { color: C.textMuted, fontSize: 10 },
        axisTick:  { lineStyle: { color: C.axisLine } },
        splitLine: { show: false },
      }],
      // 迭代8 BUG-align: axisLabel 加 width:52, overflow:'truncate'
      yAxis: [{
        min: 0, max: 100,
        splitLine: { lineStyle: { color: C.gridLine, type: 'dashed' } },
        axisLabel: {
          color: C.textMuted, fontSize: 10,
          width: 52, overflow: 'truncate',
          formatter: v => v === 70 ? '超买70' : v === 30 ? '超卖30' : v,
        },
        axisLine: { lineStyle: { color: C.axisLine } },
      }],
      series: [
        {
          name: 'RSI14', type: 'line', data: rsi14,
          symbol: 'none', smooth: false,
          lineStyle: { color: C.dif, width: 1.5 },
          // 超买超卖区间着色（遵循红买绿卖）
          markArea: {
            silent: true,
            data: [
              // 超买区（70~100）= 卖出信号 = 绿底
              [{
                yAxis: 70,
                itemStyle: { color: C.overbought },
              }, { yAxis: 100 }],
              // 超卖区（0~30）= 买入信号 = 红底
              [{
                yAxis: 0,
                itemStyle: { color: C.oversold },
              }, { yAxis: 30 }],
            ],
          },
          markLine: {
            silent: true,
            symbol: 'none',
            data: [
              // 超买参考线 = 绿（卖出信号色）
              { yAxis: 70, lineStyle: { color: C.overboughtLine, width: 1, type: 'dashed' } },
              // 超卖参考线 = 红（买入信号色）
              { yAxis: 30, lineStyle: { color: C.oversoldLine,   width: 1, type: 'dashed' } },
            ],
            label: { show: true, color: C.textMuted, fontSize: 10,
                     formatter: params => params.value === 70 ? '70' : '30' },
          },
        },
      ],
    }
  }, [dates, rsi14])

  return (
    <div style={{ flex: 1, minWidth: 0, background: C.chartBg, position: 'relative', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      {/* 面板标题行（迭代8 FEAT-collapse-btn: 折叠按钮已移至 ChartSidebar，仅保留标题/信号/[?]） */}
      <div style={{
        padding:    '8px 12px 0',
        display:    'flex',
        alignItems: 'center',
        gap:        6,
      }}>
        <span style={{ fontSize: 11, color: C.textMuted, fontWeight: 600 }}>RSI(14)</span>
        {/* 迭代8 FEAT-guide-top: 新增 [?] 说明浮层按钮 */}
        <button
          onClick={() => setShowHelp(v => !v)}
          title={showHelp ? '收起说明' : '展开指标说明'}
          style={{
            flexShrink:   0,
            background:   showHelp ? C.accentBg : 'none',
            border:       `1px solid ${showHelp ? C.accent : C.border2}`,
            borderRadius: 4,
            color:        showHelp ? C.accentText : C.textMuted,
            fontSize:     11,
            fontWeight:   600,
            cursor:       'pointer',
            padding:      '1px 6px',
            lineHeight:   '18px',
          }}
        >?</button>
      </div>
      {/* 迭代8 FEAT-guide-top: 说明浮层（默认隐藏，点击 [?] 展开） */}
      {showHelp && (
        <div style={{
          margin:       '6px 12px 0',
          padding:      10,
          background:   C.panelBg,
          borderRadius: 8,
          border:       `1px solid ${C.border}`,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: C.accentText, marginBottom: 6 }}>
            📖 RSI 超买超卖指标
          </div>
          {HELP_ITEMS.map((item, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 11, color: C.textMuted, lineHeight: 1.5, padding: '2px 0' }}>
              <span style={{ flexShrink: 0, marginTop: 4, display: 'inline-flex', alignItems: 'center' }}>
                <LegendMark type={item.iconType || 'dot'} color={item.color} />
              </span>
              <span dangerouslySetInnerHTML={{ __html: item.text }} />
            </div>
          ))}
        </div>
      )}
      <ReactECharts
        ref={ref}
        option={option}
        style={{ height: 240 }}
        notMerge={false}
        lazyUpdate={false}
      />
    </div>
  )
})

export default RSIPanel
