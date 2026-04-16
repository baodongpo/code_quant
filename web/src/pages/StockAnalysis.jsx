/**
 * pages/StockAnalysis.jsx — 个股分析页（主页面 /）
 *
 * 布局：
 *   - 顶部导航栏（股票选择 / 周期切换 / 时间范围 / 标记点开关 / 跳转 Watchlist）
 *   - 综合信号横幅（SignalBanner，导航栏与主图之间）
 *   - 主图（K线 + MA + BOLL + 成交量）+ ChartSidebar
 *   - 副图折叠控制（panel-toggle 按钮组）
 *   - MACD / RSI / KDJ 副图（各附 ChartSidebar，支持折叠）
 *   - 底部信息条（双层）
 *   - 60 秒自动刷新
 *   - 跨图时间轴联动（useChartSync）
 *
 * v3.5 变更：
 *   - 综合信号横幅
 *   - 各图表包裹 ChartSidebar（200px 说明栏）
 *   - 副图折叠控制（localStorage 持久化）
 *   - 接入 useChartSync hook
 *   - 标记点开关
 *   - 布局间距调整
 */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { fetchStocks, fetchKline, fetchWatchlistSummary, fetchHealth } from '../api/client.js'
import StockSelector     from '../components/StockSelector.jsx'
import PeriodSelector    from '../components/PeriodSelector.jsx'
import TimeRangeSelector from '../components/TimeRangeSelector.jsx'
import MainChart         from '../components/MainChart.jsx'
import MACDPanel         from '../components/MACDPanel.jsx'
import RSIPanel          from '../components/RSIPanel.jsx'
import KDJPanel          from '../components/KDJPanel.jsx'
import VPADefenderPanel  from '../components/VPADefenderPanel.jsx'
import BottomBar         from '../components/BottomBar.jsx'
import SignalBanner      from '../components/SignalBanner.jsx'
import ChartSidebar      from '../components/ChartSidebar.jsx'
import useChartSync      from '../hooks/useChartSync.js'
import { calcCompositeSignal } from '../utils/compositeSignal.js'
import { C } from '../utils/colors.js'

function daysAgo(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

const today = () => new Date().toISOString().slice(0, 10)

// OBV 取最后一个值（OBV 数组全为数字，无 null）
function obv_last_val(arr) {
  return arr.length > 0 ? arr[arr.length - 1] : null
}

// 从 localStorage 读取折叠状态（可选持久化）
function loadCollapseState() {
  try {
    const saved = localStorage.getItem('quant_panel_collapse_state')
    if (saved) return JSON.parse(saved)
  } catch (_) {}
  return { MACD: false, RSI: false, KDJ: false, VPA: false }
}

export default function StockAnalysis() {
  const [stocks,     setStocks]    = useState([])
  const [code,       setCode]      = useState(null)
  const [period,     setPeriod]    = useState('1D')
  const [startDate,  setStartDate] = useState(daysAgo(365))
  const [endDate,    setEndDate]   = useState(today())
  const [data,       setData]      = useState(null)
  const [loading,    setLoading]   = useState(false)
  const [error,      setError]     = useState(null)
  const [lastUpdate, setLastUpdate]= useState(null)
  const [showMarkers,setShowMarkers]= useState(true)     // 标记点开关
  const [collapsed,  setCollapsed] = useState(loadCollapseState)  // 副图折叠状态
  const [watchlistSignals, setWatchlistSignals] = useState({})  // 各股综合信号
  const [appVersion, setAppVersion] = useState(null)  // 系统版本号（FEAT-version）
  const [usStockSource, setUsStockSource] = useState(null)  // 美股数据源（FEAT-1：控制周期选项）
  // FEAT-legend-toggle：各副图面板的图例激活状态（seriesName → boolean，false=隐藏）
  // 切换股票时重置为全 active（新股票重新开始）
  const [legendActiveMaps, setLegendActiveMaps] = useState({ MACD: {}, RSI: {}, KDJ: {}, VPA: {} })

  // 图表 refs（供 forwardRef + useChartSync 使用）
  const mainRef = useRef(null)
  const macdRef = useRef(null)
  const rsiRef  = useRef(null)
  const kdjRef  = useRef(null)
  const vpaRef  = useRef(null)

  const timerRef = useRef(null)

  // 跨图联动（主图十字线 → 副图同步；collapsed/code 变化时重绑定新 ECharts 实例）
  useChartSync(mainRef, [macdRef, rsiRef, kdjRef, vpaRef], collapsed, code)

  // 加载股票列表
  useEffect(() => {
    fetchStocks()
      .then(list => {
        setStocks(list)
        // 从 URL 参数读取初始股票代码
        const params = new URLSearchParams(window.location.search)
        const urlCode = params.get('code')
        const initialCode = urlCode && list.find(s => s.stock_code === urlCode)
          ? urlCode
          : (list.length > 0 ? list[0].stock_code : null)
        if (initialCode && !code) setCode(initialCode)
      })
      .catch(e => setError(e.message))
  }, [])

  // 加载 watchlist 综合信号，用于下拉颜色
  useEffect(() => {
    fetchWatchlistSummary()
      .then(summary => {
        const map = {}
        summary.forEach(item => {
          map[item.stock_code] = item.signals?.composite || 'neutral'
        })
        setWatchlistSignals(map)
      })
      .catch(e => console.warn('[StockSelector] watchlist 信号加载失败，颜色功能降级:', e.message))  // 不阻断主流程
  }, [])

  // 加载系统版本号（FEAT-version：页面初始化时调用一次 /api/health）
  useEffect(() => {
    fetchHealth()
      .then(data => {
        if (data?.version) setAppVersion(data.version)
        if (data?.us_stock_source) setUsStockSource(data.us_stock_source)
      })
      .catch(() => {
        // 静默降级：版本号区域不展示，不影响其他功能
      })
  }, [])

  // 加载 K线+指标数据（切换股票时同步重置图例激活状态）
  const loadData = useCallback(async () => {
    if (!code) return
    setLoading(true)
    setError(null)
    // FEAT-legend-toggle：切换股票时重置全部图例为 active（AC-legend-toggle-8）
    setLegendActiveMaps({ MACD: {}, RSI: {}, KDJ: {}, VPA: {} })
    try {
      const result = await fetchKline(code, period, startDate, endDate)
      setData(result)
      setLastUpdate(new Date().toLocaleTimeString('zh-CN'))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [code, period, startDate, endDate])

  // 切换参数时重新拉取
  useEffect(() => {
    loadData()
  }, [loadData])

  // 60 秒自动刷新
  useEffect(() => {
    timerRef.current = setInterval(loadData, 60_000)
    return () => clearInterval(timerRef.current)
  }, [loadData])

  // 折叠状态持久化到 localStorage
  const togglePanel = (panel) => {
    setCollapsed(prev => {
      const next = { ...prev, [panel]: !prev[panel] }
      try { localStorage.setItem('quant_panel_collapse_state', JSON.stringify(next)) } catch (_) {}
      // FEAT-legend-toggle：展开时同步恢复 ECharts legend 状态（AC-legend-toggle-6）
      // 展开（prev[panel]=true → next[panel]=false），需把 inactive 的 series 重新 dispatch
      if (prev[panel] === true) {
        const refMap = { MACD: macdRef, RSI: rsiRef, KDJ: kdjRef, VPA: vpaRef }
        const panelRef = refMap[panel]
        const activeMap = legendActiveMaps[panel] || {}
        // 延迟一帧等待 ECharts 实例挂载
        setTimeout(() => {
          const chart = panelRef?.current?.getEchartsInstance?.()
          if (chart) {
            Object.entries(activeMap).forEach(([seriesName, isActive]) => {
              if (isActive === false) {
                chart.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
              }
            })
          }
        }, 80)
      }
      return next
    })
  }

  const bars       = data?.bars        || []
  const indicators = data?.indicators  || {}
  const signals    = data?.signals     || {}
  const dates      = bars.map(b => b.date)
  const closes     = bars.map(b => b.close)
  const latestBar  = bars[bars.length - 1] || null

  // RSI 最新值
  const rsiList  = indicators?.RSI?.RSI14 || []
  const rsiValue = rsiList.slice().reverse().find(v => v != null) ?? null

  // 综合信号计算
  const composite = bars.length > 0
    ? calcCompositeSignal({ signals, indicators, bars })
    : null

  // 当前股票名称
  const currentStock = stocks.find(s => s.stock_code === code)
  const stockDisplayName = currentStock?.name
    ? `${currentStock.name}（${code}）`
    : (code || '')

  // ── 侧边栏配置 ──

  const mainSidebarLegend = [
    { color: C.ma5,      type: 'line',   label: 'MA5' },
    { color: C.ma20,     type: 'line',   label: 'MA20' },
    { color: C.ma60,     type: 'line',   label: 'MA60' },
    { color: C.bollUpper,type: 'dashed', label: 'BOLL上' },
    { color: C.bollMid,  type: 'dashed', label: 'BOLL中' },
    { color: C.bollLower,type: 'dashed', label: 'BOLL下' },
    { color: C.buy,      type: 'circle', label: '买入参考' },
    { color: C.sell,     type: 'circle', label: '卖出参考' },
  ]
  const mainSidebarGuide = [
    { dotColor: C.candleUp,  text: '<b>红色蜡烛</b>=上涨，绿色=下跌' },
    { dotColor: C.ma5,       text: '价格站上 <b>MA均线</b> 为强势信号' },
    { dotColor: C.bollMid,   text: '<b>布林带</b>：触上轨留意回调，触下轨留意反弹' },
    { dotType:  'neut',      text: '成交量放大配合涨价，信号更可信' },
    { dotType:  'bull',      text: '<b>红圈●买入参考</b>：MACD金叉位置' },
    { dotType:  'bear',      text: '<b>绿圈●卖出参考</b>：MACD死叉位置' },
  ]

  const macdSidebarLegend = [
    { color: C.dif,        type: 'line',   label: 'DIF',    seriesName: 'DIF' },
    { color: C.dea,        type: 'line',   label: 'DEA',    seriesName: 'DEA' },
    { color: C.macdBarPos, type: 'bar',    label: '柱(正)', seriesName: 'MACD柱' },
    { color: C.macdBarNeg, type: 'bar',    label: '柱(负)', seriesName: 'MACD柱' },
    { color: C.buy,        type: 'circle', label: '金叉' },
    { color: C.sell,       type: 'circle', label: '死叉' },
  ]
  const macdSidebarGuide = [
    { dotType: 'bull', text: '<b>红圈●金叉</b>：DIF 上穿 DEA，短期动能由弱转强的信号' },
    { dotType: 'bear', text: '<b>绿圈●死叉</b>：DIF 下穿 DEA，短期动能由强转弱的信号' },
    { dotType: 'neut', text: 'MACD 柱由负转正并持续放大，反映多空力量正在转变' },
  ]

  const rsiSidebarLegend = [
    { color: C.dif,        type: 'line',   label: 'RSI(14)',   seriesName: 'RSI14' },
    { color: C.sell,       type: 'bar',    label: '超买区(卖)' },
    { color: C.buy,        type: 'bar',    label: '超卖区(买)' },
  ]
  const rsiSidebarGuide = [
    { dotType: 'bear', text: '<b>RSI &gt; 70（绿色区域）</b>：超买区间，价格短期涨幅较大，动能偏强' },
    { dotType: 'bull', text: '<b>RSI &lt; 30（红色区域）</b>：超卖区间，价格短期跌幅较大，动能偏弱' },
    { dotType: 'neut', text: '30–70 为中性区间，多空力量相对均衡' },
  ]

  const kdjSidebarLegend = [
    { color: C.kLine, type: 'line',   label: 'K线', seriesName: 'K' },
    { color: C.dLine, type: 'line',   label: 'D线', seriesName: 'D' },
    { color: C.jLine, type: 'dashed', label: 'J线', seriesName: 'J' },
    { color: C.buy,   type: 'circle', label: '金叉' },
    { color: C.sell,  type: 'circle', label: '死叉' },
  ]
  const kdjSidebarGuide = [
    { dotType: 'bull', text: '<b>红圈●金叉</b>：K 线从下方穿越 D 线，低位出现时反映短期超卖后的动能回升' },
    { dotType: 'bear', text: '<b>绿圈●死叉</b>：K 线从上方穿越 D 线，高位出现时反映短期超买后的动能回落' },
    { dotType: 'neut', text: 'J 线是 K/D 的放大版，超过 80 或低于 20 时波动往往加剧' },
  ]

  // VPA-Defender 侧边栏配置（迭代7）
  const vpaSidebarLegend = [
    { color: '#8b949e', type: 'line',   label: '收盘价',  seriesName: '收盘价' },
    { color: '#ef5350', type: 'line',   label: '防守线',  seriesName: '防守线' },
    { color: '#ff7043', type: 'line',   label: '阻力线',  seriesName: '阻力线' },
    { color: '#42a5f5', type: 'line',   label: 'OBV',     seriesName: 'OBV' },
    { color: '#ffa726', type: 'dashed', label: 'OBV均线', seriesName: 'OBV均线' },
  ]
  const vpaSidebarGuide = [
    { dotColor: '#26a69a', text: '<b>防守线（红色实线）</b>：基于价格波动幅度计算的动态参考线。它会随着价格创新高而自动上移，但绝不会下降。当价格跌破这条线时，意味着波动幅度已经超出了正常范围。' },
    { dotColor: '#42a5f5', text: '<b>OBV 能量潮（蓝色线）</b>：通过成交量的累计变化，观察资金的流入流出方向。当它持续上升时，说明伴随上涨的成交量大于伴随下跌的成交量。' },
    { dotColor: '#ffa726', text: '<b>OBV 均线（橙色虚线）</b>：OBV 的 20 日平均值，用来过滤单日波动噪音，判断资金流向的中期趋势。' },
    { dotColor: '#26a69a', text: '<b>绿色（共振主升浪）</b>：价格在防守线上方，且资金持续流入——量价配合良好' },
    { dotColor: '#ffd54f', text: '<b>黄色（顶背离预警）</b>：价格仍在防守线上方，但资金已开始流出——量价出现分歧' },
    { dotColor: '#2ea043', text: '<b>绿色（破位警示）</b>：价格跌破防守线——趋势可能发生变化' },  // 迭代8 BUG-vpa-color
    { dotColor: '#b0bec5', text: '<b>灰色（底部观察）</b>：价格在防守线下方，但资金开始流入——可能正在酝酿变化' },
  ]

  // VPA-Defender 最新值
  const vpaData = indicators?.VPA_DEFENDER || {}
  const latestStopLine = (vpaData.stop_line || []).slice().reverse().find(v => v != null)
  const latestOBV = obv_last_val(vpaData.obv || [])
  const latestOBVMA = (vpaData.obv_ma20 || []).slice().reverse().find(v => v != null)

  // 当前 MACD/RSI/KDJ 值
  const latestDIF = (indicators?.MACD?.dif || []).slice().reverse().find(v => v != null)
  const latestDEA = (indicators?.MACD?.dea || []).slice().reverse().find(v => v != null)
  const latestK   = (indicators?.KDJ?.K || []).slice().reverse().find(v => v != null)
  const latestD   = (indicators?.KDJ?.D || []).slice().reverse().find(v => v != null)
  const latestJ   = (indicators?.KDJ?.J || []).slice().reverse().find(v => v != null)

  return (
    <div style={{ minHeight: '100vh', background: C.chartBg, color: C.text }}>
      {/* ① 顶部导航栏 */}
      <div style={{
        display:      'flex',
        alignItems:   'center',
        flexWrap:     'wrap',
        gap:          12,
        padding:      '10px 20px',
        background:   C.panelBg,
        borderBottom: `1px solid ${C.border}`,
        position:     'sticky',
        top:          0,
        zIndex:       100,
      }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: C.text, marginRight: 8, whiteSpace: 'nowrap' }}>
          📈 {stockDisplayName || 'AI 量化决策'}
        </span>

        <StockSelector stocks={stocks} value={code} onChange={setCode} signals={watchlistSignals} />
        <PeriodSelector value={period} onChange={setPeriod} stockCode={code} usStockSource={usStockSource} />
        <TimeRangeSelector
          start={startDate} end={endDate}
          onChange={(s, e) => { setStartDate(s); setEndDate(e) }}
        />

        {/* 右侧工具栏 */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {/* 标记点开关 */}
          <button
            onClick={() => setShowMarkers(v => !v)}
            style={{
              background:   showMarkers ? '#0d2137' : C.panelBg,
              border:       `1px solid ${showMarkers ? C.accent : C.border2}`,
              borderRadius: 6,
              color:        showMarkers ? C.accentText : C.textMuted,
              fontSize:     12,
              cursor:       'pointer',
              padding:      '5px 10px',
              whiteSpace:   'nowrap',
            }}
            title="切换买卖标记点显示"
          >
            {showMarkers ? '● 标记点 开' : '○ 标记点 关'}
          </button>

          {loading && <span style={{ fontSize: 12, color: '#f0c040' }}>⏳ 加载中...</span>}
          {lastUpdate && !loading && (
            <span style={{ fontSize: 11, color: C.textMuted }}>更新: {lastUpdate}</span>
          )}
          <Link
            to="/watchlist"
            style={{
              fontSize: 13, color: C.accentText, textDecoration: 'none',
              border: `1px solid ${C.border2}`, borderRadius: 6,
              padding: '4px 10px',
            }}
          >
            Watchlist总览 →
          </Link>
          {/* 版本号（FEAT-version：从 /api/health 获取，静默降级） */}
          {appVersion && (
            <span style={{ fontSize: 11, color: C.textDim, userSelect: 'none', whiteSpace: 'nowrap' }}>
              {appVersion}
            </span>
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div style={{
          padding: '8px 20px', background: '#3a1a1a',
          color: C.buyText, fontSize: 13,
          borderBottom: `1px solid ${C.buy}`,
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span>⚠️ {error}</span>
          <button
            onClick={loadData}
            style={{
              background: 'none', border: `1px solid ${C.buy}`,
              borderRadius: 6, color: C.buyText,
              fontSize: 12, cursor: 'pointer', padding: '3px 10px',
            }}
          >重试</button>
        </div>
      )}

      {/* ② 综合信号横幅 */}
      {composite && bars.length > 0 && (
        <SignalBanner
          level={composite.level}
          score={composite.score}
          label={composite.label}
          votes={composite.votes}
        />
      )}

      {/* 图表区域 */}
      {bars.length > 0 ? (
        <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* ③ 主图 + 侧边说明栏 */}
          <div style={{
            display:      'flex',
            borderRadius: 10,
            overflow:     'hidden',
            border:       `1px solid ${C.border}`,
            background:   C.chartBg,
          }}>
            <MainChart
              ref={mainRef}
              bars={bars}
              indicators={indicators}
              showMarkers={showMarkers}
              stockCode={code}
            />
            <ChartSidebar
              title="📊 K线 · 均线 · 布林带"
              signal={signals?.MA || undefined}
              signalLabel={latestBar ? `收盘 ${latestBar.close}` : undefined}
              valueItems={latestBar ? [
                {
                  label: '最新收盘',
                  value: latestBar.close,
                  type: latestBar.last_close
                    ? (latestBar.close >= latestBar.last_close ? 'bull' : 'bear')
                    : 'neut',
                },
              ] : []}
              legendItems={mainSidebarLegend}
              guideItems={mainSidebarGuide}
            />
          </div>

          {/* 副图折叠控制按钮组 */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: C.textDim }}>显示副图：</span>
            {['MACD', 'RSI', 'KDJ', 'VPA'].map(panel => (
              <button
                key={panel}
                onClick={() => togglePanel(panel)}
                style={{
                  background:   !collapsed[panel] ? '#0d2137' : C.panelBg,
                  border:       `1px solid ${!collapsed[panel] ? C.accent : C.border2}`,
                  borderRadius: 6,
                  color:        !collapsed[panel] ? C.accentText : C.textMuted,
                  fontSize:     11,
                  cursor:       'pointer',
                  padding:      '4px 12px',
                  transition:   'all 0.15s',
                }}
              >
                {panel === 'MACD' ? 'MACD 趋势动能' : panel === 'RSI' ? 'RSI 超买超卖' : panel === 'KDJ' ? 'KDJ 短线时机' : 'VPA 量价共振'}
              </button>
            ))}
          </div>

          {/* ④-A MACD 副图 */}
          {collapsed.MACD ? (
            <MACDPanel
              dates={dates} macd={indicators.MACD} signal={signals.MACD}
              collapsed={true} onToggle={() => togglePanel('MACD')}
            />
          ) : (
            <div style={{
              display:      'flex',
              borderRadius: 10,
              overflow:     'hidden',
              border:       `1px solid ${C.border}`,
              background:   C.chartBg,
            }}>
              <MACDPanel
                key={`macd-panel-${code}`}
                ref={macdRef}
                dates={dates} macd={indicators.MACD} signal={signals.MACD}
                collapsed={false} onToggle={() => togglePanel('MACD')}
              />
              <ChartSidebar
                key={`macd-sidebar-${code}`}
                title="📶 MACD 趋势动能"
                signal={signals.MACD}
                onToggle={() => togglePanel('MACD')}
                valueItems={[
                  latestDIF != null ? { label: 'DIF', value: latestDIF.toFixed(4), type: latestDIF > 0 ? 'bull' : 'bear' } : null,
                  latestDEA != null ? { label: 'DEA', value: latestDEA.toFixed(4), type: latestDEA > 0 ? 'bull' : 'bear' } : null,
                ].filter(Boolean)}
                legendItems={macdSidebarLegend}
                guideItems={macdSidebarGuide}
                onLegendToggle={(seriesName) => {
                  // 同步更新父组件维护的激活状态（用于折叠展开时状态恢复）
                  setLegendActiveMaps(prev => ({
                    ...prev,
                    MACD: { ...prev.MACD, [seriesName]: prev.MACD[seriesName] === false ? true : false },
                  }))
                  const chart = macdRef.current?.getEchartsInstance?.()
                  if (chart) chart.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
                }}
              />
            </div>
          )}

          {/* ④-B RSI 副图 */}
          {collapsed.RSI ? (
            <RSIPanel
              dates={dates} rsi={indicators.RSI} signal={signals.RSI}
              collapsed={true} onToggle={() => togglePanel('RSI')}
            />
          ) : (
            <div style={{
              display:      'flex',
              borderRadius: 10,
              overflow:     'hidden',
              border:       `1px solid ${C.border}`,
              background:   C.chartBg,
            }}>
              <RSIPanel
                key={`rsi-panel-${code}`}
                ref={rsiRef}
                dates={dates} rsi={indicators.RSI} signal={signals.RSI}
                collapsed={false} onToggle={() => togglePanel('RSI')}
              />
              <ChartSidebar
                key={`rsi-sidebar-${code}`}
                title="💪 RSI 超买超卖"
                signal={signals.RSI}
                onToggle={() => togglePanel('RSI')}
                valueItems={rsiValue != null ? [
                  { label: 'RSI(14)', value: rsiValue.toFixed(2), type: rsiValue > 70 ? 'bear' : rsiValue < 30 ? 'bull' : 'neut' },
                ] : []}
                legendItems={rsiSidebarLegend}
                guideItems={rsiSidebarGuide}
                onLegendToggle={(seriesName) => {
                  setLegendActiveMaps(prev => ({
                    ...prev,
                    RSI: { ...prev.RSI, [seriesName]: prev.RSI[seriesName] === false ? true : false },
                  }))
                  const chart = rsiRef.current?.getEchartsInstance?.()
                  if (chart) chart.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
                }}
              />
            </div>
          )}

          {/* ④-C KDJ 副图 */}
          {collapsed.KDJ ? (
            <KDJPanel
              dates={dates} kdj={indicators.KDJ} signal={signals.KDJ}
              collapsed={true} onToggle={() => togglePanel('KDJ')}
            />
          ) : (
            <div style={{
              display:      'flex',
              borderRadius: 10,
              overflow:     'hidden',
              border:       `1px solid ${C.border}`,
              background:   C.chartBg,
            }}>
              <KDJPanel
                key={`kdj-panel-${code}`}
                ref={kdjRef}
                dates={dates} kdj={indicators.KDJ} signal={signals.KDJ}
                collapsed={false} onToggle={() => togglePanel('KDJ')}
              />
              <ChartSidebar
                key={`kdj-sidebar-${code}`}
                title="🔀 KDJ 短线时机"
                signal={signals.KDJ}
                onToggle={() => togglePanel('KDJ')}
                valueItems={[
                  latestK != null ? { label: 'K', value: latestK.toFixed(2), type: latestK > 80 ? 'bear' : latestK < 20 ? 'bull' : 'neut' } : null,
                  latestD != null ? { label: 'D', value: latestD.toFixed(2), type: latestD > 80 ? 'bear' : latestD < 20 ? 'bull' : 'neut' } : null,
                  latestJ != null ? { label: 'J', value: latestJ.toFixed(2), type: latestJ > 80 ? 'bear' : latestJ < 20 ? 'bull' : 'neut' } : null,
                ].filter(Boolean)}
                legendItems={kdjSidebarLegend}
                guideItems={kdjSidebarGuide}
                onLegendToggle={(seriesName) => {
                  setLegendActiveMaps(prev => ({
                    ...prev,
                    KDJ: { ...prev.KDJ, [seriesName]: prev.KDJ[seriesName] === false ? true : false },
                  }))
                  const chart = kdjRef.current?.getEchartsInstance?.()
                  if (chart) chart.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
                }}
              />
            </div>
          )}

          {/* ④-D VPA-Defender 副图（迭代7） */}
          {collapsed.VPA ? (
            <VPADefenderPanel
              dates={dates} closes={closes} vpaDefender={indicators.VPA_DEFENDER} signal={signals.VPA_DEFENDER}
              collapsed={true} onToggle={() => togglePanel('VPA')} stockCode={code}
            />
          ) : (
            <div style={{
              display:      'flex',
              borderRadius: 10,
              overflow:     'hidden',
              border:       `1px solid ${C.border}`,
              background:   C.chartBg,
            }}>
              <VPADefenderPanel
                key={`vpa-panel-${code}`}
                ref={vpaRef}
                dates={dates} closes={closes} vpaDefender={indicators.VPA_DEFENDER} signal={signals.VPA_DEFENDER}
                collapsed={false} onToggle={() => togglePanel('VPA')} stockCode={code}
              />
              <ChartSidebar
                key={`vpa-sidebar-${code}`}
                title="🛡️ VPA 量价共振防守"
                signal={signals.VPA_DEFENDER}
                onToggle={() => togglePanel('VPA')}
                valueItems={[
                  latestStopLine != null ? { label: '防守线', value: latestStopLine.toFixed(2), type: 'neut' } : null,
                  latestOBV != null ? { label: 'OBV', value: Number(latestOBV).toLocaleString(), type: latestOBV > 0 ? 'bull' : latestOBV < 0 ? 'bear' : 'neut' } : null,
                ].filter(Boolean)}
                legendItems={vpaSidebarLegend}
                guideItems={vpaSidebarGuide}
                onLegendToggle={(seriesName) => {
                  setLegendActiveMaps(prev => ({
                    ...prev,
                    VPA: { ...prev.VPA, [seriesName]: prev.VPA[seriesName] === false ? true : false },
                  }))
                  const chart = vpaRef.current?.getEchartsInstance?.()
                  if (chart) chart.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
                }}
              />
            </div>
          )}

        </div>
      ) : (
        !loading && (
          <div style={{
            textAlign:  'center',
            padding:    '80px 0',
            color:      C.textMuted,
            fontSize:   14,
          }}>
            {code
              ? (code.startsWith('US.')
                ? '暂无足够数据（至少需要60个交易日，请确认 TuShare 数据已同步）'
                : '暂无足够数据（至少需要60个交易日，请确认数据已同步）')
              : '请选择股票'}
          </div>
        )
      )}

      {/* 骨架屏 / 加载中提示 */}
      {loading && !data && (
        <div style={{
          padding: '40px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          {[500, 200, 200, 200, 200].map((h, i) => (
            <div key={i} style={{
              height:       h,
              borderRadius: 10,
              background:   C.panelBg,
              border:       `1px solid ${C.border}`,
              display:      'flex',
              alignItems:   'center',
              justifyContent: 'center',
              color:        C.textMuted,
              fontSize:     13,
            }}>
              {i === 0 ? '⏳ 数据加载中...' : ''}
            </div>
          ))}
        </div>
      )}

      {/* ⑤ 底部信息条 */}
      {latestBar && (
        <BottomBar latestBar={latestBar} signals={signals} rsiValue={rsiValue} />
      )}
    </div>
  )
}
