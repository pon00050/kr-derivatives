"""kr-derivatives: Korean derivatives pricing and forensic analytics.

Public API:
    Pricing:   bs_call, bs_put, implied_vol, greeks
    Contracts: CBSpec, WarrantSpec, ContractType
    Forensic:  cb_issuance_score, repricing_coercion_score, composite_score
    Market:    compute_hist_vol, fetch_ktb_rate
"""

from .pricing import bs_call, bs_put, implied_vol, greeks
from .contracts import CBSpec, WarrantSpec, ContractType
from .forensic import cb_issuance_score, repricing_coercion_score, composite_score
from .market import compute_hist_vol, fetch_ktb_rate

__version__ = "0.1.0"

__all__ = [
    # Pricing
    "bs_call",
    "bs_put",
    "implied_vol",
    "greeks",
    # Contracts
    "CBSpec",
    "WarrantSpec",
    "ContractType",
    # Forensic
    "cb_issuance_score",
    "repricing_coercion_score",
    "composite_score",
    # Market
    "compute_hist_vol",
    "fetch_ktb_rate",
]
