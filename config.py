"""
config.py — Theme, Landau-de Gennes parameters, colormaps, CONFIG dict.
"""
import matplotlib
matplotlib.use("Agg")
from matplotlib.colors import LinearSegmentedColormap

THEME = {
    "BG":           "#000000",
    "PANEL_BG":     "#0a0a0a",
    "GRID":         "#1a1a1a",
    "SPINE":        "#333333",
    "TEXT":         "#ffffff",
    "TEXT_DIM":     "#aaaaaa",
    "ORANGE":       "#ff9500",
    "ORANGE_HOT":   "#ff6b00",
    "CYAN":         "#00f2ff",
    "YELLOW":       "#ffd400",
    "GREEN":        "#00ff41",
    "RED":          "#ff3050",
    "MAGENTA":      "#ff1493",
    "PINK":         "#ff2a9e",
    "BLUE":         "#00bfff",
    "FONT":         "Arial",
}

CONFIG = {
    "N_STOCKS":     30,
    "N_SECTORS":    6,
    "T_TOTAL":      756,
    "ROLL_CORR":    63,
    "ROLL_BETA":    21,
    "S_GRID_N":     80,
    "S_MIN":        0.0,
    "S_MAX":        0.85,
    "DPI":          100,
    "FIG_W":        19.2,
    "FIG_H":        10.8,
    "OUT_PNG":      "ldg_nematic_transition.png",
    "OUT_GIF":      "ldg_nematic_transition.gif",
    "A0":           2.0,
    "B_LDG":        0.600,
    "C_LDG":        1.000,
    "T_STAR":       0.008,
    "S_NI":         0.400,
    "T_NI":         0.048,
    "WATERMARK":    "@Laksh",
    "FONT":         "Arial",
    "SEED":         42,
}

# Custom colormap: valleys (minima) = white-hot, barriers (peaks) = deep violet
CMAP_LDG = LinearSegmentedColormap.from_list("ldg_energy", [
    "#200040",
    "#8B0080",
    "#ff1493",
    "#ff9500",
    "#ffd400",
    "#ffffff",
])

if __name__ == "__main__":
    print("config.py loaded successfully")
    print(f"  T_NI  = {CONFIG['T_NI']}")
    print(f"  S_NI  = {CONFIG['S_NI']}")
    print(f"  T*    = {CONFIG['T_STAR']}")
    print(f"  CMAP  = {CMAP_LDG.name} ({len(CMAP_LDG.colors)} stops)")