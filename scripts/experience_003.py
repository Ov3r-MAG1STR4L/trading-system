"""
Expérience 003 : retournement à court terme après une séance extrême, 6 variantes figées (proposition validée :
docs/proposition-experience-003.md), PREMIÈRE expérience sous le protocole v0.4.2. Hors ligne, aucune connexion MT5.

  python scripts/experience_003.py      (seulement après décision explicite)

Déroulé : vérifications -> copie figée de la proposition -> inscription des 6 variantes au registre (juste avant
l'évaluation, chemin passé explicitement) -> entraînement -> validation (base, stress, benchmark v0.4.2 : 200 tirages
conservés) -> critères v0.4.2 -> decision.json.
Les données sont TRONQUÉES à la fin de la validation dès leur chargement : l'OOS n'est jamais lu.
Le script S'ARRÊTE après la validation sur « VALIDATION_COMPLETE — OOS_LOCKED », même si une variante est KEEP.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src import couts, data, rapport, recherche as rc  # noqa: E402
from src.engine import VERSION_MOTEUR, Params  # noqa: E402
from strategies import reversion  # noqa: E402

EXP = "003"
DOSSIER = rc.EXPERIMENTS / "003-reversion-seance-extreme"
PROPOSITION = rc.ROOT / "docs" / "proposition-experience-003.md"
REGISTRE = rc.REGISTRE
DOSSIERS_HISTORIQUES = {"001": rc.EXPERIMENTS / "001-donchian-baseline",
                        "002": rc.EXPERIMENTS / "002-momentum-serie-temporelle"}
VARIANTES_ATTENDUES = [{"z": z, "H": H} for z in (1.5, 2.0, 2.5) for H in (3, 5)]  # copie de la proposition
PROTOCOLE_ATTENDU = "v0.4.2"
VARIANTES_AVANT = 12  # 001 (6) + 002 (6) : registre attendu avant 003
PERIODES_EVALUEES = ("entrainement", "validation")  # jamais "oos" ici
ETAT_FINAL = "VALIDATION_COMPLETE — OOS_LOCKED"
FICHIERS_RESULTATS = ("experience.json", "resultats.csv", "decision.json", "rapports", "benchmark",
                      "oos_ouvert.json", "hypothese.md")
SEED = 3


def arreter(msg):
    sys.exit(f"STOP : {msg}")


def chemins():
    """Résolus à l'APPEL (et non à la définition) : un test qui redirige ces chemins est bien pris en compte."""
    return DOSSIER, PROPOSITION, REGISTRE, DOSSIERS_HISTORIQUES


def verifier_variantes(proposition: Path) -> None:
    if reversion.GRILLE != VARIANTES_ATTENDUES:
        arreter(f"la grille de strategies/reversion.py ne correspond pas à la proposition : {reversion.GRILLE}")
    texte = proposition.read_text(encoding="utf-8")
    for attendu in ("Statut : VALIDÉE", "z (seuil du mouvement, en ATR) | 1,5 ; 2,0 ; 2,5",
                    "H (séances de détention) | 3 ; 5", "6 variantes"):
        if attendu not in texte:
            arreter(f"la proposition ne contient pas « {attendu} »")


def verifier_preconditions(git: dict) -> None:
    """Toutes les conditions de lancement ; arrête le script (SystemExit) à la première qui échoue."""
    dossier, proposition, registre, historiques = chemins()
    if not git.get("commit") or git.get("dirty"):
        arreter("dépôt non propre ou sans commit. Commite avant de lancer une expérience.")
    if rc.VERSION_PROTOCOLE != PROTOCOLE_ATTENDU:
        arreter(f"protocole actif {rc.VERSION_PROTOCOLE}, attendu {PROTOCOLE_ATTENDU}")
    if not proposition.exists():
        arreter("proposition 003 absente : l'hypothèse doit être validée avant l'exécution")
    existants = [f for f in FICHIERS_RESULTATS if (dossier / f).exists()]
    if existants:
        arreter(f"l'expérience 003 a déjà des résultats ({', '.join(existants)}) : elle ne se rejoue pas")
    if list(registre.parent.rglob("oos_ouvert.json")):
        arreter("un OOS a été ouvert : état inattendu, vérification manuelle nécessaire")
    reg = pd.read_csv(registre, sep=";", dtype=str)
    if len(reg) != VARIANTES_AVANT or (reg["experience"] == EXP).any() or reg.duplicated(["experience", "variante"]).any():
        arreter(f"registre inattendu : {len(reg)} lignes (attendu {VARIANTES_AVANT}, sans 003 ni doublon)")
    for nom, d in historiques.items():
        dec = json.loads((d / "decision.json").read_text(encoding="utf-8"))
        if dec.get("oos_ouvert_pour") is not None or any(v["statut"] != "REJECT" for v in dec["variantes"].values()):
            arreter(f"l'expérience {nom} n'est plus dans son état historique")
    verifier_variantes(proposition)


def preparer(marches: dict) -> dict:
    """Coûts : plancher = médiane des spreads > 0 sur 2012-2022 ; stress = 1 plancher de slippage par exécution."""
    planchers = {s: float(df.loc[df["spread"] > 0, "spread"].median()) for s, df in marches.items()}
    return {"planchers": planchers,
            "base": {s: couts.Hypotheses("historique", planchers[s], 0.0) for s in marches},
            "stress": {s: couts.Hypotheses("historique", planchers[s], planchers[s]) for s in marches},
            "variantes": [(reversion.nom_variante(p), p) for p in reversion.GRILLE]}


def params_rapport(p, periode, symboles, planchers):
    d, f = rc.PERIODES[periode]
    return {"strategie": reversion.NOM,
            "params_strategie": {**p, "atr": reversion.ATR_N, "stop_atr": reversion.STOP_ATR, "duree_max": p["H"],
                                 "retournement": False, "objectif": None},
            "marches": symboles, "periode": {"nom": periode, "debut": d, "fin": f},
            "source_donnees": "MT5 MetaQuotes-Demo, D1, data/*_D1.csv (v0.2), tronquées au 2022-12-31",
            "risque": {"capital": rc.CAPITAL, "risque_pct": rc.RISQUE_RECHERCHE, "compose": True,
                       "regle": "0,25 % du capital réalisé à l'entrée, sans plafond"},
            "couts": {"spread_mode": "historique", "spread_points": "par marché : médiane des spreads > 0, 2012-2022",
                      "slippage_points": 0.0, "swaps": True},
            "spread_plancher_points_par_marche": planchers, "date_swaps": "2026-10-28 (relevé v0.4)",
            "version_moteur": VERSION_MOTEUR, "protocole": rc.VERSION_PROTOCOLE, "benchmark": rc.BENCHMARK,
            "experience": EXP}


def main():
    git = rapport.etat_git()
    verifier_preconditions(git)
    dossier, proposition, registre, _ = chemins()

    symboles = pd.read_csv(data.ROOT / "config" / "marches.csv", sep=";").query("actif == 1")["symbol"].tolist()
    fin_val = rc.PERIODES["validation"][1]
    marches = rc.tronquer({s: data.charger(s) for s in symboles}, fin_val)  # l'OOS n'est jamais gardé en mémoire
    infos = {s: couts.info_symbole(s) for s in symboles}
    prep = preparer(marches)
    noms = prep["variantes"]

    dossier.mkdir(parents=True, exist_ok=True)
    shutil.copy(proposition, dossier / "hypothese.md")  # copie figée de l'hypothèse validée
    total_variantes = rc.enregistrer_variantes(EXP, noms, git["commit"], registre)  # juste avant l'évaluation
    (dossier / "experience.json").write_text(json.dumps({
        "experience": EXP, "strategie": reversion.NOM, "grille": reversion.GRILLE, "stop_atr": reversion.STOP_ATR,
        "retournement": False, "protocole": rc.VERSION_PROTOCOLE, "benchmark": {**rc.BENCHMARK, "graine": SEED},
        "periodes_evaluees": {p: rc.PERIODES[p] for p in PERIODES_EVALUEES},
        "oos": {"periode": rc.PERIODES["oos"], "etat": "FERMÉ, données tronquées au chargement"},
        "criteres": rc.CRITERES, "risque_par_trade": rc.RISQUE_RECHERCHE, "capital": rc.CAPITAL,
        "spread_plancher_points": prep["planchers"], "slippage_stress_points": prep["planchers"],
        "commit": git["commit"], "variantes_registre_total": total_variantes, "marches": symboles},
        indent=2, ensure_ascii=False), encoding="utf-8")

    res, lignes = {}, []
    for nom, p in noms:
        f = reversion.variante(p)
        res[nom] = {}
        for periode in PERIODES_EVALUEES:
            ev = rc.evaluer(marches, f, infos, prep["base"], periode)
            m = rc.metriques(ev, symboles)
            ms = rc.metriques(rc.evaluer(marches, f, infos, prep["stress"], periode), symboles)
            res[nom][periode] = {"m": m, "stress": ms}
            a = ev["analyse"]
            rapport.ecrire(f"{nom}_{periode}", params_rapport(p, periode, symboles, prep["planchers"]), a["trades"],
                           ev["evenements"], racine=dossier / "rapports", tables=a["tables"],
                           portefeuille=a["resume"], version="v0.4", git=git)
            print(f"{nom:9} {periode:12} trades {m.get('trades', 0):4}  E={m.get('esperance_R', 0):+.3f} R  "
                  f"stress E={ms.get('esperance_R', 0):+.3f} R", flush=True)
        mv = res[nom]["validation"]["m"]
        tirages = rc.benchmark_entrees_randomisees(marches, f, infos, prep["base"], "validation",
                                                   mv.get("trades_par_marche", {}), Params(None),
                                                   rc.BENCHMARK["tirages"], SEED)
        resume = rc.resume_benchmark(tirages, mv.get("esperance_R", float("-inf")))
        rc.ecrire_benchmark(dossier, nom, tirages, resume)
        res[nom]["bench"] = np.array([np.nan if t["esperance_R"] is None else t["esperance_R"] for t in tirages])
        res[nom]["bench_resume"] = resume
        print(f"{nom:9} benchmark : P50 {resume['p50']} R, P95 {resume['p95']} R, "
              f"percentile stratégie {resume['percentile_strategie']} %", flush=True)

    esp_train = {n: r["entrainement"]["m"].get("esperance_R", -1) for n, r in res.items()}
    pl = rc.plateau(esp_train, reversion.GRILLE, reversion.nom_variante, cle_longueur="z", cle_stop="H")
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
                          "part_annees_positives_tv": pa, "benchmark": r["bench_resume"]}
        for periode in PERIODES_EVALUEES:
            m, ms = r[periode]["m"], r[periode]["stress"]
            lignes.append({"variante": nom, "periode": periode, **{k: v for k, v in m.items() if not isinstance(v, dict)},
                           "esperance_R_stress": ms.get("esperance_R"), "statut": statut})

    candidats = [n for n, d in decisions.items() if d["statut"] == "KEEP"]
    pd.DataFrame(lignes).to_csv(dossier / "resultats.csv", sep=";", index=False)
    (dossier / "decision.json").write_text(json.dumps({
        "experience": EXP, "commit": git["commit"], "protocole": rc.VERSION_PROTOCOLE, "etat": ETAT_FINAL,
        "oos_ouvert_pour": None, "candidats_oos": candidats,
        "note": "KEEP = candidat à l'OOS, pas une preuve de rentabilité ; OOS à ouvrir seulement sur décision manuelle. "
                "Benchmark : entrées randomisées à sorties identiques (mesure le timing d'entrée).",
        "variantes": decisions, "variantes_registre_total": total_variantes},
        indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("\nDécisions (entraînement + validation) :")
    for n, d in decisions.items():
        print(f"- {n:9} {d['statut']:12} {'; '.join(d['rejet'] or d['revue']) or 'aucun critère en échec'}")
    print(f"\n{ETAT_FINAL} — candidats à l'OOS : {candidats or 'aucun'}")


if __name__ == "__main__":
    main()
