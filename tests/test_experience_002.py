"""Tests du script de l'expérience 002, SANS l'exécuter : aucune évaluation sur les données réelles."""
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import scripts.experience_002 as x
from src import portefeuille as pf
from src import recherche as rc
from src.couts import Hypotheses
from src.engine import Params
from strategies import momentum
from tests.outils import bougies

GIT_PROPRE = {"commit": "a" * 40, "tag": None, "dirty": False}
SOURCE = Path(x.__file__).read_text(encoding="utf-8")
INFO = {"symbol": "X", "swap_long": -1.0, "swap_short": -1.0, "swap_mode": 1, "unite": "points",
        "triple_swap_jour": "mercredi", "point": 0.01}


@pytest.fixture(autouse=True)
def protocole_historique_002(monkeypatch):
    """002 a été évaluée sous v0.4.1 : ses tests de logique simulent ce protocole. Le protocole réel (v0.4.2) est
    vérifié séparément par test_protocole_actuel_bloque_aussi_002."""
    monkeypatch.setattr(rc, "VERSION_PROTOCOLE", "v0.4.1")


def test_protocole_actuel_bloque_aussi_002(monkeypatch, dossiers):
    source = (Path(rc.__file__)).read_text(encoding="utf-8")
    assert 'VERSION_PROTOCOLE = "v0.4.2"' in source  # protocole réellement actif
    monkeypatch.setattr(rc, "VERSION_PROTOCOLE", "v0.4.2")
    with pytest.raises(SystemExit, match="protocole actif v0.4.2, attendu v0.4.1"):
        x.verifier_preconditions(GIT_PROPRE, *dossiers)  # même avec un dossier vierge, 002 ne peut plus partir


@pytest.fixture
def dossiers(tmp_path):
    """Copie de l'hypothèse 002 et de la décision 001 dans un dossier temporaire."""
    d2, d1 = tmp_path / "002", tmp_path / "001"
    d2.mkdir()
    d1.mkdir()
    shutil.copy(x.DOSSIER / "hypothese.md", d2 / "hypothese.md")
    shutil.copy(x.DOSSIER_001 / "decision.json", d1 / "decision.json")
    return d2, d1


def marche(seed, n=3700, debut="2012-08-06"):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[100, c[:-1]]
    df = bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)), debut=debut)
    df["spread"] = 10
    return df


# ---------------- variantes et protocole ----------------

def test_six_variantes_exactes_preparees():
    assert x.VARIANTES_ATTENDUES == momentum.GRILLE
    prep = x.preparer({"A": marche(1, 300)}, {"A": INFO})
    assert [n for n, _ in prep["variantes"]] == ["L60_K3", "L60_K5", "L125_K3", "L125_K5", "L250_K3", "L250_K5"]
    assert [p for _, p in prep["variantes"]] == x.VARIANTES_ATTENDUES


def test_variante_hors_grille_refusee(dossiers, monkeypatch):
    with pytest.raises(ValueError, match="hors grille"):
        momentum.variante({"L": 90, "k": 3.0})
    monkeypatch.setattr(momentum, "GRILLE", momentum.GRILLE + [{"L": 90, "k": 3.0}])
    with pytest.raises(SystemExit, match="grille"):
        x.verifier_variantes(dossiers[0])


def test_protocole_v041_obligatoire(dossiers, monkeypatch):
    assert x.PROTOCOLE_ATTENDU == "v0.4.1" == rc.VERSION_PROTOCOLE
    monkeypatch.setattr(rc, "VERSION_PROTOCOLE", "v0.4")
    with pytest.raises(SystemExit, match="protocole"):
        x.verifier_preconditions(GIT_PROPRE, *dossiers)


def test_periodes_evaluees_entrainement_et_validation_seulement():
    assert x.PERIODES_EVALUEES == ("entrainement", "validation")
    assert rc.PERIODES["entrainement"] == ("2012-08-06", "2019-12-31")
    assert rc.PERIODES["validation"] == ("2020-01-01", "2022-12-31")


def test_002_executee_ne_peut_plus_etre_relancee():
    """État post-exécution (2026-10-28) : le dépôt réel contient les résultats de 002, le lancement est refusé."""
    with pytest.raises(SystemExit, match="ne se rejoue pas"):
        x.verifier_preconditions(GIT_PROPRE)


@pytest.mark.parametrize("git,motif", [({"commit": None, "dirty": None}, "dépôt"),
                                       ({"commit": "a" * 40, "dirty": True}, "dépôt")])
def test_depot_non_propre_refuse(dossiers, git, motif):
    with pytest.raises(SystemExit, match=motif):
        x.verifier_preconditions(git, *dossiers)


def test_hypothese_absente_refusee(dossiers):
    (dossiers[0] / "hypothese.md").unlink()
    with pytest.raises(SystemExit, match="hypothese"):
        x.verifier_preconditions(GIT_PROPRE, *dossiers)


# ---------------- OOS ----------------

def test_le_script_n_ouvre_jamais_l_oos():
    for interdit in ("ouvrir_oos", "oos_autorise", '"oos")', "'oos')"):
        assert interdit not in SOURCE, interdit
    assert x.ETAT_FINAL == "VALIDATION_COMPLETE — OOS_LOCKED" and "OOS_LOCKED" in SOURCE


def test_oos_deja_ouvert_bloque_le_lancement(dossiers):
    (dossiers[0] / "oos_ouvert.json").write_text("{}")
    with pytest.raises(SystemExit, match="déjà des résultats"):
        x.verifier_preconditions(GIT_PROPRE, *dossiers)


def test_preparation_ne_cree_aucun_fichier(dossiers):
    avant = sorted(p.name for p in dossiers[0].iterdir())
    x.verifier_preconditions(GIT_PROPRE, *dossiers)
    x.preparer({"A": marche(1, 300)}, {"A": INFO})
    assert sorted(p.name for p in dossiers[0].iterdir()) == avant == ["hypothese.md"]
    assert not list(dossiers[0].parent.rglob("oos_ouvert.json"))


# ---------------- pas de rejeu ----------------

@pytest.mark.parametrize("fichier", ["decision.json", "resultats.csv", "experience.json"])
def test_experience_non_rejouable(dossiers, fichier):
    (dossiers[0] / fichier).write_text("{}")
    with pytest.raises(SystemExit, match="ne se rejoue pas"):
        x.verifier_preconditions(GIT_PROPRE, *dossiers)


def test_main_s_arrete_avant_toute_evaluation_si_decision_existe(dossiers, monkeypatch, tmp_path):
    reg = tmp_path / "registre_isole.csv"
    (dossiers[0] / "decision.json").write_text("{}")
    monkeypatch.setattr(x, "DOSSIER", dossiers[0])
    monkeypatch.setattr(x, "DOSSIER_001", dossiers[1])
    monkeypatch.setattr(x, "REGISTRE", reg)
    monkeypatch.setattr(x.rapport, "etat_git", lambda: GIT_PROPRE)
    monkeypatch.setattr(x.data, "charger", lambda *a, **k: pytest.fail("aucune donnée ne doit être chargée"))
    monkeypatch.setattr(x.rc, "evaluer", lambda *a, **k: pytest.fail("aucune évaluation ne doit être lancée"))
    avant = rc.REGISTRE.read_bytes()
    with pytest.raises(SystemExit, match="ne se rejoue pas"):
        x.main()
    assert not reg.exists() and rc.REGISTRE.read_bytes() == avant  # aucun registre touché


def test_le_registre_utilise_par_le_script_est_redirigeable():
    """Garde-fou de l'incident de préparation : le chemin du registre est passé explicitement."""
    assert "rc.enregistrer_variantes(EXP, noms, git[\"commit\"], REGISTRE)" in SOURCE


# ---------------- registre ----------------

def test_six_variantes_inscrites_au_registre(tmp_path):
    reg = tmp_path / "registre.csv"
    r0 = pd.read_csv(rc.REGISTRE, sep=";", dtype=str)
    r0[r0["experience"] == "001"].to_csv(reg, sep=";", index=False)  # état du registre AVANT 002
    prep = x.preparer({"A": marche(1, 300)}, {"A": INFO})
    assert rc.enregistrer_variantes(x.EXP, prep["variantes"], "abc", reg) == 12
    r = pd.read_csv(reg, sep=";", dtype=str)
    assert r.loc[r["experience"] == "002", "variante"].tolist() == [n for n, _ in prep["variantes"]]
    assert (r["experience"] == "001").sum() == 6  # les 6 variantes de 001 restent intactes
    assert rc.enregistrer_variantes(x.EXP, prep["variantes"], "abc", reg) == 12  # pas de doublon


def test_registre_reel_apres_002():
    """Les 6 de 001 (commit 94be67c) puis les 6 de 002 (commit 172705d), sans doublon ; les expériences suivantes
    s'ajoutent sans modifier ces lignes."""
    r = pd.read_csv(rc.REGISTRE, sep=";", dtype=str)
    assert not r.duplicated(["experience", "variante"]).any()
    assert r["experience"].tolist()[:12] == ["001"] * 6 + ["002"] * 6
    assert r.loc[r["experience"] == "001", "variante"].tolist() == ["N20_S2", "N20_S3", "N55_S2", "N55_S3",
                                                                    "N100_S2", "N100_S3"]
    assert r.loc[r["experience"] == "002", "variante"].tolist() == [momentum.nom_variante(p)
                                                                    for p in x.VARIANTES_ATTENDUES]
    assert set(r.loc[r["experience"] == "001", "commit"].str[:7]) == {"94be67c"}
    assert set(r.loc[r["experience"] == "002", "commit"].str[:7]) == {"172705d"}


# ---------------- retournement ----------------

def test_strategie_executee_avec_retournement(monkeypatch):
    vus = []
    vrai = pf.backtest

    def espion(*a, **k):
        vus.append(k.get("retournement"))
        return vrai(*a, **k)
    monkeypatch.setattr(pf, "backtest", espion)
    infos = {s: {**INFO, "symbol": s} for s in "AB"}
    pf.executer({s: marche(i, 400) for i, s in enumerate("AB")}, momentum.variante(x.VARIANTES_ATTENDUES[0]),
                Params(None), infos, Hypotheses("fixe", 10, 0))
    assert vus == [True, True]


def test_benchmark_avec_les_memes_regles_de_retournement(monkeypatch):
    vus = []
    vrai = rc.backtest

    def espion(*a, **k):
        vus.append(k.get("retournement"))
        return vrai(*a, **k)
    monkeypatch.setattr(rc, "backtest", espion)
    m = {"A": marche(3)}
    rc.benchmark_aleatoire(m, momentum.variante(x.VARIANTES_ATTENDUES[0]), {"A": INFO},
                           {"A": Hypotheses("fixe", 10, 0)}, "validation", {"A": 10}, n_tirages=2, seed=1)
    assert vus and all(v is True for v in vus)


def test_plateau_avec_les_parametres_de_momentum():
    nom = momentum.nom_variante
    esp = {nom(p): 0.1 for p in momentum.GRILLE}
    esp["L125_K5"] = -0.1
    pl = rc.plateau(esp, momentum.GRILLE, nom, cle_longueur="L", cle_stop="k")
    assert not pl["L125_K3"] and not pl["L60_K5"] and not pl["L250_K5"]  # voisins de L125_K5
    assert pl["L60_K3"] and pl["L250_K3"]


# ---------------- 001 et sécurité ----------------

def test_experience_001_inchangee_et_002_jugee_oos_ferme():
    import json
    racine = Path(x.__file__).resolve().parent.parent
    r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "experiments/001-donchian-baseline"], cwd=racine)
    assert r.returncode == 0  # aucun fichier de 001 modifié par rapport au dernier commit
    d = json.loads((x.DOSSIER / "decision.json").read_text("utf-8"))
    assert d["etat"] == x.ETAT_FINAL and d["protocole"] == "v0.4.1"
    assert d["oos_ouvert_pour"] is None and d["candidats_oos"] == []
    assert [v["statut"] for v in d["variantes"].values()] == ["REJECT"] * 6
    assert len(list((x.DOSSIER / "rapports").iterdir())) == 12  # 6 variantes x (entraînement, validation)
    assert not any("oos" in p.name for p in (x.DOSSIER / "rapports").iterdir())
    assert not list(rc.EXPERIMENTS.rglob("oos_ouvert.json"))  # OOS toujours vierge


def test_aucune_fonction_d_ordre_ni_mt5():
    for interdit in ("order_send", "order_check", "positions_send", "MetaTrader5", "mt5."):
        assert interdit not in SOURCE, interdit
