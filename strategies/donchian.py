"""
Baseline v0.4 : breakout de Donchian (expérience 001). Pas une stratégie définitive.

À la clôture de i (bougies <= i seulement) :
  long  si close[i] > plus haut des N bougies PRÉCÉDENTES (i-N .. i-1)
  short si close[i] < plus bas  des N bougies précédentes
  stop  = stop_atr x ATR(20)[i]
  sortie d'un long  si close[i] < plus bas  des N/2 bougies précédentes (short : symétrique)
Pas d'objectif. Le moteur exécute tout à l'ouverture de i+1.
"""
import pandas as pd

from src.indicateurs import atr

NOM = "donchian_breakout"
ATR_N = 20
# Grille fixée AVANT le test (protocole v0.4, expérience 001) : 6 variantes, aucune autre.
GRILLE = [{"n": n, "stop_atr": s} for n in (20, 55, 100) for s in (2.0, 3.0)]


def signaux(df: pd.DataFrame, n: int, stop_atr: float) -> dict:
    haut = df["high"].rolling(n).max().shift(1)
    bas = df["low"].rolling(n).min().shift(1)
    m = n // 2
    haut_sortie = df["high"].rolling(m).max().shift(1)
    bas_sortie = df["low"].rolling(m).min().shift(1)
    c = df["close"]
    signal = (c > haut).astype(float) - (c < bas).astype(float)  # NaN (début) -> False -> 0
    return {"signal": signal, "stop_dist": atr(df, ATR_N) * stop_atr,
            "sortie_long": (c < bas_sortie).fillna(False), "sortie_short": (c > haut_sortie).fillna(False)}


def variante(p: dict):
    """Fonction de signal pour une variante de la grille (refuse toute variante hors grille)."""
    if p not in GRILLE:
        raise ValueError(f"variante hors grille fixée à l'avance : {p}")
    return lambda df: signaux(df, p["n"], p["stop_atr"])


def nom_variante(p: dict) -> str:
    return f"N{p['n']}_S{p['stop_atr']:g}"
