"""
Gestion du risque, indépendante du moteur et de toute stratégie. Résultats BRUTS (sans coûts :
spread, swaps et slippage sont dans src/couts.py).

Conventions :
  - risque_pct est une fraction : 0.01 = 1 % du capital risqué par trade (référence du projet) ;
  - R = (sortie - entrée) / (entrée - stop) : même formule pour un long et un short ;
  - equity composée par défaut : chaque trade risque risque_pct du capital COURANT
    (comme scripts/backtest.py) ; compose=False = risque fixe sur le capital initial.
Aucune valeur par défaut silencieuse : toute entrée invalide lève RisqueInvalide.
"""
import math

import numpy as np
import pandas as pd

RISQUE_REFERENCE = 0.01


class RisqueInvalide(ValueError):
    pass


def _positif(nom, x):
    if x is None or not math.isfinite(x) or x <= 0:
        raise RisqueInvalide(f"{nom} doit être un nombre > 0 (reçu {x!r})")


def montant_risque(capital: float, risque_pct: float = RISQUE_REFERENCE) -> float:
    """Montant risqué : 10 000 € x 1 % = 100 €."""
    _positif("capital", capital)
    _positif("risque_pct", risque_pct)
    if risque_pct > 0.05:
        raise RisqueInvalide(f"risque_pct = {risque_pct:.2%} : au-delà de 5 %, c'est sûrement une erreur d'unité")
    return capital * risque_pct


def taille_position(capital: float, risque_pct: float, stop_dist: float, valeur_point: float = 1.0,
                    pas: float | None = None, taille_min: float | None = None) -> float:
    """Taille telle qu'un stop touché coûte capital x risque_pct.

    valeur_point : gain/perte en devise du compte pour un mouvement de prix de 1,0 sur 1 unité
                   (ex. 1 lot EURUSD = 100 000 USD/point de prix, converti en devise du compte).
    pas          : taille arrondie VERS LE BAS à un multiple de pas (le risque réel ne dépasse jamais la cible).
    taille_min   : si la taille arrondie est sous ce minimum, on lève une erreur au lieu de prendre plus de risque.
    """
    risque = montant_risque(capital, risque_pct)
    _positif("stop_dist", stop_dist)
    _positif("valeur_point", valeur_point)
    taille = risque / (stop_dist * valeur_point)
    if pas is not None:
        _positif("pas", pas)
        taille = math.floor(taille / pas + 1e-9) * pas
    if taille_min is not None and taille < taille_min:
        raise RisqueInvalide(f"taille {taille:g} < minimum {taille_min:g} : trade impossible sans dépasser le risque")
    if taille <= 0:
        raise RisqueInvalide("taille nulle après arrondi : stop trop large pour ce capital")
    return taille


def risque_reel(taille: float, stop_dist: float, valeur_point: float = 1.0) -> float:
    """Perte en devise si le stop est touché, après arrondi de la taille."""
    return taille * stop_dist * valeur_point


def resultat_r(entree: float, sortie: float, stop: float) -> float:
    """Gain/perte en R, long ou short : le signe de (entrée - stop) donne le sens."""
    for nom, x in (("entree", entree), ("sortie", sortie), ("stop", stop)):
        if x is None or not math.isfinite(x):
            raise RisqueInvalide(f"{nom} manquant ({x!r})")
    if entree == stop:
        raise RisqueInvalide("stop égal à l'entrée : risque initial nul")
    return (sortie - entree) / (entree - stop)


def montant(r: float, risque_initial: float) -> float:
    """-1 R avec 100 € de risque = -100 €."""
    _positif("risque_initial", risque_initial)
    return r * risque_initial


def _valider_r(r) -> np.ndarray:
    a = np.asarray(r, dtype=float)
    if np.isnan(a).any():
        raise RisqueInvalide("résultats R manquants (NaN)")
    return a


def equity(r, capital: float, risque_pct: float = RISQUE_REFERENCE, compose: bool = True) -> pd.Series:
    """Equity après chaque trade, précédée du capital initial (longueur = trades + 1)."""
    risque = montant_risque(capital, risque_pct)
    a = _valider_r(r)
    courbe = capital * np.cumprod(1 + risque_pct * a) if compose else capital + risque * np.cumsum(a)
    return pd.Series(np.r_[capital, courbe], name="equity")


def drawdown(eq: pd.Series) -> pd.DataFrame:
    """Plus haut historique, drawdown absolu (devise) et relatif (fraction du plus haut), point par point."""
    e = pd.Series(eq, dtype=float).reset_index(drop=True)
    if e.isna().any() or (e <= 0).any():
        raise RisqueInvalide("equity manquante ou <= 0")
    plus_haut = e.cummax()
    return pd.DataFrame({"equity": e, "plus_haut": plus_haut, "dd_abs": plus_haut - e,
                         "dd_pct": (plus_haut - e) / plus_haut})


def drawdown_max(eq: pd.Series) -> dict:
    """Drawdown maximal absolu et relatif (ils peuvent tomber à des moments différents)."""
    d = drawdown(eq)
    return {"dd_max_abs": float(d["dd_abs"].max()), "dd_max_pct": float(d["dd_pct"].max()),
            "fin_dd_max_pct": int(d["dd_pct"].idxmax())}


def series(r) -> dict:
    """Séries max de pertes / gains consécutifs et série courante (+k gains, -k pertes, 0 si aucune).
    Un trade à 0 R casse les deux séries."""
    a = _valider_r(r)
    max_p = max_g = cur = 0
    for x in a:
        if x > 0:
            cur = cur + 1 if cur > 0 else 1
        elif x < 0:
            cur = cur - 1 if cur < 0 else -1
        else:
            cur = 0
        max_g, max_p = max(max_g, cur), max(max_p, -cur)
    return {"max_pertes": max_p, "max_gains": max_g, "courante": cur}
