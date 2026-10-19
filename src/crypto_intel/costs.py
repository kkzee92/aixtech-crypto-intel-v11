"""Declared round-trip cost assumptions by asset class. Research only."""

from crypto_intel.models import AssetClass

CLASS_COSTS = {
    AssetClass.MAJOR: 0.0008,
    AssetClass.LARGE_CAP_ALT: 0.0014,
    AssetClass.STABLECOIN: 0.0,
    AssetClass.DEFI: 0.0022,
    AssetClass.MEME: 0.0045,
    AssetClass.L2: 0.0016,
    AssetClass.RWA: 0.0012,
    AssetClass.PERPETUAL: 0.0010,
}

def round_trip_cost(asset_class: AssetClass) -> float:
    return CLASS_COSTS.get(asset_class, 0.0015)
