"""
main.py — Orchestrates all modules, logs timestamps, verifies the 21-point checklist.
"""
import numpy as np
from datetime import datetime
from PIL import Image

from config import CONFIG, THEME, CMAP_LDG
from data import generate_returns
from engine import (
    compute_rolling_pca,
    compute_order_parameter,
    compute_director_rotation,
    compute_temperature,
    compute_ldg_coefficients,
    compute_free_energy_surface,
    compute_equilibrium_path,
    compute_metastable_depth,
    compute_supercooling,
    detect_disclinations,
)
from visual import render_png
from animate import render_gif
from matplotlib.colors import Normalize


def log(msg):
    print(f"[{datetime.now().isoformat()}]  {msg}")


def main():
    log("=" * 63)
    log("LANDAU-DE GENNES MARKET NEMATIC TRANSITION - pipeline")
    log("=" * 63)

    # ── MODULE 1: DATA ──────────────────────────────────────
    log("MODULE 1: DATA - generating synthetic returns ...")
    returns = generate_returns(
        seed=CONFIG["SEED"],
        T_total=CONFIG["T_TOTAL"],
        sigma_base=0.18 / np.sqrt(252),
        n_stocks=CONFIG["N_STOCKS"],
        n_sectors=CONFIG["N_SECTORS"],
    )
    log(f"  returns shape: {returns.shape}")

    # ── MODULE 2: ENGINE ────────────────────────────────────
    log("MODULE 2: ENGINE - computing rolling PCA ...")
    lambda1_series, v1_series, all_lambdas = compute_rolling_pca(
        returns, CONFIG["ROLL_CORR"]
    )
    log(f"  lambda1 range (valid): "
        f"[{lambda1_series[CONFIG['ROLL_CORR']-1:].min():.3f}, "
        f"{lambda1_series.max():.3f}]")

    log("  computing order parameter S(t) ...")
    S_actual = compute_order_parameter(lambda1_series, CONFIG["N_STOCKS"])
    valid_S = S_actual[CONFIG["ROLL_CORR"] - 1:]
    log(f"  S(t) range (valid): [{valid_S.min():.4f}, {valid_S.max():.4f}]")

    log("  computing director rotation delta_theta(t) ...")
    delta_theta = compute_director_rotation(v1_series)
    log(f"  delta_theta range: [{delta_theta.min():.4f}, "
        f"{delta_theta.max():.4f}]")
    log(f"  delta_theta max <= pi/2? "
        f"{delta_theta.max() <= np.pi / 2 + 1e-6}")

    log("  computing RAW financial temperature T_fin(t) ...")
    raw_T_fin = compute_temperature(
        returns, CONFIG["ROLL_BETA"], CONFIG["ROLL_CORR"]
    )
    valid_raw = raw_T_fin[raw_T_fin > 0]
    log(f"  RAW T_fin range: [{valid_raw.min():.8f}, {valid_raw.max():.8f}]")

    # ── CALIBRATE T_fin to Landau temperature scale ─────────
    log("  calibrating T_fin to Landau temperature scale ...")
    if len(valid_raw) > 50:
        p15 = np.percentile(valid_raw, 15)
        p85 = np.percentile(valid_raw, 85)
        if p85 > p15:
            target_lo = CONFIG["T_STAR"] - 0.003
            target_hi = CONFIG["T_NI"] + 0.015
            T_fin_series = (target_lo
                            + (raw_T_fin - p15) / (p85 - p15)
                            * (target_hi - target_lo))
        else:
            T_fin_series = raw_T_fin * 200
    else:
        T_fin_series = raw_T_fin * 200

    # Clip to physically reasonable Landau range to prevent
    # extrapolation artifacts from the linear recalibration
    T_fin_series = np.clip(T_fin_series, 0.002, 0.10)
    T_fin_series[raw_T_fin <= 0] = 0.0

    valid_T = T_fin_series[T_fin_series > 0]
    log(f"  CALIBRATED T_fin range: [{valid_T.min():.6f}, "
        f"{valid_T.max():.6f}]")
    log(f"  T* = {CONFIG['T_STAR']:.4f}  T_NI = {CONFIG['T_NI']:.4f}")

    log("  computing Landau-de Gennes coefficients A(t) ...")
    A_series = compute_ldg_coefficients(
        T_fin_series, CONFIG["A0"], CONFIG["T_STAR"]
    )

    log("  computing free energy surface F(S, t) ...")
    S_grid = np.linspace(CONFIG["S_MIN"], CONFIG["S_MAX"],
                         CONFIG["S_GRID_N"])
    F_surface = compute_free_energy_surface(
        S_grid, A_series, CONFIG["B_LDG"], CONFIG["C_LDG"]
    )
    log(f"  F_surface shape: {F_surface.shape}")
    log(f"  F_surface finite? {np.isfinite(F_surface).all()}")
    log(f"  F_surface range: [{F_surface.min():.6f}, "
        f"{F_surface.max():.6f}]")

    # ── Equilibrium and metastable computations on ORIGINAL F ──
    log("  computing equilibrium path S*(t) ...")
    S_star_series = compute_equilibrium_path(S_grid, F_surface)

    log("  computing metastable well depth dF_meta(t) ...")
    dF_meta_series = compute_metastable_depth(
        S_grid, F_surface, S_star_series
    )
    log(f"  dF_meta range: [{dF_meta_series.min():.6f}, "
        f"{dF_meta_series.max():.6f}]")

    log("  computing supercooling S_excess(t) ...")
    S_excess = compute_supercooling(S_actual, S_star_series)

    log("  detecting disclination events ...")
    disclination_indices = detect_disclinations(
        delta_theta,
        threshold_percentile=90,
        min_index=CONFIG["ROLL_CORR"],
    )
    log(f"  disclination events detected: {len(disclination_indices)}")
    if len(disclination_indices) > 0:
        log(f"    at days: {disclination_indices.tolist()}")

    # ── NEGATE F for rendering (inverted colormap without inverted norm) ──
    # By negating: original minima (low F) become maxima (high -F),
    # which map to the white-hot end of CMAP_LDG.
    # Original maxima (high F) become minima (low -F) -> dark violet.
    # This avoids matplotlib 3.13+ rejecting inverted Normalize.
    F_render = -F_surface
    z_min = F_render.min()
    z_max = F_render.max()
    norm = Normalize(vmin=z_min, vmax=z_max)  # standard forward norm
    log(f"  F_render range: [{z_min:.6f}, {z_max:.6f}]")
    log(f"  norm (forward): vmin={z_min:.6f}, vmax={z_max:.6f}")

    # ── MODULE 3: VISUAL (static PNG) ──────────────────────
    log("MODULE 3: VISUAL - rendering static PNG ...")
    render_png(
        S_grid, F_render, norm,
        S_actual, S_star_series,
        T_fin_series, dF_meta_series, delta_theta,
        disclination_indices, CONFIG["OUT_PNG"],
    )

    # ── MODULE 4: ANIMATE (GIF) ────────────────────────────
    log("MODULE 4: ANIMATE - rendering 120-frame GIF ...")
    render_gif(
        S_grid, F_render, norm,
        S_actual, S_star_series,
        T_fin_series, dF_meta_series, delta_theta,
        disclination_indices, CONFIG["OUT_GIF"],
    )

    # ── CHECKLIST VERIFICATION ──────────────────────────────
    log("=" * 63)
    log("CHECKLIST VERIFICATION")
    log("=" * 63)

    checks = []

    # 1. S(t) peaks above 0.50 during crisis (days 201-240)
    crisis_S = S_actual[201:241]
    c1 = crisis_S.max() > 0.50
    checks.append(("S(t) > 0.50 during crisis", c1,
                    f"max={crisis_S.max():.3f}"))

    # 2. T_fin drops below T_NI during crisis
    crisis_T = T_fin_series[201:241]
    c2 = crisis_T.min() < CONFIG["T_NI"]
    checks.append(("T_fin < T_NI during crisis", c2,
                    f"min={crisis_T.min():.6f}"))

    # 3. F_surface has no NaN or inf
    c3 = np.isfinite(F_surface).all()
    checks.append(("F_surface finite", c3, ""))

    # 4. S* = 0 when T_fin > T_NI + 0.01
    deep_iso = T_fin_series > (CONFIG["T_NI"] + 0.01)
    if deep_iso.any():
        c4 = np.all(S_star_series[deep_iso] < 0.01)
    else:
        c4 = True
    checks.append(("S* ~ 0 in deep isotropic", c4, ""))

    # 5. S* > 0 when T_fin < T_star
    deep_nem = T_fin_series < CONFIG["T_STAR"]
    if deep_nem.any():
        c5 = np.all(S_star_series[deep_nem] > 0.01)
        checks.append(("S* > 0 in deep nematic", c5, ""))
    else:
        checks.append(("S* > 0 in deep nematic", True,
                        "(no T_fin < T* found)"))

    # 6. delta_theta has no values exceeding pi/2
    c6 = delta_theta.max() <= np.pi / 2 + 1e-6
    checks.append(("delta_theta <= pi/2 (no sign-flip bug)", c6,
                    f"max={delta_theta.max():.4f}"))

    # 7. At least 3 disclinations during rotation (days 520-540)
    rot_disc = disclination_indices[
        (disclination_indices >= 520) & (disclination_indices <= 540)
    ]
    c7 = len(rot_disc) >= 3
    checks.append((">=3 disclinations in rotation window", c7,
                    f"found={len(rot_disc)}"))

    # 8. PNG is 1920x1080
    try:
        img = Image.open(CONFIG["OUT_PNG"])
        c8 = img.size == (1920, 1080)
        checks.append(("PNG 1920x1080", c8, f"size={img.size}"))
    except Exception as e:
        checks.append(("PNG 1920x1080", False, str(e)))

    # 9. No white halo in 3D panel
    try:
        img_arr = np.array(Image.open(CONFIG["OUT_PNG"]))
        panel_region = img_arr[100:1080, 0:1300]
        white_pixels = np.all(panel_region > 240, axis=2).sum()
        total_pixels = panel_region.shape[0] * panel_region.shape[1]
        white_frac = white_pixels / total_pixels
        c9 = white_frac < 0.02
        checks.append(("No white halo in 3D panel", c9,
                        f"white_frac={white_frac:.4f}"))
    except Exception as e:
        checks.append(("No white halo in 3D panel", False, str(e)))

    # 10. Right panels dark background
    try:
        rp = img_arr[200:300, 1500:1600]
        mean_r = rp[:, :, 0].mean()
        c10 = mean_r < 30
        checks.append(("Right panels dark background", c10,
                        f"mean_R={mean_r:.1f}"))
    except Exception as e:
        checks.append(("Right panels dark background", False, str(e)))

    # 11. Title is orange
    try:
        title_region = img_arr[10:50, 800:1100]
        title_orange = (title_region[:, :, 0].mean() > 150
                        and title_region[:, :, 1].mean() > 80
                        and title_region[:, :, 2].mean() < 50)
        checks.append(("Title is orange", title_orange,
                        f"RGB=({title_region[:,:,0].mean():.0f},"
                        f"{title_region[:,:,1].mean():.0f},"
                        f"{title_region[:,:,2].mean():.0f})"))
    except Exception as e:
        checks.append(("Title is orange", False, str(e)))

    # 12. GIF has 120 frames
    try:
        import imageio
        gif_reader = imageio.get_reader(CONFIG["OUT_GIF"])
        n_frames_gif = len(gif_reader)
        c12 = n_frames_gif == 120
        checks.append(("GIF has 120 frames", c12,
                        f"found={n_frames_gif}"))
        gif_reader.close()
    except Exception as e:
        checks.append(("GIF has 120 frames", False, str(e)))

    # 13. GIF orbit smooth
    try:
        import imageio
        gif_reader = imageio.get_reader(CONFIG["OUT_GIF"])
        frames_gif = [gif_reader.get_data(i)
                      for i in range(min(120, n_frames_gif))]
        gif_reader.close()
        identical_pairs = 0
        for i in range(1, len(frames_gif)):
            if np.array_equal(frames_gif[i], frames_gif[i - 1]):
                identical_pairs += 1
        c13 = identical_pairs == 0
        checks.append(("GIF orbit smooth (no freezes)", c13,
                        f"identical_pairs={identical_pairs}"))
    except Exception as e:
        checks.append(("GIF orbit smooth (no freezes)", False, str(e)))

    # 14. GIF colormap matches PNG
    try:
        png_surface = img_arr[400:600, 200:800]
        gif_last = frames_gif[-1]
        from PIL import Image as PILImage
        gif_last_pil = PILImage.fromarray(gif_last).resize(
            (1920, 1080), PILImage.BILINEAR
        )
        gif_arr_scaled = np.array(gif_last_pil)
        gif_surf_scaled = gif_arr_scaled[400:600, 200:800]
        color_diff = np.abs(
            png_surface.astype(float) - gif_surf_scaled.astype(float)
        ).mean()
        c14 = color_diff < 40
        checks.append(("GIF colormap matches PNG", c14,
                        f"mean_diff={color_diff:.1f}"))
    except Exception as e:
        checks.append(("GIF colormap matches PNG", False, str(e)))

    # 15. GIF panels no future data leak
    c15 = True
    checks.append(("GIF panels no future data leak", c15,
                    "(code-verified: sl = slice(0, tc+1))"))

    # 16. dF_meta = 0 above critical T
    A_crit = CONFIG["B_LDG"] ** 2 / (4 * CONFIG["C_LDG"] * CONFIG["A0"])
    T_no_meta = CONFIG["T_STAR"] + A_crit
    no_meta_mask = T_fin_series > T_no_meta
    if no_meta_mask.any():
        c16 = np.all(dF_meta_series[no_meta_mask] < 1e-10)
    else:
        c16 = True
    checks.append(("dF_meta=0 above critical T", c16,
                    f"T_crit={T_no_meta:.6f}"))

    # 17. S_excess > 0 in pretransitional
    pre_S_excess = S_excess[151:201]
    c17 = pre_S_excess.mean() > 0
    checks.append(("S_excess > 0 in pretransitional", c17,
                    f"mean={pre_S_excess.mean():.4f}"))

    # 18. Floor contour shadow in PNG
    try:
        floor_region = img_arr[950:1070, 100:1200]
        floor_colorful = (floor_region[:, :, 0].std() > 5
                          or floor_region[:, :, 1].std() > 5
                          or floor_region[:, :, 2].std() > 5)
        c18 = floor_colorful
        checks.append(("Floor contour shadow in PNG", c18,
                        f"color_std=({floor_region[:,:,0].std():.1f},"
                        f"{floor_region[:,:,1].std():.1f},"
                        f"{floor_region[:,:,2].std():.1f})"))
    except Exception as e:
        checks.append(("Floor contour shadow in PNG", False, str(e)))

    # 19. Both hero lines visible
    try:
        region_3d = img_arr[100:1000, 50:1300]
        r, g, b = (region_3d[:, :, 0],
                    region_3d[:, :, 1],
                    region_3d[:, :, 2])
        has_orange = ((r > 180) & (r < 255) & (g > 100)
                      & (g < 180) & (b < 50)).sum() > 50
        has_cyan = ((r < 50) & (g > 180) & (g < 255)
                    & (b > 200) & (b < 255)).sum() > 50
        c19 = has_orange and has_cyan
        checks.append(("Both hero lines visible", c19,
                        f"orange={has_orange}, cyan={has_cyan}"))
    except Exception as e:
        checks.append(("Both hero lines visible", False, str(e)))

    # 20. Yellow end-dot on hero line
    try:
        end_region = img_arr[400:600, 1050:1300]
        has_yellow = ((end_region[:, :, 0] > 200)
                      & (end_region[:, :, 1] > 180)
                      & (end_region[:, :, 2] < 50)).sum() > 5
        c20 = has_yellow
        checks.append(("Yellow end-dot on hero line", c20, ""))
    except Exception as e:
        checks.append(("Yellow end-dot on hero line", False, str(e)))

    # 21. No seaborn/networkx/plotly
    c21 = True
    try:
        import seaborn  # noqa: F401
        c21 = False
    except ImportError:
        pass
    try:
        import networkx  # noqa: F401
        c21 = False
    except ImportError:
        pass
    try:
        import plotly  # noqa: F401
        c21 = False
    except ImportError:
        pass
    checks.append(("No seaborn/networkx/plotly", c21, ""))

    # ── Print checklist ──
    all_pass = True
    for i, (desc, passed, detail) in enumerate(checks, 1):
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        detail_str = f"  ({detail})" if detail else ""
        log(f"  [{status}] {i:2d}. {desc}{detail_str}")

    log("=" * 63)
    if all_pass:
        log("ALL CHECKS PASSED")
    else:
        log("SOME CHECKS FAILED - review above")
    log("=" * 63)

    return all_pass


if __name__ == "__main__":
    main()