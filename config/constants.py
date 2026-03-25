"""Central constants for the Medici prediction engine.

All magic numbers are documented here with their purpose and source.
Change values here to tune the prediction engine without modifying code.
"""

# ── Prediction Engine ─────────────────────────────────────────────────

# Ensemble weights — how the 3 signals combine (must sum to 1.0)
# Historical Pattern inflates predictions via aggressive lead-time adjustment (+240%)
# Until lead-time formula is fixed, keep Historical at 10% to prevent all-CALL bias
ENSEMBLE_WEIGHT_FORWARD_CURVE = 0.70
ENSEMBLE_WEIGHT_HISTORICAL = 0.10
ENSEMBLE_WEIGHT_ML = 0.20

# Bayesian shrinkage prior strength (higher = more smoothing toward global mean)
BAYESIAN_K = 5

# Minimum daily volatility floor (%) — prevents zero-vol predictions
MIN_VOLATILITY = 0.5

# Maximum prediction horizon (days to check-in)
MAX_PREDICTION_HORIZON = 180

# Hard clamp bounds on ensemble price (fraction of current price)
# Hotel rooms don't jump 150% in weeks — max +50% is realistic for Miami market
PRICE_CLAMP_MIN = 0.50   # 50% of current price (max -50% drop)
PRICE_CLAMP_MAX = 1.50   # 150% of current price (max +50% rise)

# Sanity check bounds — blend toward current price if exceeded
# Triggers earlier to prevent Historical Pattern from inflating ensemble
SANITY_RATIO_HIGH = 1.40   # 1.4x current price → start blending
SANITY_RATIO_LOW = 0.60    # 0.6x current price → start blending
SANITY_PENALTY_FLOOR = 0.05  # Minimum penalty multiplier for outliers

# Outlier taming blend (when prediction exceeds sanity bounds)
OUTLIER_BLEND_PREDICTION = 0.2  # 20% predicted price
OUTLIER_BLEND_CURRENT = 0.8     # 80% current price
OUTLIER_CONFIDENCE_PENALTY = 0.3  # Confidence multiplied by this

# ── Data Density Thresholds ────────────────────────────────────────────

DATA_DENSITY_HIGH = 15     # ≥15 observations → "high" density
DATA_DENSITY_MEDIUM = 7    # ≥7 observations → "medium" density
MIN_DECAY_CURVE_ROWS = 50  # Minimum rows to build decay curve
MIN_T_OBSERVATIONS = 20    # Minimum T-observations for curve

# ── Confidence Scores ─────────────────────────────────────────────────

# Confidence by data density
CONFIDENCE_HIGH = 0.8
CONFIDENCE_MEDIUM = 0.6
CONFIDENCE_LOW = 0.4
CONFIDENCE_EXTRAPOLATED = 0.2

# Dynamic weight scaling: w = base_w * (WEIGHT_SCALE_BASE + WEIGHT_SCALE_CONF * confidence)
WEIGHT_SCALE_BASE = 0.5
WEIGHT_SCALE_CONF = 0.5

# ── Signal Generation ─────────────────────────────────────────────────

SIGNAL_THRESHOLD_HIGH = 0.70   # High-confidence CALL/PUT threshold
SIGNAL_THRESHOLD_MEDIUM = 0.60  # Medium-confidence threshold

# ── Enrichment Caps (daily % impact on forward curve) ──────────────────

# Demand (flights)
DEMAND_IMPACT_HIGH = 0.15    # HIGH demand → +0.15%/day
DEMAND_IMPACT_LOW = -0.15    # LOW demand → -0.15%/day

# Competitor pressure
COMPETITOR_IMPACT_MAX = 0.20  # ±0.20%/day max

# Cancellation risk
CANCELLATION_IMPACT_MAX = 0.25  # -0.25%/day max (always negative)

# Provider margin pressure
PROVIDER_IMPACT_MAX = 0.20   # ±0.20%/day max

# Seasonality
SEASONALITY_MULTIPLIER = 3.0  # Multiplier on (index - 1.0) for daily adjustment

# Momentum
MOMENTUM_DECAY_RATE = 0.15    # Exponential decay constant (~7-day half-life)
MOMENTUM_IMPACT_SCALE = 0.3   # Momentum impact multiplier

# Event impact windows
EVENT_RAMP_DAYS = 3   # Days before event to ramp impact
EVENT_TAPER_DAYS = 2  # Days after event to taper impact

# ── Extreme Outlier Caps ──────────────────────────────────────────────

# Daily % change caps for T-observations
DAILY_CHANGE_CAP = 10.0  # ±10% max daily change

# Confidence interval Z-score (95%)
CI_Z_SCORE = 1.96

# ── Data Collection ────────────────────────────────────────────────────

COLLECTION_INTERVAL = 3600  # 1 hour between collection cycles
DB_QUERY_TIMEOUT = 30       # Database query timeout (seconds)
API_TIMEOUT = 10            # External API timeout (seconds)

# ── Confidence Band Adjustment ─────────────────────────────────────────

CONFIDENCE_BAND_SPREAD = 0.3  # Band spread factor for multi-signal uncertainty
