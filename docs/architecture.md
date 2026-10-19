# Architecture (v0.11)

```mermaid
flowchart LR
    FX[\"fixtures/candles_synthetic.json\"] --> M[\"market.py\"]
    M --> RG[\"regime.py multi-scale + anomaly (kurtosis) + vol\"]
    M --> ST[\"strategies.py advanced multi-factor + StochRSI + cloud + OBV + divergence per class\"]
    RG --> ST
    ST --> RK[\"risk.py adaptive gates + anomaly\"]
    CS[\"costs.py\"] --> EN[\"engine.py paper fill\"]
    RK --> EN
    EN --> AU[\"security.py enhanced audit + multi-hash + entropy\"]
    PS[\"posture.py attestation and RBAC\"] --> CLI[\"cli.py scan, brief, posture, backtest\"]
    EN --> CLI
    BR[\"briefing.py\"] --> CLI
```

Runtime dependencies are the Python standard library. Tests inject fetchers and never open a socket. See [security-architecture.md](security-architecture.md) and [asset-class-strategies.md](asset-class-strategies.md).
