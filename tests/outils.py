"""Petites données synthétiques pour les tests (prix écrits à la main)."""
import pandas as pd


def bougies(ohlc, debut="2020-01-06", gaps_avant=()):
    """ohlc : liste de (open, high, low, close). gaps_avant : index des bougies qui suivent un trou."""
    df = pd.DataFrame(ohlc, columns=["open", "high", "low", "close"], dtype=float)
    df.insert(0, "time", pd.bdate_range(debut, periods=len(df)))
    df["spread"] = 0
    df["gap_avant"] = False
    for i in gaps_avant:
        df.loc[i, "gap_avant"] = True
    return df


def serie(n, **valeurs):
    """Series de longueur n à 0, avec quelques valeurs posées : serie(5, **{'2': 1})."""
    s = pd.Series(0.0, index=range(n))
    for k, v in valeurs.items():
        s[int(k)] = v
    return s


PLAT = (100, 101, 99, 100)  # bougie neutre : ne touche ni stop à 95 ni objectif à 110
