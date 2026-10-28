"""
Expérience 003 : retournement à court terme après une séance extrême (proposition validée :
docs/proposition-experience-003.md).

À la clôture de la séance s (bougies <= s seulement) :
  m[s] = (close[s] - close[s-1]) / ATR20[s-1]     ATR arrêté la VEILLE : la séance extrême ne gonfle pas sa mesure
  long  si m[s] <= -z   (forte baisse)
  short si m[s] >= +z   (forte hausse)
  stop  = 2 x ATR20[s] (bougie du signal), fixé à l'entrée par le moteur, jamais déplacé
  sortie au temps : duree_max = H (moteur : ouverture de l'entrée + H séances), pas d'objectif, pas de retournement
Aucun signal pendant la chauffe (21 bougies) ni si l'ATR de la veille est nul ou inconnu (mouvement non mesurable).
"""
import pandas as pd

from src.indicateurs import atr

NOM = "reversion_seance_extreme"
ATR_N = 20
STOP_ATR = 2.0   # convention du laboratoire, pas un paramètre
CHAUFFE = 21
# Grille fixée AVANT le test (proposition 003) : 6 variantes, aucune autre.
GRILLE = [{"z": z, "H": H} for z in (1.5, 2.0, 2.5) for H in (3, 5)]


def mouvement(df: pd.DataFrame) -> pd.Series:
    """m[s] en unités d'ATR de la veille ; NaN si l'ATR de la veille est nul ou inconnu."""
    atr_veille = atr(df, ATR_N).shift(1)
    return (df["close"] - df["close"].shift(1)) / atr_veille.where(atr_veille > 0)


def signaux(df: pd.DataFrame, z: float, H: int) -> dict:
    m = mouvement(df)
    signal = (m <= -z).astype(float) - (m >= z).astype(float)  # NaN -> False -> 0
    signal.iloc[:CHAUFFE] = 0.0
    return {"signal": signal, "stop_dist": atr(df, ATR_N) * STOP_ATR,
            "retournement": False, "duree_max": int(H)}


def variante(p: dict):
    """Fonction de signal pour une variante de la grille (refuse toute variante hors grille)."""
    if p not in GRILLE:
        raise ValueError(f"variante hors grille fixée à l'avance : {p}")
    return lambda df: signaux(df, p["z"], p["H"])


def nom_variante(p: dict) -> str:
    return f"Z{p['z']:g}_H{p['H']}".replace(".", "p")
