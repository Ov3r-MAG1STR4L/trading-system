"""
Moteur de backtest bougie par bougie, indépendant de toute stratégie. Résultats bruts en R
(les coûts arrivent avec src/couts.py).

Contrat avec la stratégie : pour chaque bougie i, calculée avec les bougies <= i seulement :
  signal[i]      : +1 long, -1 short, 0 rien
  stop_dist[i]   : distance du stop en prix (> 0)
  sortie[i]      : True = sortir de la position en cours (optionnel)
C'est le MOTEUR qui décale : une info de la clôture de i n'agit qu'à l'ouverture de i+1.

Règles d'exécution (CLAUDE.md, règles du projet) :
  - entrée à l'ouverture suivante, stop = entrée -/+ stop_dist, objectif = target_r x stop_dist ;
  - stop et objectif dans la même bougie -> stop ;
  - ouverture au-delà du stop -> sortie au prix d'ouverture (gap défavorable encaissé) ;
  - sortie sur signal -> à l'ouverture suivante ;
  - une seule position à la fois, pas de nouvelle entrée sur la bougie d'une sortie.

DATA_GAP / NON_TRADABLE (décision 2026-10-28) :
  - aucune bougie inventée pendant le trou ;
  - aucune entrée à la reprise à partir d'un signal antérieur au trou ;
  - une position ouverte reste ouverte : pas de sortie sur une bougie inexistante ;
  - à la reprise, on utilise le premier prix réel (ouverture), règles de stop normales ;
  - le trade est marqué `traverse_gap = True` et le trou est journalisé.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data import STATUT_GAP

VERSION_MOTEUR = "0.3.0"


@dataclass(frozen=True)
class Params:
    target_r: float | None = None  # objectif en multiples du risque, None = pas d'objectif


def backtest(df: pd.DataFrame, signal: pd.Series, stop_dist: pd.Series,
             params: Params = Params(), sortie: pd.Series | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Renvoie (trades, evenements). df doit venir de src.data (colonne gap_avant)."""
    n = len(df)
    for nom, s in (("signal", signal), ("stop_dist", stop_dist)):
        if len(s) != n:
            raise ValueError(f"{nom} : {len(s)} valeurs pour {n} bougies")
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t = df["time"].to_numpy()
    gap = df["gap_avant"].to_numpy(bool) if "gap_avant" in df else np.zeros(n, bool)
    sig = np.nan_to_num(np.asarray(signal, float))
    dist = np.asarray(stop_dist, float)
    sort = np.zeros(n, bool) if sortie is None else np.asarray(sortie, bool)

    trades, evenements, pos = [], [], None

    def fermer(i, prix, raison):
        trades.append({**{k: pos[k] for k in ("direction", "entry_time", "entry", "stop", "target", "dist",
                                             "traverse_gap")},
                       "exit_time": t[i], "exit": prix, "raison": raison, "bougies": i - pos["i"] + 1,
                       "R": (prix - pos["entry"]) * pos["d"] / pos["dist"]})

    for i in range(1, n):
        if gap[i]:
            evenements.append({"statut": STATUT_GAP, "derniere_bougie_avant": t[i - 1], "reprise": t[i],
                               "position_ouverte": pos is not None,
                               # signal d'avant le trou qui aurait donné une entrée : refusé (NON_TRADABLE)
                               "entree_refusee": pos is None and sig[i - 1] != 0})
            if pos is not None:
                pos["traverse_gap"] = True

        sorti = False
        if pos is not None:
            d, stop, target = pos["d"], pos["stop"], pos["target"]
            if sort[i - 1]:                                    # sortie décidée à la clôture de i-1
                fermer(i, o[i], "signal")
            elif (d == 1 and l[i] <= stop) or (d == -1 and h[i] >= stop):
                prix = min(o[i], stop) if d == 1 else max(o[i], stop)
                fermer(i, prix, "stop_gap" if prix == o[i] and o[i] != stop else "stop")
            elif target is not None and ((d == 1 and h[i] >= target) or (d == -1 and l[i] <= target)):
                fermer(i, max(o[i], target) if d == 1 else min(o[i], target), "objectif")
            else:
                continue                                       # position conservée
            pos, sorti = None, True

        if sorti or gap[i] or sig[i - 1] == 0:
            continue
        if not (np.isfinite(dist[i - 1]) and dist[i - 1] > 0):
            continue
        d, e, dd = int(np.sign(sig[i - 1])), o[i], dist[i - 1]
        pos = {"i": i, "d": d, "direction": "long" if d == 1 else "short", "entry_time": t[i], "entry": e,
               "dist": dd, "stop": e - d * dd,
               "target": None if params.target_r is None else e + d * dd * params.target_r,
               "traverse_gap": False}
        # la bougie d'entrée peut déjà toucher le stop ou l'objectif (après l'ouverture)
        if (d == 1 and l[i] <= pos["stop"]) or (d == -1 and h[i] >= pos["stop"]):
            fermer(i, pos["stop"], "stop")
            pos = None
        elif pos["target"] is not None and ((d == 1 and h[i] >= pos["target"]) or (d == -1 and l[i] <= pos["target"])):
            fermer(i, pos["target"], "objectif")
            pos = None

    if pos is not None:                                        # position ouverte à la fin des données
        fermer(n - 1, c[n - 1], "fin_donnees")

    cols = ["direction", "entry_time", "entry", "stop", "target", "dist", "exit_time", "exit", "raison",
            "bougies", "R", "traverse_gap"]
    return (pd.DataFrame(trades, columns=cols),
            pd.DataFrame(evenements, columns=["statut", "derniere_bougie_avant", "reprise", "position_ouverte",
                                               "entree_refusee"]))


def verifier_sans_lookahead(fonction_signal, df: pd.DataFrame, coupures=(0.3, 0.5, 0.8), seed: int = 0) -> None:
    """Lève AssertionError si fonction_signal(df) utilise des bougies futures.

    Pour chaque coupure t : on remplace toutes les bougies après t par du bruit.
    Les valeurs renvoyées jusqu'à t incluse doivent rester identiques.
    fonction_signal renvoie une Series ou un dict de Series alignées sur df.
    """
    rng = np.random.default_rng(seed)
    ref = _en_dict(fonction_signal(df))
    for frac in coupures:
        k = int(len(df) * frac)
        futur = df.copy()
        bruit = rng.uniform(0.5, 1.5, size=len(df) - k - 1)
        for col in ("open", "high", "low", "close"):
            futur.loc[futur.index[k + 1:], col] = df[col].to_numpy()[k + 1:] * bruit
        alt = _en_dict(fonction_signal(futur))
        for nom in ref:
            a, b = ref[nom].iloc[:k + 1], alt[nom].iloc[:k + 1]
            pd.testing.assert_series_equal(a, b, check_names=False,
                                           obj=f"{nom} jusqu'à la bougie {k} (données futures modifiées)")


def _en_dict(x):
    return {k: pd.Series(v).reset_index(drop=True) for k, v in x.items()} if isinstance(x, dict) \
        else {"signal": pd.Series(x).reset_index(drop=True)}
