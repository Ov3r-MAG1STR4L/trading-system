"""
Reporting reproductible d'un backtest. Ne fait que MESURER et ENREGISTRER :
aucun choix de stratégie, de paramètre ou de marché, aucun trade supprimé.

Dossier : reports/AAAA-MM-JJ_v0.3_<nom>/
  params.json         paramètres complets + git + date d'exécution
  resultats.csv       un trade par ligne (brut, coûts, net, états DATA_GAP / SWAP_UNAVAILABLE)
  evenements.csv      journal des DATA_GAP du moteur
  resume.json         statistiques brut -> coûts -> net
  avertissements.txt  limitations détectées automatiquement

Reproductibilité : resultats.csv, evenements.csv et resume.json ne dépendent que des entrées
(pas de date ni de hasard) ; params.json contient en plus la date et l'état Git.
"""
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src import risque
from src.couts import SWAP_UNAVAILABLE

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
CLES_OBLIGATOIRES = ["strategie", "params_strategie", "marches", "periode", "source_donnees",
                     "risque", "couts", "version_moteur"]


class RapportInvalide(ValueError):
    pass


# ---------------- Git ----------------

def etat_git(racine: Path = ROOT) -> dict:
    def git(*args):
        r = subprocess.run(["git", *args], cwd=racine, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    commit = git("rev-parse", "HEAD")
    statut = git("status", "--porcelain", "--untracked-files=no")  # dirty = code suivi modifié (pas les rapports créés)
    return {"commit": commit, "tag": git("describe", "--tags", "--always", "--dirty") if commit else None,
            "dirty": None if statut is None else bool(statut)}


# ---------------- statistiques ----------------

def stats_r(r) -> dict:
    """Statistiques d'une série de R (ordre chronologique)."""
    a = np.asarray(r, dtype=float)
    if np.isnan(a).any():
        raise RapportInvalide("R manquant : utiliser seulement des résultats complets")
    if len(a) == 0:
        return {"trades": 0}
    gains, pertes = a[a > 0].sum(), -a[a < 0].sum()
    s = risque.series(a)
    return {"trades": len(a), "taux_reussite": float((a > 0).mean()),
            "profit_factor": float(gains / pertes) if pertes > 0 else None,
            "esperance_R": float(a.mean()), "total_R": float(a.sum()),
            "pire_serie_pertes": s["max_pertes"], "meilleure_serie_gains": s["max_gains"]}


def stats_argent(r, capital: float, risque_pct: float, compose: bool) -> dict:
    eq = risque.equity(r, capital, risque_pct, compose)
    dd = risque.drawdown_max(eq)
    return {"capital_initial": capital, "capital_final": float(eq.iloc[-1]),
            "resultat_monetaire": float(eq.iloc[-1] - capital),
            "drawdown_realise": dd["dd_max_abs"], "drawdown_realise_pct": dd["dd_max_pct"]}


def resume(trades: pd.DataFrame, evenements: pd.DataFrame, params: dict, argent: bool = True) -> dict:
    """Brut -> coûts -> net. Le net n'est calculé que si aucun swap n'est SWAP_UNAVAILABLE.
    argent=False : pas d'equity séquentielle trade après trade (le portefeuille fournit la sienne)."""
    arg = stats_argent if argent else (lambda *a: {})
    t = trades.sort_values(["exit_time", "entry_time"], kind="stable").reset_index(drop=True)
    rq = params["risque"]
    out = {"brut": {**stats_r(t["R"]), **arg(t["R"], rq["capital"], rq["risque_pct"], rq["compose"])}}
    if "R_execution" in t:
        indispo = t["statut_swap"] == SWAP_UNAVAILABLE
        out["couts_R"] = {"spread": float(t["cout_spread_R"].sum()), "slippage": float(t["cout_slippage_R"].sum()),
                          "swap_connu": float(t.loc[~indispo, "swap_R"].sum()),
                          "trades_swap_unavailable": int(indispo.sum()),
                          "total_connu": float((t["R"] - t["R_execution"]).sum() - t.loc[~indispo, "swap_R"].sum())}
        out["apres_spread_slippage"] = stats_r(t["R_execution"])
        if indispo.any():
            out["net"] = {"statut": SWAP_UNAVAILABLE,
                          "raison": f"{int(indispo.sum())} trade(s) sans swap calculable : net inconnu, pas mis à zéro"}
        else:
            out["net"] = {**stats_r(t["R_net"]),
                          **arg(t["R_net"], rq["capital"], rq["risque_pct"], rq["compose"])}
    out["data_gap"] = {"trous": len(evenements),
                       "trades_traversant": int(t["traverse_gap"].sum()) if len(t) else 0,
                       "entrees_refusees": int(evenements["entree_refusee"].sum()) if len(evenements) else 0}
    return out


# ---------------- avertissements ----------------

def avertissements(params: dict, trades: pd.DataFrame, evenements: pd.DataFrame, git: dict,
                   qualite: pd.DataFrame | None = None) -> list[str]:
    a = []
    if git.get("commit") is None:
        a.append("GIT : commit introuvable, résultat non reproductible.")
    elif git.get("dirty"):
        a.append(f"GIT : dépôt modifié (dirty) au commit {git['commit'][:7]}, le code exécuté n'est pas exactement celui du commit.")
    a.append(f"SOURCE : une seule source de données ({params['source_donnees']}), sans recoupement.")
    c = params["couts"]
    if c["spread_mode"] == "historique":
        n = int(trades["plancher_utilise"].sum()) if "plancher_utilise" in trades else 0
        a.append(f"SPREAD : historique MT5 avec plancher de {c['spread_points']} points "
                 f"(plancher utilisé sur {n} trade(s) ; le spread D1 de MT5 contient de nombreuses valeurs à 0).")
    else:
        a.append(f"SPREAD : valeur FIXE de {c['spread_points']} points (hypothèse, pas une donnée historique).")
    a.append(f"SLIPPAGE : {c['slippage_points']} point(s) par exécution, valeur hypothétique."
             if c["slippage_points"] else "SLIPPAGE : 0 (aucun slippage simulé).")
    if not c["swaps"]:
        a.append("SWAPS : désactivés, le résultat ignore les frais de portage.")
    else:
        a.append(f"SWAPS : valeurs actuelles du broker ({params.get('date_swaps', 'date inconnue')}) appliquées "
                 "à tout l'historique : approximation, pas les swaps observés à l'époque.")
        if "statut_swap" in trades and (trades["statut_swap"] == SWAP_UNAVAILABLE).any():
            m = sorted(trades.loc[trades["statut_swap"] == SWAP_UNAVAILABLE, "symbol"].unique()) \
                if "symbol" in trades else ["?"]
            a.append(f"{SWAP_UNAVAILABLE} : swap non convertible pour {', '.join(m)} ; résultat net inconnu pour ces trades.")
    if len(evenements):
        a.append(f"DATA_GAP : {len(evenements)} trou(s) de données ; "
                 f"{int(trades['traverse_gap'].sum()) if len(trades) else 0} trade(s) les traversent ; "
                 f"{int(evenements['entree_refusee'].sum())} entrée(s) refusée(s).")
    if qualite is not None:
        for q in qualite.itertuples():
            if q.plates_depuis_ref:
                a.append(f"BOUGIES PLATES : {q.symbol} en a {q.plates_depuis_ref} sur la période de référence.")
    if "fin_donnees" in set(trades.get("raison", [])):
        a.append("FIN DES DONNÉES : position(s) clôturée(s) à la dernière clôture disponible.")
    return a


# ---------------- écriture ----------------

def _json(x):
    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating, float)):
            return None if math.isnan(o) else float(o)
        if isinstance(o, (pd.Timestamp, datetime, np.datetime64)):
            return pd.Timestamp(o).isoformat()
        if isinstance(o, Path):
            return str(o)
        raise TypeError(type(o))
    return json.dumps(x, indent=2, sort_keys=True, ensure_ascii=False, default=conv)


def ecrire(nom: str, params: dict, trades: pd.DataFrame, evenements: pd.DataFrame,
           qualite: pd.DataFrame | None = None, racine: Path = REPORTS, git: dict | None = None,
           maintenant: datetime | None = None, tables: dict | None = None,
           portefeuille: dict | None = None, version: str = "v0.3") -> Path:
    """tables : {"nom.csv": DataFrame} écrits tels quels ; portefeuille : résumé de src.portefeuille
    (remplace l'equity séquentielle, inadaptée à des positions simultanées)."""
    manquantes = [k for k in CLES_OBLIGATOIRES if k not in params]
    if manquantes:
        raise RapportInvalide(f"paramètres obligatoires manquants : {manquantes}")
    for k in ("capital", "risque_pct", "compose"):
        if k not in params["risque"]:
            raise RapportInvalide(f"risque.{k} manquant")
    git = etat_git() if git is None else git
    maintenant = maintenant or datetime.now()

    dossier = racine / f"{maintenant:%Y-%m-%d}_{version}_{nom}"
    k = 2
    while dossier.exists():  # jamais d'écrasement d'un rapport existant
        dossier = racine / f"{maintenant:%Y-%m-%d}_{version}_{nom}_{k}"
        k += 1
    dossier.mkdir(parents=True)

    res = resume(trades, evenements, params, argent=portefeuille is None)
    if portefeuille is not None:
        res["portefeuille"] = portefeuille
    avert = avertissements(params, trades, evenements, git, qualite)
    if portefeuille is not None:
        x = portefeuille.get("exposition", {})
        avert.append("DRAWDOWN : calculé sur l'equity RÉALISÉE (trades clôturés) ; pertes latentes non comptées, "
                     "le vrai drawdown peut être plus grand.")
        avert.append(f"RISQUE SIMULTANÉ : sans plafond en v0.3 ; maximum observé {x.get('risque_ouvert_max_pct', 0):.2%} "
                     f"du capital, {x.get('positions_simultanees_max', 0)} position(s) ouvertes.")
    (dossier / "params.json").write_text(_json({**params, "git": git, "execution": maintenant.isoformat(timespec="seconds"),
                                                "nom": nom}), encoding="utf-8")
    trades.to_csv(dossier / "resultats.csv", index=False, sep=";", na_rep="NaN")
    evenements.to_csv(dossier / "evenements.csv", index=False, sep=";")
    for nom_f, table in (tables or {}).items():
        table.to_csv(dossier / nom_f, index=False, sep=";", na_rep="NaN")
    (dossier / "resume.json").write_text(_json(res), encoding="utf-8")
    (dossier / "avertissements.txt").write_text("\n".join(f"- {x}" for x in avert) + "\n", encoding="utf-8")
    return dossier
