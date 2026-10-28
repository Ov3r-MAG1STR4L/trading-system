"""
Moteur de backtest bougie par bougie, indépendant de toute stratégie. Résultats bruts en R
(les coûts arrivent avec src/couts.py).

Contrat avec la stratégie : pour chaque bougie i, calculée avec les bougies <= i seulement :
  signal[i]      : +1 long, -1 short, 0 rien
  stop_dist[i]   : distance du stop en prix (> 0)
  sortie[i]      : True = sortir de la position en cours (optionnel)
  sortie_long[i] / sortie_short[i] : True = sortir seulement d'un long / d'un short (optionnel)
C'est le MOTEUR qui décale : une info de la clôture de i n'agit qu'à l'ouverture de i+1.

Règles d'exécution (CLAUDE.md, règles du projet) :
  - entrée à l'ouverture suivante, stop = entrée -/+ stop_dist, objectif = target_r x stop_dist ;
  - stop et objectif dans la même bougie -> stop ;
  - ouverture au-delà du stop -> sortie au prix d'ouverture (gap défavorable encaissé) ;
  - sortie sur signal -> à l'ouverture suivante ;
  - une seule position à la fois, pas de nouvelle entrée sur la bougie d'une sortie ;
  - EXCEPTION, seulement si retournement=True (activé explicitement par la stratégie) : quand une sortie SUR SIGNAL
    décidée à la clôture de i-1 coïncide avec un signal de sens OPPOSÉ à la même clôture, la position est fermée à
    l'ouverture de i et la position inverse est ouverte à cette même ouverture, avec son propre stop
    (stop_dist[i-1]) et son propre état. Jamais après un stop, un objectif, ni sur une bougie de reprise après un trou.
  - durée maximale de détention, seulement si duree_max=H (entier >= 1, activé par la stratégie) : une position
    ouverte à l'ouverture de la bougie i est fermée à l'ouverture de la bougie i+H (motif « duree ») si elle est
    encore ouverte, c'est-à-dire après H séances complètes (i .. i+H-1). Les séances sont les bougies RÉELLEMENT
    disponibles (une bougie de reprise après un trou compte comme la séance suivante). La sortie à l'ouverture passe
    avant le stop intra-bougie de i+H. Jamais de retournement ni de nouvelle entrée sur cette bougie. Si les données
    s'arrêtent avant i+H, la position est fermée en « fin_donnees ».

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
             params: Params = Params(), sortie: pd.Series | None = None,
             sortie_long: pd.Series | None = None, sortie_short: pd.Series | None = None,
             retournement: bool = False, duree_max: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Renvoie (trades, evenements). df doit venir de src.data (colonne gap_avant)."""
    if duree_max is not None and (isinstance(duree_max, bool) or not isinstance(duree_max, (int, np.integer))
                                  or duree_max < 1):
        raise ValueError(f"duree_max doit être un entier >= 1 ou None (reçu {duree_max!r})")
    n = len(df)
    for nom, s in (("signal", signal), ("stop_dist", stop_dist)):
        if len(s) != n:
            raise ValueError(f"{nom} : {len(s)} valeurs pour {n} bougies")
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t = df["time"].to_numpy()
    gap = df["gap_avant"].to_numpy(bool) if "gap_avant" in df else np.zeros(n, bool)
    sig = np.nan_to_num(np.asarray(signal, float))
    dist = np.asarray(stop_dist, float)
    sort, sort_l, sort_s = (np.zeros(n, bool) if x is None else np.asarray(x, bool)
                            for x in (sortie, sortie_long, sortie_short))
    for nom, x in (("sortie", sort), ("sortie_long", sort_l), ("sortie_short", sort_s)):
        if len(x) != n:
            raise ValueError(f"{nom} : {len(x)} valeurs pour {n} bougies")

    trades, evenements, pos = [], [], None

    def fermer(i, prix, raison):
        trades.append({**{k: pos[k] for k in ("direction", "entry_time", "entry", "stop", "target", "dist",
                                             "traverse_gap", "retournement")},
                       "exit_time": t[i], "exit": prix, "raison": raison, "bougies": i - pos["i"] + 1,
                       "R": (prix - pos["entry"]) * pos["d"] / pos["dist"]})

    for i in range(1, n):
        if gap[i]:
            evenements.append({"statut": STATUT_GAP, "derniere_bougie_avant": t[i - 1], "reprise": t[i],
                               "position_ouverte": pos is not None,
                               # complété plus bas, APRÈS la sortie éventuelle à la reprise
                               "entree_refusee": False})
            if pos is not None:
                pos["traverse_gap"] = True

        sorti, inverse = False, False
        if pos is not None:
            d, stop, target = pos["d"], pos["stop"], pos["target"]
            if sort[i - 1] or (sort_l[i - 1] if d == 1 else sort_s[i - 1]):  # décidée à la clôture de i-1
                fermer(i, o[i], "signal")
                inverse = retournement and sig[i - 1] == -d  # sortie sur signal + signal opposé : retournement
            elif duree_max is not None and i - pos["i"] >= duree_max:  # H séances complètes : sortie à l'ouverture
                fermer(i, o[i], "duree")
            elif (d == 1 and l[i] <= stop) or (d == -1 and h[i] >= stop):
                prix = min(o[i], stop) if d == 1 else max(o[i], stop)
                fermer(i, prix, "stop_gap" if prix == o[i] and o[i] != stop else "stop")
            elif target is not None and ((d == 1 and h[i] >= target) or (d == -1 and l[i] <= target)):
                fermer(i, max(o[i], target) if d == 1 else min(o[i], target), "objectif")
            else:
                continue                                       # position conservée
            pos, sorti = None, True

        if gap[i]:  # signal d'avant le trou qui aurait pu donner une entrée : refusé (NON_TRADABLE)
            evenements[-1]["entree_refusee"] = pos is None and sig[i - 1] != 0
        if (sorti and not inverse) or gap[i] or sig[i - 1] == 0:
            continue
        if not (np.isfinite(dist[i - 1]) and dist[i - 1] > 0):
            continue
        d, e, dd = int(np.sign(sig[i - 1])), o[i], dist[i - 1]
        pos = {"i": i, "d": d, "direction": "long" if d == 1 else "short", "entry_time": t[i], "entry": e,
               "dist": dd, "stop": e - d * dd,
               "target": None if params.target_r is None else e + d * dd * params.target_r,
               "traverse_gap": False, "retournement": inverse}
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
            "bougies", "R", "traverse_gap", "retournement"]
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
