"""
Coûts d'un trade : spread, slippage, swaps. Aucune logique de stratégie.

S'applique APRÈS src/engine.py, sur sa table de trades (engine.py inchangé).

Ordre d'application (tous les coûts sont exprimés en R, rapportés au risque initial prévu `dist`) :
  1. signal -> prix THÉORIQUES (engine) : prix BID MT5, R_brut
  2. prix d'EXÉCUTION = prix théorique + spread + slippage, toujours dans le sens défavorable :
       long  : achat au ask (bid + spread) + slippage, vente au bid - slippage
       short : vente au bid - slippage, rachat au ask (bid + spread) + slippage
     -> R_execution
  3. swaps, nuit par nuit, entre l'entrée et la sortie -> R_net
Pourquoi le spread n'est payé qu'une fois : les prix MT5 sont des BID ; un long achète au ask
(spread payé à l'entrée) et revend au bid ; un short vend au bid et rachète au ask (spread à la sortie).

Limites assumées (voir docs/decisions.md) :
  - stop et objectif sont déclenchés sur le BID par le moteur (un short réel se déclenche sur l'ask) ;
  - spread D1 historique de MT5 : beaucoup de valeurs à 0 (non fiables) -> plancher obligatoire ;
  - swaps = valeurs ACTUELLES du broker (2026-10-28), appliquées au passé : APPROXIMATION.
"""
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SWAPS_CSV = ROOT / "reports" / "2026-10-28_v0.4_swaps" / "swaps.csv"  # v0.4 : avec devises et mode de calcul
JOURS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}
MODE_POINTS = 1  # SYMBOL_SWAP_MODE_POINTS : converti en prix par x point
MODES_DEVISE = (2, 3)  # SYMBOL_SWAP_MODE_CURRENCY_SYMBOL / _MARGIN : montant par lot dans devise_swap
CALCUL_CFD = 2  # SYMBOL_CALC_MODE_CFD : P&L d'1 lot = variation de prix x contrat, en devise_profit
SWAP_UNAVAILABLE = "SWAP_UNAVAILABLE"  # swap non convertible : état explicite, jamais remplacé par 0
AVERTISSEMENT_SWAPS = ("Swaps : valeurs ACTUELLES du broker (récupérées le {date}) appliquées à tout l'historique. "
                       "Approximation : ce ne sont PAS les swaps observés à l'époque.")


class CoutInvalide(ValueError):
    """Information insuffisante : on refuse le calcul plutôt que d'inventer."""


@dataclass(frozen=True)
class Hypotheses:
    spread_mode: str = "historique"   # "historique" = max(spread de la bougie, plancher) ; "fixe" = spread_points
    spread_points: float | None = None  # plancher (historique) ou valeur fixe (fixe), en points ; obligatoire
    slippage_points: float = 0.0      # par exécution (entrée ET sortie), défavorable ; 0 = backtest brut
    swaps: bool = True                # False = swaps ignorés (à déclarer dans le rapport)

    def valider(self):
        if self.spread_mode not in ("historique", "fixe"):
            raise CoutInvalide(f"spread_mode inconnu : {self.spread_mode!r}")
        if self.spread_points is None or not np.isfinite(self.spread_points) or self.spread_points < 0:
            raise CoutInvalide("spread_points obligatoire et >= 0 (plancher ou valeur fixe)")
        if not np.isfinite(self.slippage_points) or self.slippage_points < 0:
            raise CoutInvalide("slippage_points doit être >= 0 (un slippage ne peut pas être un gain)")

    def en_dict(self):
        return asdict(self)


def info_symbole(symbol: str, swaps_csv: Path = SWAPS_CSV) -> dict:
    t = pd.read_csv(swaps_csv, sep=";")
    ligne = t[t["symbol"] == symbol]
    if ligne.empty:
        raise CoutInvalide(f"{symbol} : symbole inconnu dans {swaps_csv.name}")
    info = ligne.iloc[0].to_dict()
    if not (np.isfinite(info["point"]) and info["point"] > 0):
        raise CoutInvalide(f"{symbol} : taille du point invalide")
    return info


def prix_execution(prix: float, d: int, cote: str, spread_px: float, slippage_px: float) -> float:
    """Prix réellement obtenu à partir d'un prix théorique BID. d = +1 long, -1 short."""
    if cote not in ("entree", "sortie") or d not in (1, -1):
        raise CoutInvalide(f"cote={cote!r}, d={d!r} invalides")
    achat = (d == 1) == (cote == "entree")  # long à l'entrée ou short à la sortie = on achète
    return prix + spread_px + slippage_px if achat else prix - slippage_px


def nuits_swap(entree: pd.Timestamp, sortie: pd.Timestamp, jour_triple: str) -> int:
    """Nombre de swaps facturés : un rollover à la fin de chaque jour ouvré J avec entrée <= J < sortie,
    x3 le jour du triple swap, 0 le week-end. Même jour = intraday = 0."""
    if jour_triple not in JOURS:
        raise CoutInvalide(f"jour de triple swap inconnu : {jour_triple!r}")
    e, s = pd.Timestamp(entree).normalize(), pd.Timestamp(sortie).normalize()
    if s < e:
        raise CoutInvalide("sortie avant l'entrée")
    jours = pd.date_range(e, s - pd.Timedelta(days=1), freq="D")
    return int(sum(3 if j.weekday() == JOURS[jour_triple] else (1 if j.weekday() < 5 else 0) for j in jours))


def raison_swap_non_convertible(info: dict) -> str | None:
    """None si le swap peut être exprimé en unités de PRIX sans aucun taux de change, sinon la raison.
    - mode points : swap x point ;
    - modes devise (2, 3) : seulement si devise du swap = devise du profit ET calcul CFD ET contrat > 0 :
      1 lot qui bouge de 1,0 rapporte « contrat » unités de devise_profit, donc swap_prix = swap / contrat."""
    mode = info.get("swap_mode")
    if mode == MODE_POINTS:
        return None
    if mode not in MODES_DEVISE:
        return f"mode de swap {mode} non pris en charge"
    ds, dp = info.get("devise_swap"), info.get("devise_profit")
    if not isinstance(ds, str) or not isinstance(dp, str):
        return "devise du swap ou du profit non relevée"
    if ds != dp:
        return f"devise du swap {ds} différente de la devise du profit {dp} (taux de change nécessaire)"
    if info.get("mode_calcul") != CALCUL_CFD:
        return f"mode de calcul {info.get('mode_calcul')} : relation prix/montant non vérifiée"
    c = info.get("contrat_taille")
    if c is None or not np.isfinite(c) or c <= 0:
        return "taille de contrat invalide"
    return None


def swap_px_par_nuit(info: dict, d: int) -> float:
    """Swap d'une nuit en unités de PRIX (positif = gain). Refuse (CoutInvalide) toute conversion non vérifiée."""
    raison = raison_swap_non_convertible(info)
    if raison:
        raise CoutInvalide(f"{info['symbol']} : swap en mode {info['swap_mode']} non convertible ({raison})")
    valeur = info["swap_long"] if d == 1 else info["swap_short"]
    if valeur is None or not np.isfinite(valeur):
        raise CoutInvalide(f"{info['symbol']} : swap {'long' if d == 1 else 'short'} manquant")
    return valeur * info["point"] if info["swap_mode"] == MODE_POINTS else valeur / info["contrat_taille"]


def appliquer(trades: pd.DataFrame, bougies: pd.DataFrame, info: dict, h: Hypotheses) -> pd.DataFrame:
    """Ajoute aux trades du moteur : prix d'exécution, coûts en R, R_execution, swaps, R_net."""
    h.valider()
    out = trades.copy()
    if out.empty:
        return out.assign(entree_exec=[], sortie_exec=[], spread_entree_pts=[], spread_sortie_pts=[],
                          plancher_utilise=[], cout_spread_R=[], cout_slippage_R=[], R_execution=[],
                          nuits_swap=[], swap_R=[], statut_swap=[], R_net=[])
    point = info["point"]
    spread_par_date = bougies.set_index("time")["spread"]
    slip = h.slippage_points * point

    def spread_pts(t):
        if h.spread_mode == "fixe":
            return h.spread_points, False
        if t not in spread_par_date.index or not np.isfinite(spread_par_date[t]):
            raise CoutInvalide(f"{info['symbol']} : spread absent pour la bougie du {t}")
        brut = float(spread_par_date[t])
        return max(brut, h.spread_points), brut < h.spread_points

    lignes = []
    for t in out.itertuples():
        d = 1 if t.direction == "long" else -1
        se, pe = spread_pts(t.entry_time)
        ss, ps = spread_pts(t.exit_time)
        # le spread n'est payé que du côté où l'on achète (ask)
        e_x = prix_execution(t.entry, d, "entree", se * point if d == 1 else 0.0, slip)
        s_x = prix_execution(t.exit, d, "sortie", ss * point if d == -1 else 0.0, slip)
        cout_spread = (se if d == 1 else ss) * point / t.dist
        r_exec = (s_x - e_x) * d / t.dist
        n = nuits_swap(t.entry_time, t.exit_time, info["triple_swap_jour"]) if h.swaps else 0
        if not h.swaps:
            swap_r, statut = 0.0, "DESACTIVE"
        elif n == 0:
            swap_r, statut = 0.0, "AUCUNE_NUIT"
        elif raison_swap_non_convertible(info):
            swap_r, statut = np.nan, SWAP_UNAVAILABLE  # R_net devient NaN : inconnu, pas zéro
        else:
            swap_r, statut = n * swap_px_par_nuit(info, d) / t.dist, "OK"
        lignes.append({"entree_exec": e_x, "sortie_exec": s_x, "spread_entree_pts": se, "spread_sortie_pts": ss,
                       "plancher_utilise": (pe and d == 1) or (ps and d == -1),
                       "cout_spread_R": cout_spread, "cout_slippage_R": 2 * slip / t.dist,
                       "R_execution": r_exec, "nuits_swap": n, "swap_R": swap_r, "statut_swap": statut,
                       "R_net": r_exec + swap_r})
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(lignes)], axis=1)
