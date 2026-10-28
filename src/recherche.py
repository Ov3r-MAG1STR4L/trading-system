"""
Laboratoire de recherche v0.4 (protocole : docs/protocole-recherche-v0.4.md).

Garde-fous :
  - périodes fixées ici, une seule fois ; chaque évaluation TRONQUE les données à la fin de sa période :
    l'entraînement ne voit pas la validation, et l'OOS n'est jamais lu avant son ouverture ;
  - trades attribués à leur date d'entrée ; une position encore ouverte en fin de période est clôturée
    à la dernière clôture de la période (fin_donnees) ;
  - OOS : ouverture unique par expérience, verrouillée par un fichier (OosDejaOuvert sinon) ;
  - registre global des variantes testées (experiments/registre_variantes.csv) ;
  - risque de recherche : 0,25 % du capital réalisé par trade, sans plafond (décision 2026-10-28).
"""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src import couts, portefeuille
from src.engine import Params, backtest

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = ROOT / "experiments"
REGISTRE = EXPERIMENTS / "registre_variantes.csv"
CAPITAL = 10_000
RISQUE_RECHERCHE = 0.0025
PERIODES = {"entrainement": ("2012-08-06", "2019-12-31"),
            "validation": ("2020-01-01", "2022-12-31"),
            "oos": ("2023-01-01", "2026-10-27")}
# Seuils du protocole (section 5). v0.4.1 : éligibilité par marché à 5 trades, 15 = simple information,
# critère « marchés positifs » = au moins 5 ET plus de la moitié des marchés éligibles (entraînement et validation).
VERSION_PROTOCOLE = "v0.4.1"
INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
CRITERES = {"trades_min": {"entrainement": 150, "validation": 60, "oos": 0},
            "trades_min_marche": 5,           # ÉLIGIBILITÉ : en dessous, le marché ne compte ni positif ni négatif
            "trades_bien_echantillonne": 15,  # INFORMATION seulement, jamais un critère de rejet
            "pf_min": 1.10, "marches_positifs_min": 5, "part_marches_positifs_min": 0.5,  # > 50 % des éligibles
            "contribution_max": 0.40, "annees_positives_min": 0.60,
            "dd_max": 0.25, "serie_pertes_max": 20, "centile_benchmark": 95, "marge_revue": 0.10,
            "pf_min_oos": 1.05}


class OosDejaOuvert(RuntimeError):
    pass


# ---------------- données et évaluation par période ----------------

def tronquer(marches: dict, fin: str) -> dict:
    """Coupe chaque marché à la fin de la période : aucune bougie postérieure n'est visible."""
    f = pd.Timestamp(fin)
    return {s: df[df["time"] <= f].reset_index(drop=True) for s, df in marches.items()}


def dans(t, periode):
    d, f = PERIODES[periode]
    return (t >= pd.Timestamp(d)) & (t <= pd.Timestamp(f))


def evaluer(marches: dict, fonction_signal, infos: dict, hyp: dict, periode: str, oos_autorise: bool = False,
            target_r=None) -> dict:
    if periode == "oos" and not oos_autorise:
        raise OosDejaOuvert("OOS : passer par ouvrir_oos() (ouverture unique)")
    m = tronquer(marches, PERIODES[periode][1])
    trades, ev = portefeuille.executer(m, fonction_signal, Params(target_r), infos, hyp)
    trades = trades[dans(trades["entry_time"], periode)].reset_index(drop=True) if len(trades) else trades
    ev = ev[dans(ev["reprise"], periode)].reset_index(drop=True) if len(ev) else ev
    dates = sorted({t for df in m.values() for t in df["time"] if dans(t, periode)})
    a = portefeuille.analyser(trades, ev, list(marches), CAPITAL, RISQUE_RECHERCHE,
                              pd.Timestamp(PERIODES[periode][0]), dates)
    return {"trades": trades, "evenements": ev, "analyse": a}


# ---------------- métriques ----------------

def metriques(ev: dict, marches: list) -> dict:
    t, res = ev["trades"], ev["analyse"]["resume"]
    if t.empty:
        return {"trades": 0}
    r = t["R_execution"]
    gains, pertes = r[r > 0].sum(), -r[r < 0].sum()
    par_m = t.groupby("symbol")["R_execution"].agg(["sum", "count"]).reindex(marches)
    eligibles = par_m[par_m["count"] >= CRITERES["trades_min_marche"]]
    statut_m = {s: (INSUFFICIENT_SAMPLE if (pd.isna(c) or c < CRITERES["trades_min_marche"])
                    else "BIEN_ECHANTILLONNE" if c >= CRITERES["trades_bien_echantillonne"] else "ELIGIBLE")
                for s, c in par_m["count"].items()}
    total = r.sum()
    annees = t.groupby(t["entry_time"].dt.year)["R_execution"].sum()
    net = t["R_net"]
    return {
        "trades": len(t), "esperance_R": float(r.mean()), "profit_factor": float(gains / pertes) if pertes else None,
        "total_R_brut": float(t["R"].sum()), "total_R_execution": float(total),
        "total_R_net": None if net.isna().any() else float(net.sum()),
        "trades_swap_unavailable": int((t["statut_swap"] == couts.SWAP_UNAVAILABLE).sum()),
        "cout_spread_R": float(t["cout_spread_R"].sum()), "cout_slippage_R": float(t["cout_slippage_R"].sum()),
        "rendement_execution": res["execution"]["resultat_monetaire"] / CAPITAL
        if res["execution"]["resultat_monetaire"] is not None else None,
        "drawdown_realise_pct": res["execution"].get("drawdown_realise_pct"),
        "pire_serie_pertes": _serie_max(r < 0), "meilleure_serie_gains": _serie_max(r > 0),
        "marches_eligibles": int(len(eligibles)), "marches_positifs": int((eligibles["sum"] > 0).sum()),
        "marches_negatifs": int((eligibles["sum"] <= 0).sum()),
        "marches_insufficient_sample": sum(v == INSUFFICIENT_SAMPLE for v in statut_m.values()),
        "marches_bien_echantillonnes": sum(v == "BIEN_ECHANTILLONNE" for v in statut_m.values()),
        "statut_echantillon_par_marche": statut_m,
        "trades_par_marche": {s: int(c) if pd.notna(c) else 0 for s, c in par_m["count"].items()},
        "R_par_marche": {s: float(v) if pd.notna(v) else 0.0 for s, v in par_m["sum"].items()},
        "contribution_max": float(par_m["sum"].max() / total) if total > 0 else None,
        "marche_contribution_max": par_m["sum"].idxmax() if total > 0 else None,
        "annees": {int(a): float(v) for a, v in annees.items()},
        "part_annees_positives": float((annees > 0).mean()),
        "part_max_une_annee": float(annees.max() / total) if total > 0 else None,
        "exposition_max_pct": res["exposition_journaliere"]["risque_ouvert_max_pct"],
        "positions_max": res["exposition_journaliere"]["positions_max"],
        "data_gap": {"traverses": int(t["traverse_gap"].sum()), "refus": int(ev["evenements"]["entree_refusee"].sum())
                     if len(ev["evenements"]) else 0},
    }


def _serie_max(masque) -> int:
    best = cur = 0
    for m in masque:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


# ---------------- benchmark : entrées aléatoires ----------------

def benchmark_aleatoire(marches: dict, fonction_signal, infos: dict, hyp: dict, periode: str,
                        trades_par_marche: dict, n_tirages: int = 200, seed: int = 0, chauffe: int = 120) -> np.ndarray:
    """Espérance (R après spread/slippage) de n_tirages portefeuilles à entrées ALÉATOIRES : mêmes marchés, même
    nombre de signaux par marché que la stratégie, mêmes stops et mêmes sorties (ceux de la stratégie), dates et
    sens tirés au hasard parmi les bougies de la période (graine fixe)."""
    rng = np.random.default_rng(seed)
    prep = {}
    for s, df in tronquer(marches, PERIODES[periode][1]).items():
        sig = fonction_signal(df)
        k0 = max(int(np.argmax(dans(df["time"], periode).to_numpy())) - chauffe, 0)
        d = df.iloc[k0:].reset_index(drop=True)
        dedans = np.flatnonzero(dans(d["time"], periode).to_numpy()[:-1])  # signal en j -> entrée en j+1
        prep[s] = (d, sig["stop_dist"].iloc[k0:].reset_index(drop=True),
                   sig.get("sortie_long", pd.Series(False, index=df.index)).iloc[k0:].reset_index(drop=True),
                   sig.get("sortie_short", pd.Series(False, index=df.index)).iloc[k0:].reset_index(drop=True), dedans,
                   bool(sig.get("retournement", False)))  # mêmes règles d'exécution que la stratégie
    esperances = np.full(n_tirages, np.nan)
    for k in range(n_tirages):
        rs = []
        for s, (d, stop, sl, ss, dedans, rt) in prep.items():
            n = min(trades_par_marche.get(s, 0), len(dedans))
            if n == 0:
                continue
            signal = pd.Series(0.0, index=d.index)
            signal.iloc[rng.choice(dedans, n, replace=False)] = rng.choice([-1.0, 1.0], n)
            t, _ = backtest(d, signal, stop, Params(None), None, sl, ss, retournement=rt)
            t = t[dans(t["entry_time"], periode)]
            if len(t):
                rs.append(couts.appliquer(t, d, infos[s], hyp[s])["R_execution"].to_numpy())
        if rs:
            esperances[k] = np.concatenate(rs).mean()
    return esperances


# ---------------- critères du protocole ----------------

def criteres(m: dict, periode: str, stress: dict | None = None, bench: np.ndarray | None = None) -> dict:
    """Critères de REJET (liste) et alertes de REVUE (marge < 10 % d'un seuil). Sur R après spread/slippage."""
    c, rejet, revue = CRITERES, [], []
    if m.get("trades", 0) < c["trades_min"][periode]:
        rejet.append(f"trades {m.get('trades', 0)} < {c['trades_min'][periode]}")
        return {"rejet": rejet, "revue": revue}
    if m["esperance_R"] <= 0:
        rejet.append(f"espérance {m['esperance_R']:.3f} R <= 0")
    pf = m["profit_factor"] or 0
    if pf < c["pf_min"]:
        rejet.append(f"profit factor {pf:.2f} < {c['pf_min']}")
    elif pf < c["pf_min"] * (1 + c["marge_revue"]):
        revue.append(f"profit factor {pf:.2f} proche du seuil")
    pos, elig = m["marches_positifs"], m["marches_eligibles"]  # éligibles seulement (INSUFFICIENT_SAMPLE exclus)
    if pos < c["marches_positifs_min"]:
        rejet.append(f"{pos} marchés positifs < {c['marches_positifs_min']} (sur {elig} éligibles)")
    elif pos <= c["part_marches_positifs_min"] * elig:
        rejet.append(f"{pos} marchés positifs sur {elig} éligibles : pas une majorité")
    elif pos == c["marches_positifs_min"] or pos - 1 <= c["part_marches_positifs_min"] * elig:
        revue.append(f"marchés positifs au seuil ({pos} sur {elig} éligibles)")
    cm = m["contribution_max"]
    if cm is not None and cm > c["contribution_max"]:
        rejet.append(f"{m['marche_contribution_max']} fait {cm:.0%} du gain (> {c['contribution_max']:.0%})")
    elif cm is not None and cm > c["contribution_max"] * (1 - c["marge_revue"]):
        revue.append(f"{m['marche_contribution_max']} fait {cm:.0%} du gain")
    dd = m["drawdown_realise_pct"]
    if dd is not None and dd > c["dd_max"]:
        rejet.append(f"drawdown réalisé {dd:.1%} > {c['dd_max']:.0%}")
    if m["pire_serie_pertes"] > c["serie_pertes_max"]:
        rejet.append(f"série de {m['pire_serie_pertes']} pertes > {c['serie_pertes_max']}")
    pa = m.get("part_annees_positives_tv")  # entraînement + validation cumulés (protocole)
    if pa is not None and pa < c["annees_positives_min"]:
        rejet.append(f"{pa:.0%} d'années positives < {c['annees_positives_min']:.0%}")
    if m["part_max_une_annee"] is not None and m["part_max_une_annee"] > 0.5:
        revue.append(f"une année fait {m['part_max_une_annee']:.0%} du gain")
    if stress is not None and stress.get("trades", 0) and stress["esperance_R"] <= 0:
        rejet.append(f"stress slippage : espérance {stress['esperance_R']:.3f} R <= 0")
    if bench is not None:
        seuil = float(np.nanpercentile(bench, c["centile_benchmark"]))
        if m["esperance_R"] <= seuil:
            rejet.append(f"ne bat pas le {c['centile_benchmark']}e centile aléatoire ({m['esperance_R']:.3f} <= {seuil:.3f} R)")
    return {"rejet": rejet, "revue": revue}


def plateau(esperances_train: dict, grille: list, nom, cle_longueur: str = "n", cle_stop: str = "stop_atr") -> dict:
    """Voisins dans la grille (même longueur et autre stop ; longueur adjacente et même stop) : tous positifs sur
    l'entraînement ? Les noms de paramètres valent ceux de Donchian par défaut (expérience 001 inchangée)."""
    ns = sorted({p[cle_longueur] for p in grille})
    out = {}
    for p in grille:
        i = ns.index(p[cle_longueur])
        voisins = [q for q in grille if (q[cle_longueur] == p[cle_longueur] and q != p)
                   or (q[cle_stop] == p[cle_stop] and abs(ns.index(q[cle_longueur]) - i) == 1)]
        out[nom(p)] = all(esperances_train[nom(q)] > 0 for q in voisins)
    return out


# ---------------- traçabilité ----------------

def enregistrer_variantes(experience: str, variantes: list, commit: str, registre: Path = REGISTRE) -> int:
    """Ajoute les variantes au registre global (sans doublon pour une même expérience). Renvoie le total."""
    registre.parent.mkdir(parents=True, exist_ok=True)
    reg = pd.read_csv(registre, sep=";", dtype=str) if registre.exists() else \
        pd.DataFrame(columns=["experience", "variante", "params", "date", "commit"])
    deja = set(zip(reg["experience"], reg["variante"]))
    nouv = [{"experience": experience, "variante": v, "params": json.dumps(p, sort_keys=True),
             "date": datetime.now().strftime("%Y-%m-%d"), "commit": commit}
            for v, p in variantes if (experience, v) not in deja]
    reg = pd.concat([reg, pd.DataFrame(nouv)], ignore_index=True) if nouv else reg
    reg.to_csv(registre, sep=";", index=False)
    return len(reg)


def ouvrir_oos(dossier: Path, variante: str, commit: str) -> None:
    """Verrou : l'OOS d'une expérience ne s'ouvre qu'une fois."""
    f = dossier / "oos_ouvert.json"
    if f.exists():
        raise OosDejaOuvert(f"OOS déjà ouvert pour {dossier.name} : {f.read_text(encoding='utf-8')}")
    f.write_text(json.dumps({"variante": variante, "commit": commit,
                             "date": datetime.now().isoformat(timespec="seconds")}, indent=2), encoding="utf-8")
