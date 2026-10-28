"""
Expérience 002 : momentum en série temporelle, 6 variantes figées (hypothèse :
experiments/002-momentum-serie-temporelle/hypothese.md, protocole v0.4.1). Hors ligne, aucune connexion MT5.

  python scripts/experience_002.py      (seulement après décision explicite)

Déroulé : vérifications -> préparation -> inscription des 6 variantes au registre (juste avant l'évaluation)
-> entraînement -> validation (base, stress, benchmark aléatoire) -> critères -> decision.json.
Le script S'ARRÊTE après la validation. Il n'ouvre JAMAIS l'OOS, même si une variante est KEEP :
état final « VALIDATION_COMPLETE — OOS_LOCKED », l'ouverture de l'OOS est une action séparée.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import couts, data, rapport, recherche as rc  # noqa: E402
from src.engine import VERSION_MOTEUR  # noqa: E402
from strategies import momentum  # noqa: E402

EXP = "002"
DOSSIER = rc.EXPERIMENTS / "002-momentum-serie-temporelle"
DOSSIER_001 = rc.EXPERIMENTS / "001-donchian-baseline"
REGISTRE = rc.REGISTRE
VARIANTES_ATTENDUES = [{"L": L, "k": k} for L in (60, 125, 250) for k in (3.0, 5.0)]  # copie de l'hypothèse
PROTOCOLE_ATTENDU = "v0.4.1"
PERIODES_EVALUEES = ("entrainement", "validation")  # jamais "oos" ici
ETAT_FINAL = "VALIDATION_COMPLETE — OOS_LOCKED"
FICHIERS_RESULTATS = ("experience.json", "resultats.csv", "decision.json", "rapports", "oos_ouvert.json")
N_TIRAGES = 200
SEED = 2


def arreter(msg):
    sys.exit(f"STOP : {msg}")


def verifier_variantes(dossier: Path = DOSSIER) -> None:
    if momentum.GRILLE != VARIANTES_ATTENDUES:
        arreter(f"la grille de strategies/momentum.py ne correspond pas à l'hypothèse : {momentum.GRILLE}")
    texte = (dossier / "hypothese.md").read_text(encoding="utf-8")
    for attendu in ("L (bougies de rendement) | 60, 125, 250", "k (stop en ATR) | 3, 5", "6 variantes"):
        if attendu not in texte:
            arreter(f"hypothese.md ne contient pas « {attendu} »")


def verifier_preconditions(git: dict, dossier: Path | None = None, dossier_001: Path | None = None) -> None:
    """Toutes les conditions de lancement ; arrête le script (SystemExit) à la première qui échoue.
    Les dossiers sont résolus à l'APPEL (pas à la définition) : un test qui redirige DOSSIER est bien pris en compte."""
    dossier = DOSSIER if dossier is None else dossier
    dossier_001 = DOSSIER_001 if dossier_001 is None else dossier_001
    if not git.get("commit") or git.get("dirty"):
        arreter("dépôt non propre ou sans commit. Commite avant de lancer une expérience.")
    if rc.VERSION_PROTOCOLE != PROTOCOLE_ATTENDU:
        arreter(f"protocole actif {rc.VERSION_PROTOCOLE}, attendu {PROTOCOLE_ATTENDU}")
    if not (dossier / "hypothese.md").exists():
        arreter("hypothese.md absent : l'hypothèse doit être écrite avant l'exécution")
    existants = [f for f in FICHIERS_RESULTATS if (dossier / f).exists()]
    if existants:
        arreter(f"l'expérience 002 a déjà des résultats ({', '.join(existants)}) : elle ne se rejoue pas")
    d001 = dossier_001 / "decision.json"
    if not d001.exists():
        arreter("décision de l'expérience 001 introuvable")
    dec = json.loads(d001.read_text(encoding="utf-8"))
    if dec.get("oos_ouvert_pour") is not None or (dossier_001 / "oos_ouvert.json").exists() \
            or any(v["statut"] != "REJECT" for v in dec["variantes"].values()):
        arreter("l'expérience 001 n'est plus dans son état historique")
    verifier_variantes(dossier)


def preparer(marches: dict, infos: dict) -> dict:
    """Hypothèses de coûts : plancher = médiane des spreads > 0 sur 2012-2022 (sans l'OOS) ; stress = 1 plancher."""
    fin_val = pd.Timestamp(rc.PERIODES["validation"][1])
    planchers = {s: float(df.loc[(df["time"] <= fin_val) & (df["spread"] > 0), "spread"].median())
                 for s, df in marches.items()}
    return {"planchers": planchers,
            "base": {s: couts.Hypotheses("historique", planchers[s], 0.0) for s in marches},
            "stress": {s: couts.Hypotheses("historique", planchers[s], planchers[s]) for s in marches},
            "variantes": [(momentum.nom_variante(p), p) for p in momentum.GRILLE]}


def params_rapport(p, periode, symboles, planchers):
    d, f = rc.PERIODES[periode]
    return {"strategie": momentum.NOM, "params_strategie": {**p, "atr": momentum.ATR_N, "retournement": True},
            "marches": symboles, "periode": {"nom": periode, "debut": d, "fin": f},
            "source_donnees": "MT5 MetaQuotes-Demo, D1, data/*_D1.csv (v0.2)",
            "risque": {"capital": rc.CAPITAL, "risque_pct": rc.RISQUE_RECHERCHE, "compose": True,
                       "regle": "0,25 % du capital réalisé à l'entrée, sans plafond"},
            "couts": {"spread_mode": "historique", "spread_points": "par marché : médiane des spreads > 0, 2012-2022",
                      "slippage_points": 0.0, "swaps": True},
            "spread_plancher_points_par_marche": planchers, "date_swaps": "2026-10-28 (relevé v0.4)",
            "version_moteur": VERSION_MOTEUR, "protocole": rc.VERSION_PROTOCOLE, "experience": EXP}


def main():
    git = rapport.etat_git()
    verifier_preconditions(git)

    symboles = pd.read_csv(data.ROOT / "config" / "marches.csv", sep=";").query("actif == 1")["symbol"].tolist()
    marches = {s: data.charger(s) for s in symboles}
    infos = {s: couts.info_symbole(s) for s in symboles}
    prep = preparer(marches, infos)
    noms = prep["variantes"]

    DOSSIER.mkdir(parents=True, exist_ok=True)
    total_variantes = rc.enregistrer_variantes(EXP, noms, git["commit"], REGISTRE)  # juste avant l'évaluation
    (DOSSIER / "experience.json").write_text(json.dumps({
        "experience": EXP, "strategie": momentum.NOM, "grille": momentum.GRILLE, "retournement": True,
        "protocole": rc.VERSION_PROTOCOLE, "periodes_evaluees": {p: rc.PERIODES[p] for p in PERIODES_EVALUEES},
        "oos": {"periode": rc.PERIODES["oos"], "etat": "FERMÉ, ouverture manuelle séparée"},
        "criteres": rc.CRITERES, "risque_par_trade": rc.RISQUE_RECHERCHE, "capital": rc.CAPITAL,
        "spread_plancher_points": prep["planchers"], "slippage_stress_points": prep["planchers"],
        "benchmark": {"tirages": N_TIRAGES, "graine": SEED, "periode": "validation", "retournement": True},
        "commit": git["commit"], "variantes_registre_total": total_variantes, "marches": symboles},
        indent=2, ensure_ascii=False), encoding="utf-8")

    res, lignes = {}, []
    for nom, p in noms:
        f = momentum.variante(p)
        res[nom] = {}
        for periode in PERIODES_EVALUEES:
            ev = rc.evaluer(marches, f, infos, prep["base"], periode)
            m = rc.metriques(ev, symboles)
            ms = rc.metriques(rc.evaluer(marches, f, infos, prep["stress"], periode), symboles)
            res[nom][periode] = {"m": m, "stress": ms}
            a = ev["analyse"]
            rapport.ecrire(f"{nom}_{periode}", params_rapport(p, periode, symboles, prep["planchers"]), a["trades"],
                           ev["evenements"], racine=DOSSIER / "rapports", tables=a["tables"],
                           portefeuille=a["resume"], version="v0.4", git=git)
            print(f"{nom:8} {periode:12} trades {m['trades']:4}  E={m.get('esperance_R', 0):+.3f} R  "
                  f"stress E={ms.get('esperance_R', 0):+.3f} R", flush=True)
        b = rc.benchmark_aleatoire(marches, f, infos, prep["base"], "validation",
                                   res[nom]["validation"]["m"]["trades_par_marche"], N_TIRAGES, SEED)
        res[nom]["bench"] = b
        print(f"{nom:8} benchmark validation : médiane {np.nanmedian(b):+.3f} R, 95e centile "
              f"{np.nanpercentile(b, 95):+.3f} R", flush=True)

    esp_train = {n: r["entrainement"]["m"].get("esperance_R", -1) for n, r in res.items()}
    pl = rc.plateau(esp_train, momentum.GRILLE, momentum.nom_variante, cle_longueur="L", cle_stop="k")
    decisions = {}
    for nom, _ in noms:
        r = res[nom]
        annees = {**r["entrainement"]["m"].get("annees", {}), **r["validation"]["m"].get("annees", {})}
        pa = float(np.mean([v > 0 for v in annees.values()])) if annees else None
        ct = rc.criteres({**r["entrainement"]["m"], "part_annees_positives_tv": pa}, "entrainement",
                         r["entrainement"]["stress"])
        cv = rc.criteres({**r["validation"]["m"], "part_annees_positives_tv": pa}, "validation",
                         r["validation"]["stress"], r["bench"])
        rejet = [f"entraînement : {x}" for x in ct["rejet"]] + [f"validation : {x}" for x in cv["rejet"]]
        if not pl[nom]:
            rejet.append("entraînement : pas de plateau (une variante voisine a une espérance <= 0)")
        revue = ct["revue"] + cv["revue"]
        statut = "REJECT" if rejet else ("NEEDS_REVIEW" if revue else "KEEP")
        decisions[nom] = {"statut": statut, "rejet": rejet, "revue": revue, "plateau": pl[nom],
                          "part_annees_positives_tv": pa,
                          "benchmark_95e": float(np.nanpercentile(r["bench"], 95)),
                          "benchmark_mediane": float(np.nanmedian(r["bench"]))}
        for periode in PERIODES_EVALUEES:
            m, ms = r[periode]["m"], r[periode]["stress"]
            lignes.append({"variante": nom, "periode": periode, **{k: v for k, v in m.items() if not isinstance(v, dict)},
                           "esperance_R_stress": ms.get("esperance_R"), "statut": statut})

    candidats = [n for n, d in decisions.items() if d["statut"] == "KEEP"]
    pd.DataFrame(lignes).to_csv(DOSSIER / "resultats.csv", sep=";", index=False)
    (DOSSIER / "decision.json").write_text(json.dumps({
        "experience": EXP, "commit": git["commit"], "protocole": rc.VERSION_PROTOCOLE, "etat": ETAT_FINAL,
        "oos_ouvert_pour": None, "candidats_oos": candidats,
        "note": "KEEP = candidat à l'OOS, pas une preuve de rentabilité ; OOS à ouvrir seulement sur décision manuelle",
        "variantes": decisions, "variantes_registre_total": total_variantes},
        indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("\nDécisions (entraînement + validation) :")
    for n, d in decisions.items():
        print(f"- {n:8} {d['statut']:12} {'; '.join(d['rejet'] or d['revue']) or 'aucun critère en échec'}")
    print(f"\n{ETAT_FINAL} — candidats à l'OOS : {candidats or 'aucun'}")


if __name__ == "__main__":
    main()
