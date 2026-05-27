"""
engine.py — MODULE 2: All Landau-de Gennes computations.
"""
import numpy as np


def compute_rolling_pca(returns, window):
    """
    BIOLOGICAL ANALOGY:
        In a nematic liquid crystal, measuring the Q-tensor is equivalent to
        measuring the second-moment tensor of molecular orientations. Rolling PCA
        on the financial correlation matrix is the exact analog: it extracts the
        dominant orientational mode (PC1) and its strength (lambda_1) from the
        "orientational distribution" of stock returns in N-dimensional space.

    FINANCIAL INTERPRETATION:
        Decomposes the rolling correlation matrix to find the dominant market
        factor (PC1 eigenvector = financial director) and the fraction of total
        variance it explains (lambda_1/N = order parameter S).

    MATHEMATICAL FORMULA:
        rho_ij(t) = Cov(r_i, r_j) / (sigma_i * sigma_j) over [t-window+1, t]
        rho = sum_k lambda_k v_k v_k^T   (eigenvalue decomposition)
        S(t) = lambda_1(t) / N

    NUMERICAL STABILITY NOTES:
        - The correlation matrix is always symmetric positive semi-definite.
        - np.linalg.eigh is used (not eig) for guaranteed real eigenvalues.
        - First window-1 entries have no valid PCA; lambda1_series is zero-padded.
        - Eigenvector sign convention is arbitrary; director rotation uses
          absolute-value dot product to handle sign flips.

    EXPECTED OUTPUT RANGES:
        lambda1_series: (T,) array, zero for t < window-1, then ~[1, N].
        v1_series: (T, N) array, unit-norm rows, zero for t < window-1.
        all_lambdas: (T, N) array, sorted descending per row.
    """
    T, N = returns.shape
    lambda1_series = np.zeros(T)
    v1_series = np.zeros((T, N))
    all_lambdas = np.zeros((T, N))

    for t in range(window - 1, T):
        block = returns[t - window + 1: t + 1]
        std = block.std(axis=0, ddof=1)
        std[std < 1e-12] = 1e-12
        z = (block - block.mean(axis=0)) / std
        corr = np.corrcoef(z, rowvar=False)
        corr = 0.5 * (corr + corr.T)
        vals, vecs = np.linalg.eigh(corr)
        idx = np.argsort(vals)[::-1]
        vals = vals[idx]
        vecs = vecs[:, idx]
        lambda1_series[t] = vals[0]
        v1_series[t] = vecs[:, 0]
        all_lambdas[t] = vals

    return lambda1_series, v1_series, all_lambdas


def compute_order_parameter(lambda1_series, n_stocks):
    """
    BIOLOGICAL ANALOGY:
        The scalar nematic order parameter S measures the degree of molecular
        alignment. S=0 means random orientations (isotropic phase); S=1 means
        perfect alignment (perfect nematic). For rod-like molecules, S ranges
        from 0 to 1, with typical nematic values of 0.3-0.7.

    FINANCIAL INTERPRETATION:
        S(t) = lambda_1(t)/N is the fraction of total variance explained by
        the dominant market factor. S~0.033 (1/30) means no dominant factor;
        S~0.40 means 40% of all variance is common — a crisis correlation state.

    MATHEMATICAL FORMULA:
        S(t) = lambda_1(t) / N
        Since Tr(rho) = N, sum of all eigenvalues = N, so S in [1/N, 1].

    NUMERICAL STABILITY NOTES:
        - lambda1_series is zero-padded for t < window-1, giving S=0 there.
        - n_stocks is the trace of the correlation matrix, guaranteeing S <= 1.

    EXPECTED OUTPUT RANGES:
        S_series: (T,) array in [0, 1]. Typical: 0.03-0.04 (normal),
        0.40-0.70 (crisis).
    """
    return lambda1_series / n_stocks


def compute_director_rotation(v1_series):
    """
    BIOLOGICAL ANALOGY:
        In liquid crystals, the director field n(r,t) can develop topological
        defects (disclinations) where the orientation changes discontinuously.
        The rotation angle delta_theta measures how much the director has turned
        between adjacent time steps — large jumps signal defect events.

    FINANCIAL INTERPRETATION:
        Measures the angular change in the PC1 eigenvector between consecutive
        days. A large delta_theta indicates a sector rotation event: the
        "market factor" has abruptly changed which stocks/sectors it loads on.
        This is the financial analog of a disclination in the director field.

    MATHEMATICAL FORMULA:
        delta_theta(t) = arccos(|v1(t)^T . v1(t-1)|)
        Range: [0, pi/2]. The absolute value handles the head-tail symmetry
        (v1 and -v1 are physically identical directors).

    NUMERICAL STABILITY NOTES:
        - CRITICAL: must use absolute value of dot product. Without it, an
          arbitrary eigenvector sign flip produces a false pi-radian spike.
        - np.clip the dot product to [-1, 1] before arccos to avoid NaN
          from floating-point roundoff.
        - First entry (t=0) is set to 0 (no previous director to compare).
        - Zero-padded vectors (before rolling window is full) are detected
          and set to 0.0 to prevent spurious pi/2 disclinations.

    EXPECTED OUTPUT RANGES:
        delta_theta: (T,) array in [0, pi/2] ≈ [0, 1.5708].
        Typical values: 0.01-0.05 rad/day. Disclination spikes: 0.3-1.0+ rad.
    """
    T = v1_series.shape[0]
    delta_theta = np.zeros(T)
    for t in range(1, T):
        # Skip zero-padded vectors (before rolling window is full)
        if np.all(v1_series[t] == 0) or np.all(v1_series[t - 1] == 0):
            delta_theta[t] = 0.0
            continue
        dot = np.dot(v1_series[t], v1_series[t - 1])
        dot = np.clip(abs(dot), -1.0, 1.0)
        delta_theta[t] = np.arccos(dot)
    return delta_theta


def compute_temperature(returns, window_beta, window_corr):
    """
    BIOLOGICAL ANALOGY:
        In statistical mechanics, temperature measures the mean kinetic energy
        of particles — the energy in random thermal motion. The financial
        temperature measures the mean-squared idiosyncratic return: the
        "thermal energy" in stock movements NOT explained by the common factor.

    FINANCIAL INTERPRETATION:
        T_fin(t) = cross-sectional mean of epsilon_i(t)^2, where epsilon_i
        is the residual after removing the market factor (equal-weighted
        portfolio). Low T_fin = stocks move together (nematic). High T_fin =
        stocks move independently (isotropic).

    MATHEMATICAL FORMULA:
        r_M(t) = (1/N) * sum_i r_i(t)                      (equal-weighted market)
        beta_i(t) = Cov_21(r_i, r_M) / Var_21(r_M)         (rolling beta)
        epsilon_i(t) = r_i(t) - beta_i(t) * r_M(t)         (idiosyncratic)
        T_fin(t) = (1/N) * sum_i epsilon_i(t)^2             (cross-section dispersion)

    NUMERICAL STABILITY NOTES:
        - Market return variance can be near-zero on calm days; clip Var(r_M)
          to minimum 1e-12 to prevent division by zero.
        - First window_beta-1 days have no beta; T_fin is zero-padded.
        - T_fin is a daily cross-sectional statistic, NOT a time-series average.
        - NOTE: The RAW output is in daily variance units (~1e-4). main.py
          applies a linear calibration to map this to the Landau temperature
          scale (T* ~ 0.008, T_NI ~ 0.048). This is equivalent to choosing
          temperature units — the physics is identical, only the scale changes.

    EXPECTED OUTPUT RANGES:
        T_fin_series: (T,) array, zero for t < window_beta-1.
        RAW values: typically [3e-5, 1e-3] for 18% annualized daily returns.
        After calibration in main.py: [0.003, 0.07] matching Landau scale.
    """
    T, N = returns.shape
    r_market = returns.mean(axis=1)
    T_fin_series = np.zeros(T)

    for t in range(window_beta - 1, T):
        rm_block = r_market[t - window_beta + 1: t + 1]
        var_rm = rm_block.var(ddof=1)
        var_rm = max(var_rm, 1e-12)

        betas = np.zeros(N)
        for i in range(N):
            ri_block = returns[t - window_beta + 1: t + 1, i]
            cov = np.cov(ri_block, rm_block, ddof=1)[0, 1]
            betas[i] = cov / var_rm

        eps = returns[t] - betas * r_market[t]
        T_fin_series[t] = np.mean(eps ** 2)

    return T_fin_series


def compute_ldg_coefficients(T_fin_series, a0, T_star):
    """
    BIOLOGICAL ANALOGY:
        The Landau coefficient A(T) = a0*(T - T*) controls the curvature of
        the free energy at the isotropic state (S=0). When A > 0, S=0 is a
        local minimum (stable isotropic). When A < 0, S=0 becomes unstable
        and the system must order (nematic phase).

    FINANCIAL INTERPRETATION:
        A(t) = a0*(T_fin(t) - T*) maps the financial temperature to the
        Landau coefficient. When idiosyncratic dispersion drops below T*,
        the isotropic (uncorrelated) market state becomes thermodynamically
        unstable — a crash correlation state is inevitable.

    MATHEMATICAL FORMULA:
        A(t) = a0 * (T_fin(t) - T*)
        Sign change at T_fin = T* (the isotropic spinodal).

    NUMERICAL STABILITY NOTES:
        - No division or other unstable operations; purely linear.
        - T_fin_series may contain zeros for early time steps; A will be
          negative there (T_fin=0 < T*), but these are masked by the
          rolling-window logic in downstream functions.

    EXPECTED OUTPUT RANGES:
        A_series: (T,) array. Typical: [-0.01, 0.10].
        Negative = below spinodal (deep nematic forced).
        Positive = isotropic stable or metastable.
    """
    return a0 * (T_fin_series - T_star)


def compute_free_energy_surface(S_grid, A_series, B, C):
    """
    BIOLOGICAL ANALOGY:
        In a nematic liquid crystal, this is the Helmholtz free energy landscape
        F(S) describing the orientational ordering of rod-like molecules. The double-
        well structure (when A < 0) is identical to the energy landscape of a magnetic
        domain: the molecules "want" to align (nematic well at S > 0) but are fighting
        thermal fluctuations (the barrier maintained by the cubic and quartic terms).

    FINANCIAL INTERPRETATION:
        F(S; t) is the "market configuration energy" — the free energy cost of the
        market being in a state with correlation order parameter S at time t. The global
        minimum of F at each t is the thermodynamic equilibrium. When this minimum
        jumps from S ≈ 0 (isotropic, uncorrelated) to S > 0 (nematic, correlated),
        a first-order phase transition has occurred: a correlation crash event.

    MATHEMATICAL FORMULA:
        F(S; t) = (1/2) * A(t) * S^2  -  (1/3) * B * S^3  +  (1/4) * C * S^4
        where A(t) = a0 * (T_fin(t) - T*)
        Stationary points: S[A(t) - B*S + C*S^2] = 0
        Non-trivial: S_± = (B ± sqrt(B² - 4CA(t))) / (2C)

    NUMERICAL STABILITY NOTES:
        - S_grid must include 0.0 as first element for isotropic minimum detection.
        - When A(t) > B²/(4C) = 0.09, no nematic minimum exists; S_± are complex.
          In this regime, only S=0 minimum exists. F is monotonically increasing for S>0.
        - When A(t) < 0 (T_fin < T*), the S=0 point becomes a local maximum.
          The deepest minimum is at S_+(t) >> S_NI.
        - No NaN or inf issues since F is a finite polynomial for finite S.
        - Use np.clip(S_grid, 0.0, 0.85) to prevent unphysical negative S values.

    EXPECTED OUTPUT RANGES:
        F values range from approximately -0.01 (deep nematic minimum during crisis)
        to +0.02 (energy barrier peak). Shape: (len(S_grid), len(A_series)).
        F(0, t) = 0 for all t (isotropic reference state has zero free energy by definition).
    """
    S = np.clip(S_grid, 0.0, 0.85)
    S2 = S ** 2
    S3 = S ** 3
    S4 = S ** 4
    F_surface = (0.5 * A_series[np.newaxis, :] * S2[:, np.newaxis]
                 - (1.0 / 3.0) * B * S3[:, np.newaxis]
                 + 0.25 * C * S4[:, np.newaxis])
    return F_surface


def compute_equilibrium_path(S_grid, F_surface):
    """
    BIOLOGICAL ANALOGY:
        The equilibrium path S*(t) traces the valley floor of the free energy
        landscape over time — it is the thermodynamically preferred order
        parameter at each temperature. In a first-order transition, this path
        jumps discontinuously at T_NI.

    FINANCIAL INTERPRETATION:
        S*(t) is the equilibrium market correlation level predicted by Landau
        theory given the current idiosyncratic temperature. When the actual
        S(t) deviates from S*(t), the market is out of equilibrium — either
        supercooled (too correlated) or superheated (too decorrelated).

    MATHEMATICAL FORMULA:
        S*(t) = argmin_{S in S_grid} F(S; t)
        Computed via grid search for robustness (avoids analytic branch issues).

    NUMERICAL STABILITY NOTES:
        - Uses np.argmin on the grid, which is always well-defined.
        - Returns S_grid[index] so the result is always a valid grid point.
        - When F is flat (early timesteps with A=0 and B≈0), returns S_grid[0]=0.

    EXPECTED OUTPUT RANGES:
        S_star_series: (T,) array in [0, 0.85]. Equals 0 during deep isotropic,
        jumps to ~0.40 at T_NI, increases to 0.55-0.70 in deep nematic.
    """
    n_T = F_surface.shape[1]
    S_star = np.zeros(n_T)
    for t in range(n_T):
        idx = np.argmin(F_surface[:, t])
        S_star[t] = S_grid[idx]
    return S_star


def compute_metastable_depth(S_grid, F_surface, S_star_series):
    """
    BIOLOGICAL ANALOGY:
        In a first-order transition, the system can be trapped in a metastable
        state separated from the true equilibrium by an energy barrier. The
        metastable well depth measures how far the metastable minimum is below
        the barrier — a deeper well means the system is more "stuck" in the
        wrong phase and requires a larger fluctuation to escape.

    FINANCIAL INTERPRETATION:
        When the nematic well exists but is not the global minimum, the market
        can be "trapped" in a correlated state even though thermodynamics
        says it should decorrelate. The well depth quantifies this fragility:
        a deep metastable nematic well means the market is one shock away
        from a correlation spike.

    MATHEMATICAL FORMULA:
        Find nematic local minimum (S > 0.05) on the F(S;t) grid.
        DeltaF_meta(t) = F(S=0) - F(S_nematic) = -F(S_nematic)
        Positive when nematic well is deeper than isotropic (fragility zone).
        Zero when no nematic local minimum exists.

    NUMERICAL STABILITY NOTES:
        - Local minimum detection: F[i] < F[i-1] AND F[i] < F[i+1].
        - The threshold S > 0.05 avoids misidentifying the isotropic minimum
          (at S≈0) as nematic.
        - Returns exactly 0.0 when no nematic minimum is found, avoiding
          spurious small values from numerical noise.

    EXPECTED OUTPUT RANGES:
        dF_meta_series: (T,) array, >= 0. Typical: 0.0 (no metastable well)
        to 0.008 (deep fragility during pretransitional zone).
    """
    n_S, n_T = F_surface.shape
    dF_meta = np.zeros(n_T)
    nematic_thresh = 0.05

    for t in range(n_T):
        F_t = F_surface[:, t]
        best_nem_F = np.inf
        for i in range(1, n_S - 1):
            if (S_grid[i] > nematic_thresh
                    and F_t[i] < F_t[i - 1]
                    and F_t[i] < F_t[i + 1]):
                if F_t[i] < best_nem_F:
                    best_nem_F = F_t[i]
        if np.isfinite(best_nem_F):
            dF_meta[t] = max(0.0, -best_nem_F)

    return dF_meta


def compute_supercooling(S_actual, S_star_series):
    """
    BIOLOGICAL ANALOGY:
        Supercooling occurs when a liquid remains in the liquid phase below
        its freezing point because the nucleation barrier prevents the
        transition. The supercooling deviation measures how far the system
        has gone past the equilibrium transition point without actually
        transitioning.

    FINANCIAL INTERPRETATION:
        S_excess(t) = S_actual(t) - S*(t). Positive means the market is
        more correlated than thermodynamic equilibrium predicts — it is
        "supercooled" in the nematic phase and could snap back to isotropic
        at any time. This is a measure of how far the market has gone past
        its equilibrium correlation level.

    MATHEMATICAL FORMULA:
        S_excess(t) = S_actual(t) - S*(t)

    NUMERICAL STABILITY NOTES:
        - Simple subtraction; no numerical issues.
        - Both inputs are bounded [0, ~0.85], so S_excess is bounded.

    EXPECTED OUTPUT RANGES:
        S_excess: (T,) array, typically [-0.3, +0.3].
        Positive = supercooled (too correlated for current temperature).
        Negative = below equilibrium (market hasn't caught up to rising correlations).
    """
    return S_actual - S_star_series


def detect_disclinations(delta_theta, threshold_percentile=90, min_index=0):
    """
    BIOLOGICAL ANALOGY:
        In liquid crystals, disclinations are topological defects where the
        director field rotates by a discrete amount (±1/2, ±1 winding number).
        Detection involves finding points where the director rotation rate
        exceeds a threshold — these are the defect cores.

    FINANCIAL INTERPRETATION:
        Detects sector rotation events: abrupt changes in the PC1 eigenvector
        direction. These are the financial analogs of disclinations — points
        where the "market factor" suddenly reorients from loading on one
        set of sectors to another.

    MATHEMATICAL FORMULA:
        threshold = percentile(delta_theta[valid], threshold_percentile)
        disclination_times = {t : delta_theta(t) > threshold AND t >= min_index}

    NUMERICAL STABILITY NOTES:
        - Only considers t >= max(1, min_index) (delta_theta[0] = 0 by definition).
        - min_index should be set to the rolling window size to exclude the
          zero-padded period where eigenvectors are not yet computed.
        - Percentile computed over all non-trivial values (>1e-6) to avoid
          dilution by the many near-zero entries.

    EXPECTED OUTPUT RANGES:
        disclination_times: 1D integer array of time indices.
        Typically 3-15 events for 756 trading days, depending on threshold.
    """
    start = max(1, min_index)
    valid = delta_theta[start:]
    if len(valid) == 0:
        return np.array([], dtype=int)
    nontrivial = valid[valid > 1e-6]
    if len(nontrivial) == 0:
        return np.array([], dtype=int)
    thresh = np.percentile(nontrivial, threshold_percentile)
    indices = np.where((delta_theta > thresh) &
                       (np.arange(len(delta_theta)) >= start))[0]
    return indices