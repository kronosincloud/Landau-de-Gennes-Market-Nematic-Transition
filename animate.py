"""
animate.py — MODULE 4: 120-frame GIF following GROW/HOLD/ORBIT structure.
Mirror Image Rule: exact same layout, norm, and title block as visual.py.
Hero lines drawn as 2D overlays to bypass 3D painter's algorithm.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import proj3d
import imageio
from config import CONFIG, THEME, CMAP_LDG


def _canvas_to_rgb(fig):
    fig.canvas.draw()
    try:
        return np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
    except AttributeError:
        w, h = fig.canvas.get_width_height()
        return np.frombuffer(fig.canvas.tostring_rgb(),
                             dtype=np.uint8).reshape(h, w, 3)


def _ease_quintic(x):
    x = np.clip(x, 0.0, 1.0)
    return 6 * x ** 5 - 15 * x ** 4 + 10 * x ** 3


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
    """Project 3D points to 2D figure coordinates and draw overlay."""
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


def _get_phase_label(s_actual, t_fin):
    if s_actual > CONFIG["S_NI"] and t_fin < CONFIG["T_STAR"]:
        return "DEEP NEMATIC"
    elif s_actual > CONFIG["S_NI"]:
        return "NEMATIC"
    elif t_fin < CONFIG["T_NI"]:
        return "PRETRANSITIONAL"
    return "ISOTROPIC"


def render_gif(S_grid, F_render, norm,
               S_actual, S_star_series,
               T_fin_series, dF_meta_series, delta_theta,
               disclination_indices, out_path):
    N_grow, N_hold, N_orbit = 45, 20, 55
    total_frames = N_grow + N_hold + N_orbit
    N_t = CONFIG["T_TOTAL"]
    t_indices = np.arange(N_t)

    neg_F_at_S_star = np.zeros(N_t)
    neg_F_at_S_actual = np.zeros(N_t)
    for t in range(N_t):
        idx_s = np.argmin(np.abs(S_grid - S_star_series[t]))
        idx_a = np.argmin(np.abs(S_grid - S_actual[t]))
        neg_F_at_S_star[t] = F_render[idx_s, t]
        neg_F_at_S_actual[t] = F_render[idx_a, t]

    S_mesh, T_mesh = np.meshgrid(S_grid, t_indices, indexing="ij")

    schedule = []
    for i in range(N_grow):
        raw = i / max(1, N_grow - 1)
        eased = _ease_quintic(raw)
        tc = max(2, int(eased * N_t))
        schedule.append({
            "phase": "GROW", "tc": tc,
            "elev": 5 + 23 * eased,
            "azim": -70 + 18 * eased,
        })
    for i in range(N_hold):
        schedule.append({
            "phase": "HOLD", "tc": N_t,
            "elev": 28 + 2 * np.sin(2 * np.pi * i / N_hold),
            "azim": -52 + 5 * (i / N_hold),
        })
    hold_end_azim = -52 + 5 * ((N_hold - 1) / N_hold)
    hold_end_elev = 28 + 2 * np.sin(2 * np.pi * (N_hold - 1) / N_hold)
    for orb_prog in np.linspace(0.0, 1.0, N_orbit):
        schedule.append({
            "phase": "ORBIT", "tc": N_t,
            "elev": hold_end_elev + 18 * np.sin(np.pi * orb_prog * 1.3),
            "azim": hold_end_azim + 360.0 * orb_prog,
        })

    phase_colors = {"GROW": THEME["ORANGE"],
                    "HOLD": THEME["YELLOW"],
                    "ORBIT": THEME["CYAN"]}

    frames = []
    for fi, sched in enumerate(schedule):
        tc = sched["tc"]
        elev = sched["elev"]
        azim = sched["azim"]

        fig = plt.figure(figsize=(19.2, 10.8), dpi=80,
                         facecolor=THEME["BG"])
        fig.patch.set_facecolor(THEME["BG"])

        gs = GridSpec(4, 2, width_ratios=[2.2, 1],
                      left=0.05, right=0.97, top=0.87, bottom=0.07,
                      hspace=0.38, wspace=0.10, figure=fig)

        ax3d = fig.add_subplot(gs[:, 0], projection="3d")
        ax3d.set_facecolor(THEME["BG"])

        pane_color = (0.02, 0.02, 0.02, 1.0)
        for axis in (ax3d.xaxis, ax3d.yaxis, ax3d.zaxis):
            axis.set_pane_color(pane_color)
            axis._axinfo["grid"]["color"] = (0.13, 0.13, 0.13, 0.5)
            axis._axinfo["grid"]["linewidth"] = 0.35

        sl = slice(0, tc + 1)
        ax3d.plot_surface(
            S_mesh[:, sl], T_mesh[:, sl], F_render[:, sl],
            cmap=CMAP_LDG, norm=norm,
            alpha=0.92, rstride=1, cstride=1,
            edgecolor=(1.0, 0.08, 0.58, 0.12),
            linewidth=0.25, antialiased=True, zorder=1,
        )

        if tc > 10:
            z_floor = F_render.min() - 0.04
            ax3d.contourf(S_mesh[:, sl], T_mesh[:, sl], F_render[:, sl],
                          zdir="z", offset=z_floor,
                          cmap=CMAP_LDG, norm=norm,
                          alpha=0.45, levels=14)

        ax3d.set_xlabel("ORDER PARAMETER  S", fontsize=11,
                        fontweight="bold", color=THEME["TEXT_DIM"],
                        labelpad=14, fontfamily=THEME["FONT"])
        ax3d.set_ylabel("TIME  t  [days]", fontsize=11,
                        fontweight="bold", color=THEME["TEXT_DIM"],
                        labelpad=14, fontfamily=THEME["FONT"])
        ax3d.set_zlabel(r"$F(S,t)$  [a.u.]", fontsize=12,
                        fontweight="bold", color=THEME["TEXT_DIM"],
                        labelpad=12, fontfamily=THEME["FONT"])
        ax3d.set_box_aspect([1.5, 2.0, 0.8])
        ax3d.view_init(elev=elev, azim=azim)
        ax3d.tick_params(axis="both", colors=THEME["TEXT_DIM"],
                         labelsize=8)

        # ── Right panels ──
        ax_p1 = fig.add_subplot(gs[0, 1])
        _style_ax(ax_p1)
        ax_p1.plot(t_indices[:tc], S_actual[:tc],
                   color=THEME["CYAN"], lw=1.4)
        ax_p1.axhline(CONFIG["S_NI"], color=THEME["ORANGE"], ls="--",
                      lw=1.0, alpha=0.7)
        ax_p1.fill_between(t_indices[:tc], CONFIG["S_NI"],
                           S_actual[:tc],
                           where=(S_actual[:tc] > CONFIG["S_NI"]),
                           color=THEME["MAGENTA"], alpha=0.15)
        ax_p1.set_xlim(0, N_t)
        ax_p1.set_ylim(0, max(0.6, S_actual.max() * 1.15))
        ax_p1.set_title(r"ORDER PARAMETER  S(t) = $\lambda_1$/N",
                        color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                        fontfamily=THEME["FONT"])

        ax_p2 = fig.add_subplot(gs[1, 1])
        _style_ax(ax_p2)
        ax_p2.plot(t_indices[:tc], T_fin_series[:tc],
                   color=THEME["YELLOW"], lw=1.4)
        ax_p2.axhline(CONFIG["T_NI"], color=THEME["ORANGE"], ls="--",
                      lw=1.0, alpha=0.7)
        ax_p2.axhline(CONFIG["T_STAR"], color=THEME["RED"], ls="--",
                      lw=1.0, alpha=0.7)
        ax_p2.axhspan(CONFIG["T_STAR"], CONFIG["T_NI"],
                      color=THEME["MAGENTA"], alpha=0.06)
        ax_p2.set_xlim(0, N_t)
        t_max_p = max(0.08, T_fin_series.max() * 1.15)
        ax_p2.set_ylim(0, t_max_p)
        ax_p2.set_title("IDIOSYNCRATIC TEMPERATURE",
                        color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                        fontfamily=THEME["FONT"])

        ax_p3 = fig.add_subplot(gs[2, 1])
        _style_ax(ax_p3)
        ax_p3.plot(t_indices[:tc], dF_meta_series[:tc],
                   color=THEME["MAGENTA"], lw=1.3)
        ax_p3.fill_between(t_indices[:tc], 0, dF_meta_series[:tc],
                           color=THEME["MAGENTA"], alpha=0.18)
        ax_p3.axhline(0, color=THEME["TEXT_DIM"], lw=0.5, alpha=0.4)
        ax_p3.set_xlim(0, N_t)
        dF_max_p = max(0.002, dF_meta_series.max() * 1.2)
        ax_p3.set_ylim(-dF_max_p * 0.1, dF_max_p)
        ax_p3.set_title("METASTABLE WELL DEPTH",
                        color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                        fontfamily=THEME["FONT"])

        ax_p4 = fig.add_subplot(gs[3, 1])
        _style_ax(ax_p4)
        ax_p4.plot(t_indices[:tc], delta_theta[:tc],
                   color=THEME["YELLOW"], lw=1.2)
        disc_now = disclination_indices[disclination_indices < tc]
        if len(disc_now) > 0:
            ax_p4.scatter(disc_now, delta_theta[disc_now],
                          s=22, color=THEME["YELLOW"], marker="*",
                          zorder=10)
        ax_p4.set_xlim(0, N_t)
        dt_max_p = max(0.1, delta_theta.max() * 1.15)
        ax_p4.set_ylim(0, dt_max_p)
        ax_p4.set_title(r"DIRECTOR ROTATION  $|d\theta/dt|$  [rad/day]",
                        color=THEME["TEXT_DIM"], fontsize=8, pad=3,
                        fontfamily=THEME["FONT"])

        # ── Title block ──
        tc_idx = max(0, tc - 1)
        s_now = S_actual[tc_idx]
        t_now = T_fin_series[tc_idx]
        ph = _get_phase_label(s_now, t_now)
        n_disc_now = len(disc_now)

        fig.text(0.50, 0.960,
                 "LANDAU-DE GENNES MARKET NEMATIC TRANSITION",
                 ha="center", va="center",
                 fontsize=26, fontweight="bold",
                 color=THEME["ORANGE"],
                 fontfamily=THEME["FONT"])
        fig.text(0.50, 0.932,
                 f"$F(S,t)=\\frac{{1}}{{2}}A(t)S^2 - "
                 f"\\frac{{1}}{{3}}BS^3 + \\frac{{1}}{{4}}CS^4$"
                 f"     $B={CONFIG['B_LDG']:.3f}$   "
                 f"$C={CONFIG['C_LDG']:.3f}$"
                 f"   $S_{{NI}}={CONFIG['S_NI']:.3f}$   "
                 f"$T^*={CONFIG['T_STAR']:.4f}$",
                 ha="center", va="center",
                 fontsize=11, color=THEME["TEXT_DIM"],
                 fontfamily=THEME["FONT"])
        fig.text(0.96, 0.900,
                 f"S={s_now:.3f}    T_FIN={t_now:.4f}"
                 f"    PHASE: {ph}    DISCL: {n_disc_now:d}",
                 ha="right", va="center",
                 fontsize=10, fontweight="bold",
                 color=THEME["YELLOW"],
                 fontfamily=THEME["FONT"])
        fig.text(0.985, 0.010, CONFIG["WATERMARK"],
                 ha="right", va="bottom", fontsize=10,
                 color=THEME["TEXT_DIM"],
                 fontfamily=THEME["FONT"], alpha=0.6)

        # ── Progress bar ──
        bar_color = phase_colors[sched["phase"]]
        ax_bar = fig.add_axes([0.05, 0.015, 0.92, 0.005])
        ax_bar.set_xlim(0, 1)
        ax_bar.set_ylim(0, 1)
        ax_bar.barh(0.5, fi / total_frames, height=1.0,
                    color=bar_color, align="center")
        ax_bar.set_facecolor(THEME["BG"])
        ax_bar.set_xticks([])
        ax_bar.set_yticks([])
        for sp in ax_bar.spines.values():
            sp.set_visible(False)

        # ASCII-safe phase labels (Arial has no Unicode block for these glyphs)
        phase_label = {"GROW": ">> GROW",
                       "HOLD": "|| HOLD",
                       "ORBIT": "~~ ORBIT"}[sched["phase"]]
        fig.text(0.06, 0.008, phase_label, ha="left", va="bottom",
                 fontsize=9, color=THEME["TEXT_DIM"],
                 fontfamily=THEME["FONT"])

        # ═══════════════ 2D OVERLAY: HERO LINES ═══════════════
        fig.canvas.draw()

        _draw_3d_overlay(fig, ax3d,
                         S_star_series[:tc], t_indices[:tc],
                         neg_F_at_S_star[:tc],
                         THEME["ORANGE"], 3.0, alpha=0.95)
        if tc > 0:
            _draw_3d_overlay(fig, ax3d,
                             [S_star_series[tc - 1]], [t_indices[tc - 1]],
                             [neg_F_at_S_star[tc - 1]],
                             THEME["YELLOW"], 0, marker='o', ms=6)
        _draw_3d_overlay(fig, ax3d,
                         S_actual[:tc], t_indices[:tc],
                         neg_F_at_S_actual[:tc],
                         THEME["CYAN"], 2.0, alpha=0.85)
        for idx in disc_now:
            _draw_3d_overlay(fig, ax3d,
                             [S_actual[idx]], [t_indices[idx]],
                             [neg_F_at_S_actual[idx]],
                             THEME["YELLOW"], 0, marker='*', ms=8,
                             mew=0.4)

        frames.append(_canvas_to_rgb(fig))
        plt.close(fig)

        if (fi + 1) % 10 == 0:
            print(f"    frame {fi + 1}/{total_frames}  "
                  f"({sched['phase']} tc={tc})")

    imageio.mimsave(out_path, frames, fps=10, loop=0)
    print(f"  Saved: {out_path}")