"""Asset-class strategy research rules.

Advanced multi-factor heuristics with multi-scale regimes, Bollinger-style channels, ADX-like trend strength, VWAP/volume-profile proxies, Stochastic RSI, Ichimoku-style cloud, OBV proxy, RSI divergence, adaptive volatility, MACD histogram, correlation consistency, and anomaly overlays for paper research (v0.11).
Not forecasts and not a recommendation to trade.
"""

from __future__ import annotations

from statistics import fmean, pstdev

from crypto_intel.models import AssetClass, Candle, Side, Signal
from crypto_intel.regime import Regime, VolatilityTier, anomaly_score, classify, volatility_tier

PLAYBOOK: dict[AssetClass, dict[str, str]] = {
    AssetClass.MAJOR: {
        "hypothesis": "Liquid majors trend with multi-EMA, MACD, Bollinger, ADX, VWAP, StochRSI, cloud, OBV, and divergence support when not in stress, high-vol mismatch, or high anomaly.",
        "entry": "Fast > mid > slow EMA, positive MACD hist, price near/above mid Bollinger and VWAP and cloud, ADX > threshold, adaptive StochRSI, OBV rising, positive divergence.",
        "invalidation": "Stress, high-vol weak trend, high anomaly, or StochRSI stretched or negative divergence.",
        "horizon": "8 bars mean-reversion, 20 bars trend",
    },
    AssetClass.LARGE_CAP_ALT: {
        "hypothesis": "Volume-confirmed breakouts with multi-momentum, MACD, Bollinger upper, VWAP, StochRSI, and OBV support outside stress.",
        "entry": "Close above prior high and Bollinger upper, volume adaptive, positive momentum/MACD, VWAP, StochRSI not extreme, OBV confirming.",
        "invalidation": "Stress or missing multi-confirmation.",
        "horizon": "12 bars",
    },
    AssetClass.STABLECOIN: {
        "hypothesis": "Statistical multi-metric peg deviation is the signal. Adaptive + z-score + consecutive + skew + kurtosis alerts only.",
        "entry": "Deviation or multi-stat beyond thresholds raises alert. No order.",
        "invalidation": "N/A. Size zero.",
        "horizon": "1 bar monitor",
    },
    AssetClass.DEFI: {
        "hypothesis": "Trend only in multi-scale calm non-stress with channel, momentum, cloud, OBV, and low anomaly.",
        "entry": "Close above EMA and mid-channel and cloud, realised vol adaptive, positive momentum, OBV, low anomaly, not stress.",
        "invalidation": "Stress, high realised vol, or high anomaly.",
        "horizon": "10 bars",
    },
    AssetClass.MEME: {
        "hypothesis": "Qualified bursts need volume profile/OBV consistency, adaptive extension, StochRSI not extreme, not pure Bollinger extreme.",
        "entry": "15% burst, vol/OBV consistency, extension adaptive, StochRSI ok, rising closes.",
        "invalidation": "Thin liquidity, excessive extension, overbought StochRSI, extreme channel, or high anomaly.",
        "horizon": "3 bars",
    },
    AssetClass.L2: {
        "hypothesis": "Multi-period relative strength vs consistent non-stress benchmark with relative volume and positive correlation.",
        "entry": "Excess returns on 6/12 bars, relative volume, correlation consistency, benchmark not stress.",
        "invalidation": "Missing, stressed, inconsistent, or low-correlation benchmark.",
        "horizon": "12 bars",
    },
    AssetClass.RWA: {
        "hypothesis": "Slow multi-scale low-vol trend preferred; adaptive gap, stress, or high anomaly halt. Cloud confirmation.",
        "entry": "Close above EMA and prior and cloud, gap adaptive, positive slow momentum, low/normal vol, low anomaly.",
        "invalidation": "Gap, stress, high vol, or high anomaly.",
        "horizon": "24 bars",
    },
    AssetClass.PERPETUAL: {
        "hypothesis": "Negative funding with contained multi-bar drift, stability, consistency, non-stress, low anomaly.",
        "entry": "Funding <= -5 bps, |drift| adaptive, stable funding, consistency, not stress, low anomaly.",
        "invalidation": "Crowded funding, large drift, inconsistency, stress, or high anomaly.",
        "horizon": "8 bars",
    },
}


def _returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def _ema(values: list[float], span: int) -> float:
    alpha = 2.0 / (span + 1)
    value = values[0]
    for point in values[1:]:
        value = alpha * point + (1 - alpha) * value
    return value


def _macd_proxy(closes: list[float]) -> float:
    if len(closes) < 26:
        return 0.0
    return _ema(closes, 12) - _ema(closes, 26)


def _macd_hist_proxy(closes: list[float]) -> float:
    macd = _macd_proxy(closes)
    if len(closes) < 35:
        return macd
    signal = _ema([_macd_proxy(closes[:i]) for i in range(26, len(closes)+1)], 9) if len(closes) > 26 else macd
    return macd - signal


def _bollinger(closes: list[float], span: int = 20, mult: float = 2.0) -> tuple[float, float, float]:
    if len(closes) < span:
        mid = fmean(closes)
        return mid, mid, mid
    window = closes[-span:]
    mid = fmean(window)
    std = pstdev(window) if len(window) > 1 else 0.0
    return mid, mid + mult * std, mid - mult * std


def _vwap_proxy(candles: list[Candle], span: int = 14) -> float:
    """Simple volume-weighted typical price proxy."""
    window = candles[-span:]
    if not window:
        return candles[-1].close if candles else 0.0
    total_pv = sum((c.high + c.low + c.close) / 3 * c.volume for c in window)
    total_v = sum(c.volume for c in window)
    return total_pv / max(total_v, 1)


def _obv_proxy(candles: list[Candle], span: int = 10) -> float:
    """Simple On-Balance Volume proxy: cumulative signed volume."""
    if len(candles) < 2:
        return 0.0
    obv = 0.0
    window = candles[-span:]
    for i in range(1, len(window)):
        if window[i].close > window[i-1].close:
            obv += window[i].volume
        elif window[i].close < window[i-1].close:
            obv -= window[i].volume
    return obv


def _adx_proxy(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 20.0
    up_moves = []
    down_moves = []
    for i in range(1, min(period + 1, len(candles))):
        high_diff = candles[-i].high - candles[-i-1].high
        low_diff = candles[-i-1].low - candles[-i].low
        up_moves.append(max(high_diff, 0.0))
        down_moves.append(max(low_diff, 0.0))
    plus = fmean(up_moves) if up_moves else 0.0
    minus = fmean(down_moves) if down_moves else 0.0
    if plus + minus == 0:
        return 20.0
    return min(100.0, 100.0 * abs(plus - minus) / (plus + minus))


def _rsi(closes: list[float], period: int = 14) -> float:
    changes = _returns(closes[-(period + 1) :])
    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]
    average_loss = fmean(losses) if losses else 0.0
    if average_loss == 0:
        return 100.0
    rs = fmean(gains) / average_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _stoch_rsi(closes: list[float], rsi_period: int = 14, stoch_period: int = 14) -> float:
    """Stochastic RSI proxy (0-100)."""
    if len(closes) < rsi_period + stoch_period:
        return 50.0
    rsis = [_rsi(closes[:i]) for i in range(rsi_period, len(closes)+1)]
    if len(rsis) < stoch_period:
        return 50.0
    window = rsis[-stoch_period:]
    min_rsi = min(window)
    max_rsi = max(window)
    if max_rsi == min_rsi:
        return 50.0
    return 100.0 * (rsis[-1] - min_rsi) / (max_rsi - min_rsi)


def _rsi_divergence(closes: list[float], candles: list[Candle]) -> float:
    """Simple RSI divergence proxy: positive if price higher low but RSI lower, or vice versa. Returns score -1 to 1."""
    if len(closes) < 10:
        return 0.0
    rsi_now = _rsi(closes)
    rsi_prev = _rsi(closes[:-3]) if len(closes) > 5 else rsi_now
    price_now = closes[-1]
    price_prev = closes[-4] if len(closes) > 4 else price_now
    if price_now > price_prev and rsi_now < rsi_prev - 5:
        return -0.5  # bearish divergence proxy
    if price_now < price_prev and rsi_now > rsi_prev + 5:
        return 0.5  # bullish divergence proxy
    return 0.0


def _cloud_proxy(closes: list[float]) -> tuple[float, float]:
    """Simple Ichimoku-style cloud proxy using multi-span EMAs."""
    if len(closes) < 26:
        mid = fmean(closes)
        return mid, mid
    tenkan = _ema(closes, 9)
    kijun = _ema(closes, 26)
    span_a = (tenkan + kijun) / 2
    span_b = _ema(closes, 52) if len(closes) >= 52 else _ema(closes, 26)
    return span_a, span_b


def _correlation(a: list[float], b: list[float]) -> float:
    """Simple Pearson proxy on returns."""
    if len(a) < 5 or len(b) < 5:
        return 0.0
    ra = _returns(a[-min(12, len(a)):])
    rb = _returns(b[-min(12, len(b)):])
    n = min(len(ra), len(rb))
    if n < 3:
        return 0.0
    ma, mb = fmean(ra[:n]), fmean(rb[:n])
    num = sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    den_a = sum((ra[i]-ma)**2 for i in range(n))
    den_b = sum((rb[i]-mb)**2 for i in range(n))
    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)**0.5


def _atr_pct(candles: list[Candle]) -> float:
    ranges = [(c.high - c.low) / c.close for c in candles[-14:] if c.close]
    return fmean(ranges) if ranges else 0.0


def _base(candles: list[Candle], side: Side, confidence: float, reason: str, size: float, bars: int) -> Signal:
    last = candles[-1]
    regime = classify(candles)
    vol = volatility_tier(candles)
    anom = anomaly_score(candles)
    adj_conf = confidence * (0.82 if anom > 0.6 else 0.90 if vol is VolatilityTier.HIGH else 1.0)
    adj_size = size * (0.45 if anom > 0.7 else 0.70 if anom > 0.5 else 1.0)
    return Signal(
        symbol=last.symbol,
        asset_class=last.asset_class,
        side=side,
        confidence=round(max(0.0, min(adj_conf, 1.0)), 4),
        reason=f"{reason}; regime={regime.value}; vol={vol.value}; anom={anom}",
        stop_distance_pct=round(max(_atr_pct(candles) * 1.5, 0.01), 4),
        size_fraction=round(max(0.0, adj_size), 4),
        horizon_bars=bars,
    )


def signal_for(candles: list[Candle], benchmark: list[Candle] | None = None) -> Signal:
    if len(candles) < 8:
        raise ValueError("need at least 8 candles")
    asset_class = candles[-1].asset_class
    closes = [c.close for c in candles]
    regime = classify(candles)
    vol = volatility_tier(candles)
    if asset_class is AssetClass.MAJOR:
        return _major(candles, closes, regime, vol)
    if asset_class is AssetClass.LARGE_CAP_ALT:
        return _breakout(candles, closes, size=0.04, bars=12, regime=regime, vol=vol)
    if asset_class is AssetClass.STABLECOIN:
        return _stable(candles, vol)
    if asset_class is AssetClass.DEFI:
        return _defi(candles, closes, regime, vol)
    if asset_class is AssetClass.MEME:
        return _meme(candles, closes, vol)
    if asset_class is AssetClass.L2:
        return _l2(candles, closes, benchmark, vol)
    if asset_class is AssetClass.RWA:
        return _rwa(candles, closes, regime, vol)
    return _perpetual(candles, closes, vol)


def _major(candles: list[Candle], closes: list[float], regime: Regime, vol: VolatilityTier) -> Signal:
    fast, mid, slow = _ema(closes, 5), _ema(closes, 8), _ema(closes, 13)
    rsi_period = 16 if vol is VolatilityTier.LOW else 12 if vol is VolatilityTier.HIGH else 14
    stoch = _stoch_rsi(closes, rsi_period)
    rsi_upper = 75 if vol is VolatilityTier.HIGH else 80
    rsi_lower_rev = 20 if vol is VolatilityTier.HIGH else 25
    macd_h = _macd_hist_proxy(closes)
    bb_mid, bb_upper, _ = _bollinger(closes)
    vwap = _vwap_proxy(candles)
    adx = _adx_proxy(candles)
    span_a, span_b = _cloud_proxy(closes)
    cloud_top = max(span_a, span_b)
    obv = _obv_proxy(candles)
    div = _rsi_divergence(closes, candles)
    anom = anomaly_score(candles)
    if regime is Regime.STRESS or (vol is VolatilityTier.HIGH and adx < 25) or anom > 0.65:
        return _base(candles, Side.FLAT, 0.38, "major stress, high-vol weak, or high anomaly: stand aside", 0.0, 1)
    if (fast > mid > slow and macd_h > 0 and closes[-1] >= bb_mid * 0.995 and closes[-1] >= vwap * 0.998 and closes[-1] >= cloud_top * 0.997 and adx > 22 and stoch <= rsi_upper and obv > 0 and div >= 0):
        return _base(candles, Side.LONG, 0.89, "major multi-EMA + MACD hist + Bollinger + VWAP + cloud + ADX + OBV + divergence, adaptive StochRSI", 0.06, 20)
    if regime is Regime.RANGE and stoch < rsi_lower_rev and closes[-1] > closes[-3] and div > 0:
        return _base(candles, Side.LONG, 0.73, "major mean-reversion: washed-out adaptive StochRSI in range with bullish divergence", 0.03, 8)
    return _base(candles, Side.FLAT, 0.34, "major: no aligned multi-factor edge", 0.0, 1)


def _breakout(candles: list[Candle], closes: list[float], size: float, bars: int, regime: Regime, vol: VolatilityTier) -> Signal:
    if regime is Regime.STRESS:
        return _base(candles, Side.FLAT, 0.34, "breakout suppressed in stress", 0.0, 1)
    window = closes[-6:-1]
    volume_now = candles[-1].volume
    volume_base = fmean(c.volume for c in candles[-6:-1])
    mom_short = closes[-1] / closes[-3] - 1.0
    mom_med = closes[-1] / closes[-6] - 1.0
    vol_mult = 1.7 if vol is VolatilityTier.HIGH else 1.35
    macd = _macd_proxy(closes)
    _, bb_upper, _ = _bollinger(closes, 15)
    vwap = _vwap_proxy(candles, 10)
    stoch = _stoch_rsi(closes)
    obv = _obv_proxy(candles)
    if (closes[-1] > max(window) and closes[-1] > bb_upper * 0.998 and volume_now > volume_base * vol_mult and mom_short > 0.007 and mom_med > 0.0 and macd > 0 and closes[-1] >= vwap * 0.997 and stoch < 85 and obv > 0):
        return _base(candles, Side.LONG, 0.84, "volume-confirmed breakout with multi-momentum, MACD, Bollinger, VWAP, StochRSI, OBV", size, bars)
    return _base(candles, Side.FLAT, 0.29, "no confirmed multi-factor breakout", 0.0, 1)


def _stable(candles: list[Candle], vol: VolatilityTier) -> Signal:
    deviation = abs(candles[-1].close - 1.0)
    closes = [c.close for c in candles[-20:]]
    z = 0.0
    consecutive = 0
    if len(closes) > 5:
        mean_p = fmean(closes)
        std_p = pstdev(closes) if len(closes) > 1 else 0.001
        z = abs(candles[-1].close - mean_p) / max(std_p, 0.001)
        consecutive = sum(1 for c in closes[-3:] if abs(c - 1.0) > 0.002)
    watch = 0.0025 if vol is VolatilityTier.HIGH else 0.002
    depeg = 0.006 if vol is VolatilityTier.HIGH else 0.005
    if deviation >= depeg or z > 3.5 or consecutive >= 3:
        return _base(candles, Side.ALERT, 0.96, f"stablecoin depeg monitor: deviation {deviation:.4f} z={z:.2f} consec={consecutive}", 0.0, 1)
    if deviation >= watch or z > 2.2:
        return _base(candles, Side.ALERT, 0.78, f"stablecoin watch band: deviation {deviation:.4f} z={z:.2f}", 0.0, 1)
    return _base(candles, Side.FLAT, 0.84, "stablecoin inside peg band", 0.0, 1)


def _defi(candles: list[Candle], closes: list[float], regime: Regime, vol: VolatilityTier) -> Signal:
    realised = fmean(abs(v) for v in _returns(closes[-8:]))
    vol_limit = 0.045 if vol is VolatilityTier.HIGH else 0.058
    mom = closes[-1] / closes[-5] - 1.0
    bb_mid, _, _ = _bollinger(closes, 10)
    span_a, span_b = _cloud_proxy(closes)
    cloud_top = max(span_a, span_b)
    obv = _obv_proxy(candles)
    anom = anomaly_score(candles)
    if regime is Regime.STRESS or realised > vol_limit or anom > 0.6:
        return _base(candles, Side.FLAT, 0.42, "defi volatility or anomaly regime: stand aside", 0.0, 1)
    if closes[-1] > _ema(closes, 8) and closes[-1] > bb_mid and closes[-1] > cloud_top * 0.998 and mom > 0.004 and obv > 0:
        return _base(candles, Side.LONG, 0.79, "defi trend in calm multi-scale regime with channel, cloud, momentum, OBV, low anomaly", 0.02, 10)
    return _base(candles, Side.FLAT, 0.35, "defi: no calm multi-factor trend", 0.0, 1)


def _meme(candles: list[Candle], closes: list[float], vol: VolatilityTier) -> Signal:
    liquidity = fmean(c.volume for c in candles[-5:])
    burst = closes[-1] / closes[-4] - 1.0
    extension = closes[-1] / closes[-8] - 1.0
    vol_accel = candles[-1].volume / max(candles[-2].volume, 1)
    rising = closes[-1] > closes[-2] > closes[-3]
    stoch = _stoch_rsi(closes)
    ext_limit = 0.26 if vol is VolatilityTier.HIGH else 0.33
    accel_req = 1.4 if vol is VolatilityTier.HIGH else 1.25
    _, bb_upper, _ = _bollinger(closes, 10)
    obv = _obv_proxy(candles)
    anom = anomaly_score(candles)
    if liquidity < 1000 or anom > 0.7:
        return _base(candles, Side.FLAT, 0.14, "meme liquidity thin or high anomaly", 0.0, 1)
    if extension > ext_limit or stoch > 85 or closes[-1] > bb_upper * 1.05:
        return _base(candles, Side.FLAT, 0.29, "meme chase filter: extension, StochRSI, or extreme Bollinger", 0.0, 1)
    if burst > 0.15 and vol_accel > accel_req and rising and stoch < 80 and obv > 0:
        return _base(candles, Side.LONG, 0.90, "meme momentum burst with volume consistency/OBV, StochRSI ok; hard time stop", 0.005, 3)
    return _base(candles, Side.FLAT, 0.24, "meme: no qualified multi-factor burst", 0.0, 1)


def _l2(candles: list[Candle], closes: list[float], benchmark: list[Candle] | None, vol: VolatilityTier) -> Signal:
    if not benchmark or len(benchmark) < 12:
        return _base(candles, Side.FLAT, 0.24, "l2 requires a benchmark series", 0.0, 1)
    if classify(benchmark) is Regime.STRESS:
        return _base(candles, Side.FLAT, 0.36, "l2 benchmark in stress", 0.0, 1)
    own6 = closes[-1] / closes[-6] - 1.0
    own12 = closes[-1] / closes[-12] - 1.0
    bench_closes = [c.close for c in benchmark]
    bench6 = bench_closes[-1] / bench_closes[-6] - 1.0
    bench12 = bench_closes[-1] / bench_closes[-12] - 1.0
    thresh6 = 0.036 if vol is VolatilityTier.HIGH else 0.029
    thresh12 = 0.026 if vol is VolatilityTier.HIGH else 0.019
    own_vol = fmean(c.volume for c in candles[-6:])
    bench_vol = fmean(c.volume for c in benchmark[-6:]) if benchmark else 1
    rel_vol = own_vol / max(bench_vol, 1)
    corr = _correlation(closes, bench_closes)
    if own6 - bench6 > thresh6 and own12 - bench12 > thresh12 and rel_vol > 0.85 and corr > 0.3:
        return _base(candles, Side.LONG, 0.81, "l2 multi-period relative strength + relative volume + correlation versus consistent benchmark", 0.03, 12)
    return _base(candles, Side.FLAT, 0.34, "l2 not leading benchmark on multi-period with volume and correlation", 0.0, 1)


def _rwa(candles: list[Candle], closes: list[float], regime: Regime, vol: VolatilityTier) -> Signal:
    gap = candles[-1].open / candles[-2].close - 1.0
    gap_limit = 0.06 if vol is VolatilityTier.HIGH else 0.075
    mom = closes[-1] / closes[-8] - 1.0
    span_a, span_b = _cloud_proxy(closes)
    cloud_top = max(span_a, span_b)
    anom = anomaly_score(candles)
    if abs(gap) > gap_limit or regime is Regime.STRESS or vol is VolatilityTier.HIGH or anom > 0.6:
        return _base(candles, Side.FLAT, 0.44, "rwa gap, stress, high vol, or anomaly halt", 0.0, 1)
    if closes[-1] > _ema(closes, 8) and closes[-1] > closes[-5] and closes[-1] > cloud_top * 0.998 and mom > 0.0:
        return _base(candles, Side.LONG, 0.76, "rwa slow multi-scale trend with cloud, positive momentum and low anomaly", 0.02, 24)
    return _base(candles, Side.FLAT, 0.34, "rwa: no slow multi-scale trend with momentum and cloud", 0.0, 1)


def _perpetual(candles: list[Candle], closes: list[float], vol: VolatilityTier) -> Signal:
    funding = candles[-1].funding_rate
    prev_funding = candles[-2].funding_rate if len(candles) > 1 else funding
    drift = closes[-1] / closes[-6] - 1.0
    funding_stable = abs(funding - prev_funding) < 0.0002
    drift_limit = 0.03 if vol is VolatilityTier.HIGH else 0.038
    mom = closes[-1] / closes[-3] - 1.0
    consistency = abs(closes[-1] / closes[-4] - 1.0) < 0.025
    anom = anomaly_score(candles)
    if funding >= 0.001:
        return _base(candles, Side.ALERT, 0.77, "perp funding crowded: monitor, no carry", 0.0, 1)
    if (funding <= -0.0005 and abs(drift) < drift_limit and funding_stable and abs(mom) < 0.028 and consistency and anom < 0.55):
        return _base(candles, Side.LONG, 0.84, "perp funding carry: negative funding, multi-bar drift contained, stable, consistent, low anomaly", 0.02, 8)
    if funding <= -0.0005:
        return _base(candles, Side.FLAT, 0.44, "perp funding attractive but drift, stability, consistency, or anomaly not met", 0.0, 1)
    return _base(candles, Side.FLAT, 0.34, "perp: no carry edge", 0.0, 1)
