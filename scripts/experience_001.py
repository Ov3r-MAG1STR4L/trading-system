"""
Expérience 001 : Donchian breakout, 6 variantes fixées (protocole v0.4). Hors ligne, aucune connexion MT5.

  python scripts/experience_001.py

Refuse de tourner si le dépôt n'est pas propre (résultat non reproductible).
L'OOS n'est ouvert QU'UNE fois, et seulement pour la meilleure variante KEEP (meilleure espérance d'entraînement).
Sorties : experiments/001-donchian-baseline/ (experience.json, resultats.csv, decision.json, rapports/).
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
from strategies import donchian  # noqa: E402

EXP = "001"
DOSSIER = rc.EXPERIMENTS / "001-donchian-baseline"
N_TIRAGES = 200
SEED = 1


def params_rapport(p, periode, symboles, planchers, slippage):
    d, f = rc.PERIODES[periode]
    return {"strategie": donchian.NOM, "params_strategie": {**p, "atr": donchian.ATR_N, "sortie": "canal N/2"},
            "marches": symboles, "periode": {"nom": periode, "debut": d, "fin": f},
            "source_donnees": "MT5 MetaQuotes-Demo, D1, data/*_D1.csv (v0.2)",
            "risque": {"capital": rc.CAPITAL, "risque_pct": rc.RISQUE_RECHERCHE, "compose": True,
                       "regle": "0,25 % du capital réalisé à l'entrée, sans plafond"},
            "couts": {"spread_mode": "historique", "spread_points": "par marché : médiane des spreads > 0, 2012-2022",
                      "slippage_points": slippage, "swaps": True},
            "spread_plancher_points_par_marche": planchers, "date_swaps": "2026-10-28 (relevé v0.4)",
            "version_moteur": VERSION_MOTEUR, "experience": EXP}


def main():
    if (DOSSIER / "decision.json").exists():
        sys.exit("STOP : l'expérience 001 est déjà jugée ; ses résultats sont historiques et ne sont pas recalculés.")
    git = rapport.etat_git()
    if not git["commit"] or git["dirty"]:
        sys.exit("STOP : dépôt non propre ou sans commit. Commite avant de lancer une expérience.")

    symboles = pd.read_csv(data.ROOT / "config" / "marches.csv", sep=";").query("actif == 1")["symbol"].tolist()
    marches = {s: data.charger(s) for s in symboles}
    infos = {s: couts.info_symbole(s) for s in symboles}
    fin_val = pd.Timestamp(rc.PERIODES["validation"][1])
    planchers = {s: float(df.loc[(df["time"] <= fin_val) & (df["spread"] > 0), "spread"].median())
                 for s, df in marches.items()}  # calculé sans l'OOS
    base = {s: couts.Hypotheses("historique", planchers[s], 0.0) for s in symboles}
    stress = {s: couts.Hypotheses("historique", planchers[s], planchers[s]) for s in symboles}
    noms = [(donchian.nom_variante(p), p) for p in donchian.GRILLE]
    total_variantes = rc.enregistrer_variantes(EXP, noms, git["commit"])

    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / "experience.json").write_text(json.dumps({
        "experience": EXP, "strategie": donchian.NOM, "grille": donchian.GRILLE, "periodes": rc.PERIODES,
        "criteres": rc.CRITERES, "risque_par_trade": rc.RISQUE_RECHERCHE, "capital": rc.CAPITAL,
        "spread_plancher_points": planchers, "slippage_stress_points": planchers, "benchmark": {
            "tirages": N_TIRAGES, "graine": SEED, "periode": "validation"},
        "commit": git["commit"], "variantes_registre_total": total_variantes, "marches": symboles},
        indent=2, ensure_ascii=False), encoding="utf-8")

    lignes, res = [], {}
    for nom, p in noms:
        f = donchian.variante(p)
        res[nom] = {}
        for periode in ("entrainement", "validation"):
            ev = rc.evaluer(marches, f, infos, base, periode)
            m = rc.metriques(ev, symboles)
            ms = rc.metriques(rc.evaluer(marches, f, infos, stress, periode), symboles)
            res[nom][periode] = {"m": m, "stress": ms}
            a = ev["analyse"]
            rapport.ecrire(f"{nom}_{periode}", params_rapport(p, periode, symboles, planchers, 0.0), a["trades"],
                           ev["evenements"], racine=DOSSIER / "rapports", tables=a["tables"],
                           portefeuille=a["resume"], version="v0.4", git=git)
            print(f"{nom:8} {periode:12} trades {m['trades']:4}  E={m.get('esperance_R', 0):+.3f} R  "
                  f"stress E={ms.get('esperance_R', 0):+.3f} R", flush=True)
        b = rc.benchmark_aleatoire(marches, f, infos, base, "validation",
                                   res[nom]["validation"]["m"]["trades_par_marche"], N_TIRAGES, SEED)
        res[nom]["bench"] = b
        print(f"{nom:8} benchmark validation : médiane {np.nanmedian(b):+.3f} R, 95e centile "
              f"{np.nanpercentile(b, 95):+.3f} R", flush=True)

    esp_train = {n: r["entrainement"]["m"].get("esperance_R", -1) for n, r in res.items()}
    pl = rc.plateau(esp_train, donchian.GRILLE, donchian.nom_variante)
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
        for periode in ("entrainement", "validation"):
            m, ms = r[periode]["m"], r[periode]["stress"]
            lignes.append({"variante": nom, "periode": periode, **{k: v for k, v in m.items() if not isinstance(v, dict)},
                           "esperance_R_stress": ms.get("esperance_R"), "statut": statut})

    keep = [n for n, d in decisions.items() if d["statut"] == "KEEP"]
    oos = None
    if keep:
        choisie = max(keep, key=lambda n: esp_train[n])
        rc.ouvrir_oos(DOSSIER, choisie, git["commit"])
        p = dict(noms)[choisie]
        ev = rc.evaluer(marches, donchian.variante(p), infos, base, "oos", oos_autorise=True)
        m = rc.metriques(ev, symboles)
        ms = rc.metriques(rc.evaluer(marches, donchian.variante(p), infos, stress, "oos", oos_autorise=True), symboles)
        a = ev["analyse"]
        rapport.ecrire(f"{choisie}_oos", params_rapport(p, "oos", symboles, planchers, 0.0), a["trades"],
                       ev["evenements"], racine=DOSSIER / "rapports", tables=a["tables"], portefeuille=a["resume"],
                       version="v0.4", git=git)
        ok = m.get("trades", 0) > 0 and m["esperance_R"] > 0 and (m["profit_factor"] or 0) >= rc.CRITERES["pf_min_oos"]
        decisions[choisie]["oos"] = {"esperance_R": m.get("esperance_R"), "profit_factor": m.get("profit_factor"),
                                    "trades": m.get("trades"), "esperance_R_stress": ms.get("esperance_R")}
        decisions[choisie]["statut"] = "KEEP" if ok else "REJECT"
        if not ok:
            decisions[choisie]["rejet"].append("OOS : espérance <= 0 ou profit factor < 1,05")
        lignes.append({"variante": choisie, "periode": "oos", **{k: v for k, v in m.items() if not isinstance(v, dict)},
                       "esperance_R_stress": ms.get("esperance_R"), "statut": decisions[choisie]["statut"]})
        oos = choisie

    pd.DataFrame(lignes).to_csv(DOSSIER / "resultats.csv", sep=";", index=False)
    (DOSSIER / "decision.json").write_text(json.dumps({
        "experience": EXP, "commit": git["commit"], "oos_ouvert_pour": oos, "variantes": decisions,
        "variantes_registre_total": total_variantes}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("\nDécisions :")
    for n, d in decisions.items():
        print(f"- {n:8} {d['statut']:12} {'; '.join(d['rejet'] or d['revue']) or 'aucun critère en échec'}")
    print(f"\nOOS ouvert pour : {oos}")


if __name__ == "__main__":
    main()
