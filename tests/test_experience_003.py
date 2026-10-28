"""Tests du script de l'expérience 003 SANS l'exécuter : toutes les dépendances lourdes sont remplacées par des
stubs, et chaque test qui écrit utilise un registre et des dossiers TEMPORAIRES (le vrai registre est contrôlé)."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import scripts.experience_003 as x
from src import portefeuille as pf
from src import recherche as rc
from src.couts import Hypotheses
from src.engine import Params
from strategies import reversion
from tests.outils import bougies

GIT_PROPRE = {"commit": "b" * 40, "tag": None, "dirty": False}
SOURCE = Path(x.__file__).read_text(encoding="utf-8")
VRAI_REGISTRE = rc.REGISTRE
INFO = {"symbol": "X", "swap_long": -1.0, "swap_short": -1.0, "swap_mode": 1, "unite": "points",
        "triple_swap_jour": "mercredi", "point": 0.01}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Copie isolée : proposition, registre (12 variantes), décisions 001/002 ; dossier 003 vierge."""
    exp = tmp_path / "experiments"
    hist = {}
    for nom, d in x.DOSSIERS_HISTORIQUES.items():
        (exp / d.name).mkdir(parents=True)
        shutil.copy(d / "decision.json", exp / d.name / "decision.json")
        hist[nom] = exp / d.name
    reg = exp / "registre_variantes.csv"
    shutil.copy(VRAI_REGISTRE, reg)
    prop = tmp_path / "proposition.md"
    shutil.copy(x.PROPOSITION, prop)
    monkeypatch.setattr(x, "DOSSIER", exp / "003-reversion-seance-extreme")
    monkeypatch.setattr(x, "PROPOSITION", prop)
    monkeypatch.setattr(x, "REGISTRE", reg)
    monkeypatch.setattr(x, "DOSSIERS_HISTORIQUES", hist)
    return {"exp": exp, "reg": reg, "prop": prop, "dossier": exp / "003-reversion-seance-extreme",
            "avant": VRAI_REGISTRE.read_bytes()}


def marche_long():
    """Marché synthétique de 2012 à 2026 : permet de vérifier que l'OOS est coupé au chargement."""
    rng = np.random.default_rng(0)
    n = 3700
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[100, c[:-1]]
    df = bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)), debut="2012-08-06")
    df["spread"] = 10
    return df


def metriques_bonnes(symboles):
    return {"trades": 400, "esperance_R": 0.2, "profit_factor": 1.6, "marches_positifs": 10, "marches_eligibles": 12,
            "contribution_max": 0.15, "marche_contribution_max": symboles[0], "drawdown_realise_pct": 0.05,
            "pire_serie_pertes": 6, "part_max_une_annee": 0.2, "annees": {2015: 1.0, 2021: 1.0},
            "trades_par_marche": {s: 30 for s in symboles}}


@pytest.fixture
def simulation(env, monkeypatch):
    """Exécution SIMULÉE : données synthétiques, évaluation, métriques, rapports et benchmark remplacés."""
    appels = {"evaluer": [], "benchmark": [], "rapports": [], "dates_max": []}
    monkeypatch.setattr(x.rapport, "etat_git", lambda: GIT_PROPRE)
    monkeypatch.setattr(x.data, "charger", lambda s: marche_long())
    monkeypatch.setattr(x.couts, "info_symbole", lambda s: {**INFO, "symbol": s})

    def evaluer(marches, f, infos, hyp, periode, **k):
        assert periode in ("entrainement", "validation") and not k.get("oos_autorise")
        appels["evaluer"].append(periode)
        appels["dates_max"].append(max(df["time"].max() for df in marches.values()))
        return {"trades": pd.DataFrame(), "evenements": pd.DataFrame(),
                "analyse": {"trades": pd.DataFrame(), "tables": {}, "resume": {}}}
    monkeypatch.setattr(x.rc, "evaluer", evaluer)
    monkeypatch.setattr(x.rc, "metriques", lambda ev, symboles: metriques_bonnes(symboles))
    monkeypatch.setattr(x.rapport, "ecrire", lambda nom, *a, **k: appels["rapports"].append(nom))

    def benchmark(marches, f, infos, hyp, periode, tpm, params, n, graine):
        appels["benchmark"].append({"periode": periode, "n": n, "graine": graine, "params": params,
                                    "signal": f(next(iter(marches.values())))})
        return [{"tirage": k + 1, "graine": [graine, k], "trades": 300, "esperance_R": -0.05 + k * 1e-4}
                for k in range(n)]
    monkeypatch.setattr(x.rc, "benchmark_entrees_randomisees", benchmark)
    x.main()
    return {**env, **appels}


# ---------------- variantes, protocole, benchmark ----------------

def test_six_variantes_exactes():
    assert x.VARIANTES_ATTENDUES == reversion.GRILLE == [{"z": z, "H": H} for z in (1.5, 2.0, 2.5) for H in (3, 5)]
    prep = x.preparer({"A": marche_long()})
    assert [n for n, _ in prep["variantes"]] == ["Z1p5_H3", "Z1p5_H5", "Z2_H3", "Z2_H5", "Z2p5_H3", "Z2p5_H5"]


def test_variante_hors_grille_refusee(env, monkeypatch):
    with pytest.raises(ValueError, match="hors grille"):
        reversion.variante({"z": 3.0, "H": 3})
    monkeypatch.setattr(reversion, "GRILLE", reversion.GRILLE + [{"z": 3.0, "H": 3}])
    with pytest.raises(SystemExit, match="grille"):
        x.verifier_preconditions(GIT_PROPRE)


def test_protocole_v042_obligatoire(env, monkeypatch):
    assert x.PROTOCOLE_ATTENDU == "v0.4.2" == rc.VERSION_PROTOCOLE
    x.verifier_preconditions(GIT_PROPRE)  # état réel copié : conditions remplies
    monkeypatch.setattr(rc, "VERSION_PROTOCOLE", "v0.4.1")
    with pytest.raises(SystemExit, match="protocole"):
        x.verifier_preconditions(GIT_PROPRE)


def test_benchmark_v042_utilise_avec_200_tirages_conserves(simulation):
    b = simulation["benchmark"]
    assert len(b) == 6 and all(c["periode"] == "validation" and c["n"] == 200 for c in b)
    assert {c["graine"] for c in b} == {x.SEED} and all(c["params"] == Params(None) for c in b)
    fichiers = sorted((simulation["dossier"] / "benchmark").glob("*.json"))
    assert [f.stem for f in fichiers] == sorted(n for n, _ in x.preparer({"A": marche_long()})["variantes"])
    contenu = json.loads(fichiers[0].read_text("utf-8"))
    assert contenu["protocole"] == "v0.4.2" and len(contenu["tirages"]) == 200
    assert contenu["benchmark"]["nom"] == "entrées randomisées à sorties identiques"
    assert "percentile_strategie" in contenu["resume"]
    assert "benchmark_aleatoire(" not in SOURCE  # l'ancien benchmark n'est pas utilisé


# ---------------- OOS ----------------

def test_le_script_ne_demande_jamais_l_oos():
    for interdit in ("ouvrir_oos", "oos_autorise", '"oos")', "'oos')"):
        assert interdit not in SOURCE, interdit


def test_arret_validation_complete_oos_locked_meme_avec_des_keep(simulation):
    d = json.loads((simulation["dossier"] / "decision.json").read_text("utf-8"))
    assert d["etat"] == "VALIDATION_COMPLETE — OOS_LOCKED" and d["protocole"] == "v0.4.2"
    assert d["candidats_oos"] and d["oos_ouvert_pour"] is None  # des KEEP simulés, et pourtant aucun OOS
    assert simulation["evaluer"] == ["entrainement", "entrainement", "validation", "validation"] * 6
    assert not list(simulation["exp"].rglob("oos_ouvert.json"))


def test_aucune_donnee_oos_chargee_ni_evaluee(simulation):
    assert max(simulation["dates_max"]) <= pd.Timestamp("2022-12-31")  # tronqué dès le chargement
    assert all(c["signal"]["signal"].index.max() < 3700 for c in simulation["benchmark"])
    rapports = simulation["rapports"]
    assert len(rapports) == 12 and not any("oos" in r for r in rapports)


# ---------------- registre ----------------

def test_inscription_des_6_variantes_sans_doublon_registre_isole(simulation):
    reg = pd.read_csv(simulation["reg"], sep=";", dtype=str)
    assert len(reg) == 18 and not reg.duplicated(["experience", "variante"]).any()
    assert reg.loc[reg["experience"] == "003", "variante"].tolist() == \
        ["Z1p5_H3", "Z1p5_H5", "Z2_H3", "Z2_H5", "Z2p5_H3", "Z2p5_H5"]
    assert set(reg.loc[reg["experience"] == "003", "commit"]) == {GIT_PROPRE["commit"]}
    assert VRAI_REGISTRE.read_bytes() == simulation["avant"]  # le vrai registre n'a pas bougé d'un octet


def test_registre_passe_explicitement():
    assert 'rc.enregistrer_variantes(EXP, noms, git["commit"], registre)' in SOURCE


@pytest.mark.parametrize("lignes", [11, 13])
def test_registre_inattendu_bloque(env, lignes):
    reg = pd.read_csv(env["reg"], sep=";", dtype=str)
    reg = reg.iloc[:lignes] if lignes < 12 else pd.concat([reg, reg.iloc[[0]].assign(experience="999")])
    reg.to_csv(env["reg"], sep=";", index=False)
    with pytest.raises(SystemExit, match="registre inattendu"):
        x.verifier_preconditions(GIT_PROPRE)


# ---------------- pas de rejeu ----------------

def test_003_ne_se_rejoue_pas_apres_resultats(simulation):
    with pytest.raises(SystemExit, match="ne se rejoue pas"):
        x.verifier_preconditions(GIT_PROPRE)


@pytest.mark.parametrize("fichier", ["decision.json", "resultats.csv", "benchmark", "hypothese.md"])
def test_un_seul_fichier_de_resultat_suffit_a_bloquer(env, fichier):
    env["dossier"].mkdir(parents=True)
    (env["dossier"] / fichier).mkdir() if fichier == "benchmark" else (env["dossier"] / fichier).write_text("{}")
    with pytest.raises(SystemExit, match="ne se rejoue pas"):
        x.verifier_preconditions(GIT_PROPRE)


@pytest.mark.parametrize("git", [{"commit": None, "dirty": None}, {"commit": "b" * 40, "dirty": True}])
def test_depot_non_propre_bloque(env, git):
    with pytest.raises(SystemExit, match="dépôt"):
        x.verifier_preconditions(git)


def test_proposition_absente_ou_non_validee_bloque(env):
    texte = env["prop"].read_text(encoding="utf-8")
    env["prop"].write_text(texte.replace("Statut : VALIDÉE", "Statut : brouillon"), encoding="utf-8")
    with pytest.raises(SystemExit, match="VALIDÉE"):
        x.verifier_preconditions(GIT_PROPRE)
    env["prop"].unlink()
    with pytest.raises(SystemExit, match="proposition"):
        x.verifier_preconditions(GIT_PROPRE)


def test_oos_ouvert_quelque_part_bloque(env):
    (env["exp"] / "001-donchian-baseline" / "oos_ouvert.json").write_text("{}")
    with pytest.raises(SystemExit, match="OOS"):
        x.verifier_preconditions(GIT_PROPRE)


# ---------------- 001, 002, sécurité ----------------

def test_001_002_modifiees_bloquent(env):
    f = env["exp"] / "002-momentum-serie-temporelle" / "decision.json"
    d = json.loads(f.read_text("utf-8"))
    d["oos_ouvert_pour"] = "L60_K3"
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit, match="002"):
        x.verifier_preconditions(GIT_PROPRE)


def test_001_002_et_registre_reels_intacts():
    racine = Path(x.__file__).resolve().parent.parent
    r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "experiments"], cwd=racine)
    assert r.returncode == 0
    assert not (rc.EXPERIMENTS / "003-reversion-seance-extreme").exists()  # 003 jamais exécutée


def test_aucune_fonction_d_ordre_ni_mt5():
    for interdit in ("order_send", "order_check", "positions_send", "MetaTrader5", "mt5."):
        assert interdit not in SOURCE, interdit


# ---------------- transmission des paramètres ----------------

def test_transmission_z_H_duree_stop_retournement(monkeypatch):
    vus = []
    vrai = pf.backtest

    def espion(df, signal, stop, params, sortie, sl, ss, retournement, duree_max):
        vus.append((retournement, duree_max, stop))
        return vrai(df, signal, stop, params, sortie, sl, ss, retournement=retournement, duree_max=duree_max)
    monkeypatch.setattr(pf, "backtest", espion)
    df = marche_long().iloc[:400].reset_index(drop=True)
    from src.indicateurs import atr
    for nom, p in x.preparer({"A": df})["variantes"]:
        pf.executer({"A": df}, reversion.variante(p), Params(None), {"A": {**INFO, "symbol": "A"}},
                    Hypotheses("fixe", 10, 0))
        rt, duree, stop = vus[-1]
        assert rt is False and duree == p["H"]
        pd.testing.assert_series_equal(stop, atr(df, 20) * 2.0)
        s = reversion.signaux(df, p["z"], p["H"])
        assert s["duree_max"] == p["H"] and nom == reversion.nom_variante(p)
