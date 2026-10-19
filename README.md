# AIxTech crypto intel v0.11: paper-only trading information system

Further advanced research harness for automated cryptocurrency **information** and paper strategy evaluation.
Builds on [kkzee92/aixtech-crypto-intel-v10](https://github.com/kkzee92/aixtech-crypto-intel-v10), prior versions, and the original [zeekiankok92/aixtech-crypto-intel](https://github.com/zeekiankok92/aixtech-crypto-intel).

It does not place live orders, does not store exchange secrets, and is not financial advice.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![version](https://img.shields.io/badge/version-0.11.0-blue)
![mode](https://img.shields.io/badge/execution-paper%20only-orange)
![Licence](https://img.shields.io/badge/licence-MIT-green)

## Enhancements in v0.11

- RSI divergence proxy for trend confirmation and mean-reversion filters across classes.
- On-Balance Volume (OBV) proxy for volume confirmation on breakouts and trends.
- Kurtosis proxy added to anomaly scoring for fat-tail detection.
- Expanded secret redaction patterns (hex private keys, PEM headers) and entropy proxy helper.
- Slightly stricter adaptive size reduction under anomaly.
- Updated docs for architecture, strategies, and security.

See [docs/asset-class-strategies.md](docs/asset-class-strategies.md) and [docs/security-architecture.md](docs/security-architecture.md).

## What it does

- Eight asset classes with advanced multi-factor research rules incorporating StochRSI, cloud, OBV, and divergence proxies.
- Multi-scale regime + volatility tier + anomaly scoring (incl. kurtosis).
- Signals with EMA, MACD, Bollinger, ADX, VWAP, StochRSI, cloud, OBV, divergence, then multi-gate risk.
- Paper-only backtests with class costs; enhanced hash-chained audit.
- Synthetic candles only. No network by default.

| Asset class | Enhanced research rule (v0.11) | Risk cap (base) | Cost |
|---|---|---|---|
| Major | Multi-EMA + MACD + Bollinger + ADX + VWAP + StochRSI + cloud + OBV/divergence; stand aside stress/high-vol/anomaly | 8% | 8 bps |
| Large-cap alt | Volume + multi-momentum + MACD + Bollinger + VWAP + StochRSI + OBV confirmation | 4% | 14 bps |
| Stablecoin | Adaptive peg + multi-stat (z, consecutive, skew, kurtosis) alerts only | 0% | n/a |
| DeFi | Calm multi-scale + channel + momentum + cloud + OBV + low anomaly | 2% | 22 bps |
| Meme | Qualified burst with volume profile/OBV, StochRSI not extreme, consistency filters | 0.5% | 45 bps |
| L2 | Multi-period RS + relative volume + correlation + consistency vs benchmark | 3% | 16 bps |
| RWA | Slow multi-scale low-vol trend with cloud, adaptive gap, momentum, anomaly | 2% | 12 bps |
| Perpetual | Funding carry with adaptive drift, stability, consistency, non-stress, low anomaly | 2% | 10 bps |

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/make_fixtures.py
PYTHONPATH=src python -m crypto_intel scan fixtures/candles_synthetic.json
PYTHONPATH=src python -m crypto_intel brief fixtures/candles_synthetic.json
PYTHONPATH=src python -m crypto_intel posture fixtures/candles_synthetic.json
```

## Controls

Paper-only. No live credentials. Class caps, adaptive confidence and sizing, kill switch, drawdown, statistical anomaly (incl. kurtosis) + correlation + StochRSI gates, hash-chained audit, expanded redaction, PDPA tripwire, gitleaks. Zero-trust research design.

## Honesty

No live exchange connector. Scores describe synthetic fixtures. Not investment, legal, or compliance advice. Research only.
