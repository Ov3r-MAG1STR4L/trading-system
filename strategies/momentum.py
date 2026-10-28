"""
Expérience 002 : momentum en série temporelle (hypothèse : experiments/002-momentum-serie-temporelle/hypothese.md).

À la clôture de i (bougies <= i seulement) :
  r[i] = close[i] / close[i-L] - 1
  entrée UNIQUEMENT quand le signe de r change : long si r[i-1] <= 0 < r[i], short si r[i-1] >= 0 > r[i]
  stop = k x ATR(20)[i] (fixé à l'entrée par le moteur, jamais déplacé)
  sortie d'un long si r[i] <= 0, d'un short si r[i] >= 0
  pas d'objectif ; aucune entrée avant L + 20 bougies (chauffe)
Pas de réentrée après un stop sans nouveau changement de signe : le signal n'existe que sur la bougie du changement.
"""
import pandas as pd

from src.indicateurs import atr

NOM = "momentum_serie_temporelle"
ATR_N = 20
# Grille fixée AVANT le test (hypothèse 002) : 6 variantes, aucune autre.
GRILLE = [{"L": L, "k": k} for L in (60, 125, 250) for k in (3.0, 5.0)]


def signaux(df: pd.DataFrame, L: int, k: float) -> dict:
    r = df["close"] / df["close"].shift(L) - 1
    precedent = r.shift(1)
    long_ = (precedent <= 0) & (r > 0)   # NaN -> False : pas d'entrée sans r[i-1] et r[i] connus
    short = (precedent >= 0) & (r < 0)
    signal = long_.astype(float) - short.astype(float)
    signal.iloc[:L + ATR_N] = 0.0        # chauffe
    return {"signal": signal, "stop_dist": atr(df, ATR_N) * k,
            "sortie_long": (r <= 0).fillna(False), "sortie_short": (r >= 0).fillna(False)}


def variante(p: dict):
    """Fonction de signal pour une variante de la grille (refuse toute variante hors grille)."""
    if p not in GRILLE:
        raise ValueError(f"variante hors grille fixée à l'avance : {p}")
    return lambda df: signaux(df, p["L"], p["k"])


def nom_variante(p: dict) -> str:
    return f"L{p['L']}_K{p['k']:g}"
