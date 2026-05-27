"""
data.py — MODULE 1: Generate synthetic return matrix with regime injections.
Uses Cholesky-correlated Gaussian returns with GARCH(1,1) volatility scaling.
"""
import numpy as np
from config import CONFIG

SECTOR_LABELS = [
    "Technology", "Financials", "Healthcare",
    "Energy", "ConsumerDisc", "Industrials",
]

# Regime schedule: (t_start, t_end, rho_within, rho_across, sigma_mult, extra)
# extra: None | dict{sector_idx: boost} | "rotation"
REGIME_SCHEDULE = [
    (0,   150, 0.35, 0.20, 1.0, None),
    (151, 200, 0.50, 0.38, 1.0, None),
    (201, 240, 0.72, 0.60, 2.0, None),
    (241, 350, 0.40, 0.25, 1.2, None),
    (351, 399, 0.35, 0.20, 1.0, None),
    (400, 500, 0.48, 0.35, 1.0, None),
    (501, 519, 0.30, 0.20, 1.0, {1: 0.25}),
    (520, 540, 0.30, 0.20, 1.0, "rotation"),
    (541, 599, 0.30, 0.20, 1.0, {0: 0.25}),
    (600, 700, 0.65, 0.55, 1.8, None),
    (701, 755, 0.35, 0.20, 1.0, None),
]


def generate_corr_regime(rho_within, rho_across, n_stocks=30, n_sectors=6):
    """
    Build block-structured N×N correlation matrix.
    rho_within: float or array-like of length n_sectors (per-sector within-correlation).
    rho_across: float (cross-sector correlation).
    Returns: (n_stocks, n_stocks) positive-definite correlation matrix.
    """
    stocks_per = n_stocks // n_sectors
    if np.isscalar(rho_within):
        rho_w = np.full(n_sectors, float(rho_within))
    else:
        rho_w = np.asarray(rho_within, dtype=float)
    corr = np.full((n_stocks, n_stocks), float(rho_across))
    np.fill_diagonal(corr, 1.0)
    for s in range(n_sectors):
        i0, i1 = s * stocks_per, (s + 1) * stocks_per
        corr[i0:i1, i0:i1] = rho_w[s]
        np.fill_diagonal(corr[i0:i1, i0:i1], 1.0)
    # Tiny diagonal nudge for numerical Cholesky stability
    corr += np.eye(n_stocks) * 1e-10
    return corr


def _get_corr_and_mult(t, regime_schedule, n_stocks, n_sectors):
    """Return (corr_matrix, sigma_multiplier) for time index t."""
    stocks_per = n_stocks // n_sectors
    rho_w = np.full(n_sectors, 0.35)
    rho_a = 0.20
    sm = 1.0

    for (ts, te, rw, ra, sml, extra) in regime_schedule:
        if ts <= t <= te:
            if np.isscalar(rw):
                rho_w[:] = rw
            rho_a = ra
            sm = sml
            if isinstance(extra, dict):
                for sec, boost in extra.items():
                    rho_w[sec] += boost
            elif extra == "rotation":
                frac = (t - ts) / max(1, te - ts)
                rho_w[1] = 0.30 + 0.25 * (1.0 - frac)
                rho_w[0] = 0.30 + 0.25 * frac
            break

    corr = generate_corr_regime(rho_w, rho_a, n_stocks, n_sectors)
    return corr, sm


def generate_returns(seed=42, T_total=756, regime_schedule=None,
                     sigma_base=None, n_stocks=30, n_sectors=6):
    """
    Generate (T_total, n_stocks) return matrix using Cholesky-correlated
    Gaussian shocks scaled by GARCH(1,1) volatility and regime-dependent
    correlation structure.
    """
    if regime_schedule is None:
        regime_schedule = REGIME_SCHEDULE
    if sigma_base is None:
        sigma_base = 0.18 / np.sqrt(252)

    rng = np.random.default_rng(seed)
    returns = np.zeros((T_total, n_stocks))

    # ── GARCH(1,1) variance path from INDEPENDENT shocks (Trap 4 fix) ──
    omega_g, alpha_g, beta_g = 1e-5, 0.10, 0.85
    sigma2_0 = sigma_base ** 2
    garch_z = rng.standard_normal(T_total)
    sigma2_path = np.full(T_total, sigma2_0)
    for t in range(1, T_total):
        sigma2_path[t] = (omega_g
                          + alpha_g * garch_z[t - 1] ** 2 * sigma2_path[t - 1]
                          + beta_g * sigma2_path[t - 1])
        sigma2_path[t] = np.clip(sigma2_path[t],
                                 sigma2_0 * 0.1, sigma2_0 * 100.0)
    garch_scale = np.sqrt(sigma2_path / sigma2_0)

    # ── Generate correlated returns per timestep ──
    for t in range(T_total):
        corr_t, sm = _get_corr_and_mult(t, regime_schedule, n_stocks, n_sectors)
        L = np.linalg.cholesky(corr_t)
        z = rng.standard_normal(n_stocks)
        returns[t] = (L @ z) * sigma_base * sm * garch_scale[t]

    return returns


if __name__ == "__main__":
    from datetime import datetime
    print(f"[{datetime.now().isoformat()}] data.py — generating returns …")
    ret = generate_returns(seed=CONFIG["SEED"], T_total=CONFIG["T_TOTAL"])
    print(f"  returns shape: {ret.shape}")
    print(f"  daily mean abs return: {np.abs(ret).mean():.6f}")
    print(f"  max single-day return: {ret.max():.4f}")
    print(f"  min single-day return: {ret.min():.4f}")

    # Quick rolling-PCA check
    from engine import compute_rolling_pca, compute_order_parameter
    lam1, _, _ = compute_rolling_pca(ret, CONFIG["ROLL_CORR"])
    S = compute_order_parameter(lam1, CONFIG["N_STOCKS"])
    valid = S[CONFIG["ROLL_CORR"] - 1:]
    print(f"  S(t) range (valid): [{valid.min():.3f}, {valid.max():.3f}]")
    crisis_slice = valid[201 - CONFIG["ROLL_CORR"] + 1:241 - CONFIG["ROLL_CORR"] + 1]
    if len(crisis_slice) > 0:
        print(f"  S(t) during crisis (days 201-240): mean={crisis_slice.mean():.3f}  max={crisis_slice.max():.3f}")
    normal_slice = valid[:150 - CONFIG["ROLL_CORR"] + 1]
    if len(normal_slice) > 0:
        print(f"  S(t) during normal (days 63-150): mean={normal_slice.mean():.3f}  max={normal_slice.max():.3f}")
    print(f"[{datetime.now().isoformat()}] data.py — done.")