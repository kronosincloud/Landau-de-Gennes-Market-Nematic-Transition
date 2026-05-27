"""
visual.py — MODULE 3: Static 1920x1080 PNG.
Mirror Image Rule: this is the canonical layout that animate.py must reproduce.

NOTE: F_render passed here is -F_surface (negated). Hero lines are drawn as
2D figure overlays to bypass matplotlib 3D's painter's algorithm, which
cannot reliably render lines on top of full-resolution surfaces.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import proj3d
from config import CONFIG, THEME, CMAP_LDG


def _style_ax(ax):
    ax.set_facecolor(THEME["PANEL_BG"])
    for sp in ax.spines.values():
        sp.set_color(THEME["SPINE"])
        sp.set_linewidth(0.5)
    ax.tick_params(colors=THEME["TEXT_DIM"], labelsize=7,
                   direction="in", length=3)
    ax.yaxis.grid(True, color=THEME["GRID"], lw=0.3, alpha=0.4)


def _draw_3d_overlay(fig, ax3d, x3d, y3d, z3d, color, lw,
                     alpha=1.0, ls='-', marker='None', ms=0,
                     mec='white', mew=0.5):
    """
    Project 3D points to 2D figure coordinates and draw a Line2D overlay.
    Bypasses the 3D painter's algorithm — lines are ALWAYS visible.
    """
    M = ax3d.get_proj()
    x2, y2, _ = proj3d.proj_transform(
        np.asarray(x3d, dtype=float),
        np.asarray(y3d, dtype=float),
        np.asarray(z3d, dtype=float), M)
    pts = np.column_stack([x2, y2])
    disp = ax3d.transData.transform(pts)
    fig_frac = fig.transFigure.inverted().transform(disp)
    line = Line2D(fig_frac[:, 0], fig_frac[:, 1],
                  color=color, lw=lw, alpha=alpha, linestyle=ls,
                  marker=marker, markersize=ms,
                  markeredgecolor=mec, markeredgewidth=mew,
                  transform=fig.transFigure, figure=fig)
    fig.add_artist(line)
    return line


def render_png(S_grid, F_render, norm,
               S_actual, S_star_series,
               T_fin_series, dF_meta_series, delta_theta,
               disclination_indices, out_path):
    """
    Render the full static Bloomberg Multi-Panel Dashboard PNG.
    F_render: (n_S, T) = -F_surface (negated so minima are white-hot).
    norm: standard forward Normalize(vmin <= vmax).
    """
    T_total = CONFIG["T_TOTAL"]
    t_indices = np.arange(T_total)

    neg_F_at_S_star = np.zeros(T_total)
    neg_F_at_S_actual = np.zeros(T_total)
    for t in range(T_total):
        idx_s = np.argmin(np.abs(S_grid - S_star_series[t]))
        idx_a = np.argmin(np.abs(S_grid - S_actual[t]))
        neg_F_at_S_star[t] = F_render[idx_s, t]
        neg_F_at_S_actual[t] = F_render[idx_a, t]

    S_mesh, T_mesh = np.meshgrid(S_grid, t_indices, indexing="ij")

    fig = plt.figure(figsize=(CONFIG["FIG_W"], CONFIG["FIG_H"]),
                     dpi=CONFIG["DPI"], facecolor=THEME["BG"])
    fig.patch.set_facecolor(THEME["BG"])

    gs = GridSpec(4, 2, width_ratios=[2.2, 1],
                  left=0.05, right=0.97, top=0.87, bottom=0.07,
                  hspace=0.38, wspace=0.10, figure=fig)

    # ═══════════════ 3D SURFACE ═══════════════
    ax3d = fig.add_subplot(gs[:, 0], projection="3d")
    ax3d.set_facecolor(THEME["BG"])

    pane_color = (0.02, 0.02, 0.02, 1.0)
    for axis in (ax3d.xaxis, ax3d.yaxis, ax3d.zaxis):
        axis.set_pane_color(pane_color)
        axis._axinfo["grid"]["color"] = (0.13, 0.13, 0.13, 0.5)
        axis._axinfo["grid"]["linewidth"] = 0.35

    ax3d.plot_surface(
        S_mesh, T_mesh, F_render,
        cmap=CMAP_LDG, norm=norm,
        alpha=0.92, rstride=1, cstride=1,
        edgecolor=(1.0, 0.08, 0.58, 0.12),
        linewidth=0.25, antialiased=True, zorder=1,
    )

    z_floor = F_render.min() - 0.04
    ax3d.contourf(S_mesh, T_mesh, F_render,
                  zdir="z", offset=z_floor,
                  cmap=CMAP_LDG, norm=norm, alpha=0.45, levels=14)

    ax3d.set_xlabel("ORDER PARAMETER  S", fontsize=11, fontweight="bold",
                    color=THEME["TEXT_DIM"], labelpad=14,
                    fontfamily=THEME["FONT"])
    ax3d.set_ylabel("TIME  t  [days]", fontsize=11, fontweight="bold",
                    color=THEME["TEXT_DIM"], labelpad=14,
                    fontfamily=THEME["FONT"])
    ax3d.set_zlabel(r"$F(S,t)$  [a.u.]", fontsize=12, fontweight="bold",
                    color=THEME["TEXT_DIM"], labelpad=12,
                    fontfamily=THEME["FONT"])
    ax3d.set_box_aspect([1.5, 2.0, 0.8])
    ax3d.view_init(elev=28, azim=-52)
    ax3d.tick_params(axis="both", colors=THEME["TEXT_DIM"], labelsize=8)

    # ═══════════════ RIGHT PANELS ═══════════════
    ax_p1 = fig.add_subplot(gs[0, 1])
    _style_ax(ax_p1)
    ax_p1.plot(t_indices, S_actual, color=THEME["CYAN"], lw=1.4)
    ax_p1.axhline(CONFIG["S_NI"], color=THEME["ORANGE"], ls="--",
                  lw=1.0, alpha=0.7, label="NEMATIC TRANSITION")
    ax_p1.fill_between(t_indices, CONFIG["S_NI"], S_actual,
                       where=(S_actual > CONFIG["S_NI"]),
                       color=THEME["MAGENTA"], alpha=0.15)
    ax_p1.set_ylabel("S(t)", color=THEME["TEXT_DIM"], fontsize=9)
    ax_p1.set_title(r"ORDER PARAMETER  S(t) = $\lambda_1$/N",
                    color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                    fontfamily=THEME["FONT"])
    ax_p1.set_xlim(0, T_total)
    ax_p1.set_ylim(0, max(0.6, S_actual.max() * 1.15))
    leg = ax_p1.legend(loc="upper left", fontsize=7,
                       facecolor=THEME["BG"], edgecolor=THEME["GRID"])
    for txt in leg.get_texts():
        txt.set_color(THEME["TEXT_DIM"])

    ax_p2 = fig.add_subplot(gs[1, 1])
    _style_ax(ax_p2)
    ax_p2.plot(t_indices, T_fin_series, color=THEME["YELLOW"], lw=1.4)
    ax_p2.axhline(CONFIG["T_NI"], color=THEME["ORANGE"], ls="--",
                  lw=1.0, alpha=0.7, label=r"$T_{NI}$")
    ax_p2.axhline(CONFIG["T_STAR"], color=THEME["RED"], ls="--",
                  lw=1.0, alpha=0.7, label=r"$T^*$")
    ax_p2.axhspan(CONFIG["T_STAR"], CONFIG["T_NI"],
                  color=THEME["MAGENTA"], alpha=0.06)
    ax_p2.set_ylabel(r"$T_{fin}$", color=THEME["TEXT_DIM"], fontsize=9)
    ax_p2.set_title("IDIOSYNCRATIC TEMPERATURE  " + r"$T_{fin}(t)$",
                    color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                    fontfamily=THEME["FONT"])
    ax_p2.set_xlim(0, T_total)
    t_max_plot = max(0.08, T_fin_series.max() * 1.15)
    ax_p2.set_ylim(0, t_max_plot)
    leg2 = ax_p2.legend(loc="upper right", fontsize=7,
                        facecolor=THEME["BG"], edgecolor=THEME["GRID"])
    for txt in leg2.get_texts():
        txt.set_color(THEME["TEXT_DIM"])

    ax_p3 = fig.add_subplot(gs[2, 1])
    _style_ax(ax_p3)
    ax_p3.plot(t_indices, dF_meta_series, color=THEME["MAGENTA"], lw=1.3)
    ax_p3.fill_between(t_indices, 0, dF_meta_series,
                       color=THEME["MAGENTA"], alpha=0.18)
    ax_p3.axhline(0, color=THEME["TEXT_DIM"], lw=0.5, alpha=0.4)
    ax_p3.set_ylabel(r"$\Delta F_{meta}$", color=THEME["TEXT_DIM"],
                     fontsize=9)
    ax_p3.set_title("METASTABLE WELL DEPTH  " + r"$\Delta F_{meta}(t)$",
                    color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                    fontfamily=THEME["FONT"])
    ax_p3.set_xlim(0, T_total)
    dF_max = max(0.002, dF_meta_series.max() * 1.2)
    ax_p3.set_ylim(-dF_max * 0.1, dF_max)

    ax_p4 = fig.add_subplot(gs[3, 1])
    _style_ax(ax_p4)
    ax_p4.plot(t_indices, delta_theta, color=THEME["YELLOW"], lw=1.2)
    if len(disclination_indices) > 0:
        ax_p4.scatter(disclination_indices,
                      delta_theta[disclination_indices],
                      s=22, color=THEME["YELLOW"], marker="*", zorder=10)
    ax_p4.set_ylabel(r"$\delta\theta$", color=THEME["TEXT_DIM"], fontsize=9)
    ax_p4.set_xlabel("TIME  [days]", color=THEME["TEXT_DIM"], fontsize=9)
    ax_p4.set_title(r"DIRECTOR ROTATION  $|d\theta/dt|$  [rad/day]",
                    color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                    fontfamily=THEME["FONT"])
    ax_p4.set_xlim(0, T_total)
    dt_max = max(0.1, delta_theta.max() * 1.15)
    ax_p4.set_ylim(0, dt_max)

    # ═══════════════ TITLE BLOCK ═══════════════
    s_final = S_actual[-1]
    t_final = T_fin_series[-1]
    if s_final > CONFIG["S_NI"] and t_final < CONFIG["T_STAR"]:
        phase_str = "DEEP NEMATIC"
    elif s_final > CONFIG["S_NI"]:
        phase_str = "NEMATIC"
    elif t_final < CONFIG["T_NI"]:
        phase_str = "PRETRANSITIONAL"
    else:
        phase_str = "ISOTROPIC"
    n_discl = len(disclination_indices)

    fig.text(0.50, 0.960,
             "LANDAU-DE GENNES MARKET NEMATIC TRANSITION",
             ha="center", va="center",
             fontsize=26, fontweight="bold",
             color=THEME["ORANGE"], fontfamily=THEME["FONT"])
    fig.text(0.50, 0.932,
             f"$F(S,t)=\\frac{{1}}{{2}}A(t)S^2 - \\frac{{1}}{{3}}BS^3 "
             f"+ \\frac{{1}}{{4}}CS^4$"
             f"     $B={CONFIG['B_LDG']:.3f}$   $C={CONFIG['C_LDG']:.3f}$"
             f"   $S_{{NI}}={CONFIG['S_NI']:.3f}$   "
             f"$T^*={CONFIG['T_STAR']:.4f}$",
             ha="center", va="center",
             fontsize=11, color=THEME["TEXT_DIM"],
             fontfamily=THEME["FONT"])
    fig.text(0.96, 0.900,
             f"S_FINAL = {s_final:.3f}    T_FIN = {t_final:.4f}"
             f"    PHASE: {phase_str}    DISCLINATIONS: {n_discl:d}",
             ha="right", va="center",
             fontsize=10, fontweight="bold",
             color=THEME["YELLOW"], fontfamily=THEME["FONT"])
    fig.text(0.985, 0.010, CONFIG["WATERMARK"],
             ha="right", va="bottom", fontsize=10,
             color=THEME["TEXT_DIM"], fontfamily=THEME["FONT"], alpha=0.6)

    # ═══════════════ 2D OVERLAY: HERO LINES ═══════════════
    fig.canvas.draw()

    _draw_3d_overlay(fig, ax3d, S_star_series, t_indices,
                     neg_F_at_S_star, THEME["ORANGE"], 3.0, alpha=0.95)
    _draw_3d_overlay(fig, ax3d,
                     [S_star_series[-1]], [t_indices[-1]],
                     [neg_F_at_S_star[-1]],
                     THEME["YELLOW"], 0, marker='o', ms=6)

    _draw_3d_overlay(fig, ax3d, S_actual, t_indices,
                     neg_F_at_S_actual, THEME["CYAN"], 2.0, alpha=0.85)

    for idx in disclination_indices:
        _draw_3d_overlay(fig, ax3d,
                         [S_actual[idx]], [t_indices[idx]],
                         [neg_F_at_S_actual[idx]],
                         THEME["YELLOW"], 0, marker='*', ms=8,
                         mew=0.4)

    fig.savefig(out_path, dpi=CONFIG["DPI"], facecolor=THEME["BG"])
    plt.close(fig)
    print(f"  Saved: {out_path}")