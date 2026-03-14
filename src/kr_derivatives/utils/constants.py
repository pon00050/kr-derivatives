"""Shared constants for kr-derivatives."""

# Forensic thresholds
FLOOR_RULE = 0.70  # CB repricing must not go below 70% of initial conversion price (Korean regulation)
ITM_AT_ISSUANCE_FLAG = 1.0  # moneyness (S/K) > 1.0 at issue = in-the-money = suspicious

# KRX contract specs
KOSPI200_MULTIPLIER = 500_000  # KRW per index point
KOSPI200_MINI_MULTIPLIER = 100_000
KRX_TICK_SIZE_FUTURES = 0.05  # index points

# Rate defaults
KTB_DEFAULT_RATE = 0.035  # 3.5% — used when FRED fetch fails

# Volatility computation
DEFAULT_VOL_WINDOW = 252  # trading days
ANNUALIZATION_FACTOR = 252  # sqrt(252) used for annualizing daily vol

# Pricing bounds
MIN_VOL = 0.001   # 0.1% — avoid division-by-zero in IV solver
MAX_VOL = 10.0    # 1000% — cap for bisection search
IV_TOLERANCE = 1e-6
IV_MAX_ITERATIONS = 100
