/**
 * utils/compositeSignal.js — 综合信号评分算法
 *
 * 纯前端计算，基于后端已返回的 signals + indicators + bars 数据
 * 严禁包含任何交易下单逻辑，仅用于技术指标机械判断辅助展示。
 *
 * 评分规则参考 PRD §3.1.1
 */

/**
 * 计算综合信号
 * @param {object} params
 * @param {object} params.signals    - 后端信号对象 { MACD, RSI, KDJ, BOLL, MA }
 * @param {object} params.indicators - 后端指标数据 { MACD:{dif,dea,macd}, RSI:{RSI14}, KDJ:{K,D}, BOLL:{upper,mid,lower}, MA:{MA5,MA10,MA20} }
 * @param {Array}  params.bars       - K线数据数组（最新一根在末尾）
 * @returns {{ level: string, score: number, label: string, votes: Array }}
 */
export function calcCompositeSignal({ signals = {}, indicators = {}, bars = [] }) {
  const votes = []
  let totalScore = 0

  // ── MACD 评分 ──
  const dif = indicators?.MACD?.dif || []
  const dea = indicators?.MACD?.dea || []
  const macdScore = calcMACDScore(dif, dea)
  if (macdScore !== 0) {
    votes.push({
      indicator: 'MACD',
      score: macdScore,
      label: macdScore > 0
        ? `MACD ${macdScore === 3 ? '金叉' : '多头'} +${macdScore}`
        : `MACD ${macdScore === -3 ? '死叉' : '空头'} ${macdScore}`,
    })
    totalScore += macdScore
  }

  // ── RSI 评分 ──
  const rsi14 = indicators?.RSI?.RSI14 || []
  const latestRSI = getLatest(rsi14)
  const rsiScore = calcRSIScore(latestRSI)
  if (rsiScore !== 0) {
    const rsiLabel = getRSILabel(latestRSI, rsiScore)
    votes.push({ indicator: 'RSI', score: rsiScore, label: rsiLabel })
    totalScore += rsiScore
  }

  // ── KDJ 评分 ──
  const kArr = indicators?.KDJ?.K || []
  const dArr = indicators?.KDJ?.D || []
  const kdjScore = calcKDJScore(kArr, dArr)
  if (kdjScore !== 0) {
    const latestK = getLatest(kArr)
    const kdjLabel = getKDJLabel(kdjScore, latestK)
    votes.push({ indicator: 'KDJ', score: kdjScore, label: kdjLabel })
    totalScore += kdjScore
  }

  // ── BOLL 评分 ──
  const bollUpper = indicators?.BOLL?.upper || []
  const bollLower = indicators?.BOLL?.lower || []
  const latestClose = bars.length > 0 ? bars[bars.length - 1].close : null
  const latestUpper = getLatest(bollUpper)
  const latestLower = getLatest(bollLower)
  const latestMid   = getLatest(indicators?.BOLL?.mid || [])
  const bollScore = calcBOLLScore(latestClose, latestUpper, latestMid, latestLower)
  if (bollScore !== 0) {
    const bollLabel = getBOLLLabel(bollScore)
    votes.push({ indicator: 'BOLL', score: bollScore, label: bollLabel })
    totalScore += bollScore
  }

  // ── MA 评分 ──
  const ma5arr  = indicators?.MA?.MA5  || []
  const ma20arr = indicators?.MA?.MA20 || []
  const ma60arr = indicators?.MA?.MA60 || []
  const latestMA5  = getLatest(ma5arr)
  const latestMA20 = getLatest(ma20arr)
  const latestMA60 = getLatest(ma60arr)
  const maScore = calcMAScore(latestMA5, latestMA20, latestMA60)
  if (maScore !== 0) {
    votes.push({
      indicator: 'MA',
      score: maScore,
      label: maScore > 0 ? `MA 多头排列 +${maScore}` : `MA 空头排列 ${maScore}`,
    })
    totalScore += maScore
  }

  // ── 综合结论 ──
  const { level, label } = getConclusion(totalScore)

  return { level, score: totalScore, label, votes }
}

// ─────────────────────────────────────
// 各指标评分函数
// ─────────────────────────────────────

/** MACD：检测最近3根K线内的金叉/死叉 */
function calcMACDScore(dif, dea) {
  if (!dif.length || !dea.length) return 0
  const n = dif.length

  // 检测最近3根K线内是否有金叉/死叉
  for (let i = n - 1; i >= Math.max(1, n - 3); i--) {
    if (dif[i] == null || dea[i] == null || dif[i - 1] == null || dea[i - 1] == null) continue
    if (dif[i - 1] <= dea[i - 1] && dif[i] > dea[i]) return +3   // 金叉
    if (dif[i - 1] >= dea[i - 1] && dif[i] < dea[i]) return -3   // 死叉
  }

  // 无近期金/死叉，看当前 DIF vs DEA
  const latestDIF = getLatest(dif)
  const latestDEA = getLatest(dea)
  if (latestDIF != null && latestDEA != null) {
    if (latestDIF > latestDEA) return +2   // 多头持续
    if (latestDIF < latestDEA) return -2   // 空头持续
  }
  return 0
}

/** RSI 分区评分 */
function calcRSIScore(rsi) {
  if (rsi == null) return 0
  if (rsi >= 20 && rsi < 30) return +2   // 深度超卖，强反弹信号
  if (rsi < 20)               return +1   // 超卖
  if (rsi >= 30 && rsi <= 50) return +1   // 超卖回升中性偏多
  if (rsi > 50 && rsi <= 70)  return +2   // 中性偏多
  if (rsi > 70)               return -1   // 超买
  return 0
}

function getRSILabel(rsi, score) {
  if (rsi == null) return `RSI 信号 +${score}`
  if (rsi > 70)   return `RSI 超买(${rsi?.toFixed(1)}) ${score}`
  if (rsi < 30)   return `RSI 超卖(${rsi?.toFixed(1)}) +${score}`
  return `RSI 中性(${rsi?.toFixed(1)}) +${score}`
}

/** KDJ 金叉/死叉评分 */
function calcKDJScore(kArr, dArr) {
  if (!kArr.length || !dArr.length) return 0
  const n = kArr.length

  // 检测最近一次金/死叉（从末尾往前找最近的交叉）
  for (let i = n - 1; i >= 1; i--) {
    if (kArr[i] == null || dArr[i] == null || kArr[i-1] == null || dArr[i-1] == null) continue
    if (kArr[i-1] <= dArr[i-1] && kArr[i] > dArr[i]) {
      // 金叉
      const k = kArr[i]
      return k < 30 ? +2 : +1
    }
    if (kArr[i-1] >= dArr[i-1] && kArr[i] < dArr[i]) {
      // 死叉
      const k = kArr[i]
      return k > 70 ? -2 : -1
    }
    break  // 只看最近一次交叉
  }
  return 0
}

function getKDJLabel(score, latestK) {
  const kStr = latestK != null ? `(K=${latestK?.toFixed(1)})` : ''
  if (score === +2) return `KDJ 金叉低位${kStr} +${score}`
  if (score === +1) return `KDJ 金叉中位${kStr} +${score}`
  if (score === -2) return `KDJ 死叉高位${kStr} ${score}`
  if (score === -1) return `KDJ 死叉中位${kStr} ${score}`
  return `KDJ ${score}`
}

/** BOLL 评分：价格相对轨道位置 */
function calcBOLLScore(close, upper, mid, lower) {
  if (close == null || upper == null || lower == null) return 0
  if (close > upper) return -2            // 超买突破上轨
  if (close < lower) return +2            // 超卖突破下轨
  if (mid != null) {
    const range = upper - lower
    if (range > 0) {
      const pos = (close - lower) / range  // 0~1
      if (pos > 2 / 3) return +1           // 上方1/3区间
      if (pos < 1 / 3) return -1           // 下方1/3区间
    }
  }
  return 0
}

function getBOLLLabel(score) {
  if (score === +2) return `BOLL 下轨突破 +${score}`
  if (score === -2) return `BOLL 上轨突破 ${score}`
  if (score === +1) return `BOLL 上方区间 +${score}`
  if (score === -1) return `BOLL 下方区间 ${score}`
  return `BOLL +${score}`
}

/** MA 排列评分 */
function calcMAScore(ma5, ma20, ma60) {
  if (ma5 == null || ma20 == null) return 0
  if (ma60 != null) {
    if (ma5 > ma20 && ma20 > ma60) return +2   // 多头排列
    if (ma5 < ma20 && ma20 < ma60) return -2   // 空头排列
  } else {
    if (ma5 > ma20) return +1
    if (ma5 < ma20) return -1
  }
  return 0
}

// ─────────────────────────────────────
// 综合结论映射
// ─────────────────────────────────────

function getConclusion(score) {
  if (score >= 5)  return { level: 'bullish', label: '多项指标共振向上，技术面偏强' }
  if (score >= 2)  return { level: 'bullish', label: '技术面多头信号为主，可关注买点' }
  if (score >= -1) return { level: 'neutral', label: '多空信号分歧，建议观望等待方向' }
  if (score >= -4) return { level: 'bearish', label: '技术面空头信号为主，注意风险' }
  return             { level: 'bearish', label: '多项指标共振向下，技术面偏弱' }
}

// ─────────────────────────────────────
// 工具函数
// ─────────────────────────────────────

/** 获取数组最后一个非 null 值 */
function getLatest(arr) {
  if (!arr || !arr.length) return null
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] != null) return arr[i]
  }
  return null
}
