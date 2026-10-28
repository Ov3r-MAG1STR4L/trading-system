import json
import math
import subprocess
from datetime import datetime

import pandas as pd
import pytest

from src import rapport
from src.couts import SWAP_UNAVAILABLE, Hypotheses, appliquer
from src.data import STATUT_GAP
from src.engine import VERSION_MOTEUR, Params, backtest
from tests.outils import PLAT, bougies

INFO = {"symbol": "TEST", "swap_long": -2.0, "swap_short": 1.0, "swap_mode": 1, "unite": "points",
        "triple_swap_jour": "mercredi", "point": 0.01}
GIT_PROPRE = {"commit": "a" * 40, "tag": "v0.2-4-gaaaaaaa", "dirty": False}
QUAND = datetime(2026, 10, 28, 12, 0, 0)


def params(h=Hypotheses("historique", 10, 5)):
    return {"strategie": "test_synthetique", "params_strategie": {"stop_dist": 5, "target_r": 2.0},
            "marches": ["TEST"], "periode": {"debut": "2020-01-06", "fin": "2020-01-31"},
            "source_donnees": "synthétique", "risque": {"capital": 10_000, "risque_pct": 0.01, "compose": True},
            "couts": h.en_dict(), "version_moteur": VERSION_MOTEUR, "date_swaps": "2026-10-28"}


def scenario(info=INFO, h=Hypotheses("historique", 10, 5)):
    """3 trades : un objectif, un stop, un qui traverse un DATA_GAP ; plus une entrée refusée par un trou."""
    ohlc = [PLAT, PLAT, PLAT, (101, 111, 100, 108),        # trade 1 : objectif
            PLAT, PLAT, (99, 100, 94, 96),                 # trade 2 : stop
            PLAT, PLAT, PLAT, (102, 103, 101, 102), (99, 100, 94, 96),  # trade 3 : traverse le trou (10), stop en 11
            PLAT, PLAT, PLAT]                              # signal en 13 refusé par le trou avant 14
    df = bougies(ohlc, gaps_avant=(10, 14))
    df["spread"] = [0, 30] * 7 + [0]
    sig = pd.Series(0.0, index=df.index)
    sig[[1, 4, 8, 13]] = 1
    trades, ev = backtest(df, sig, pd.Series(5.0, index=df.index), Params(2.0))
    trades = appliquer(trades, df, info, h)
    trades.insert(0, "symbol", info["symbol"])
    return trades, ev


def ecrire(tmp_path, nom="essai", info=INFO, git=GIT_PROPRE, h=Hypotheses("historique", 10, 5), **kw):
    trades, ev = scenario(info, h)
    return rapport.ecrire(nom, params(h), trades, ev, racine=tmp_path, git=git, maintenant=QUAND, **kw)


def lire(d, f):
    return json.loads((d / f).read_text(encoding="utf-8"))


# ---------------- dossier et fichiers ----------------

def test_creation_du_dossier_et_des_fichiers(tmp_path):
    d = ecrire(tmp_path)
    assert d.name == "2026-10-28_v0.3_essai"
    for f in ("params.json", "resultats.csv", "resume.json", "avertissements.txt", "evenements.csv"):
        assert (d / f).exists(), f


def test_un_rapport_existant_n_est_jamais_ecrase(tmp_path):
    d1, d2 = ecrire(tmp_path), ecrire(tmp_path)
    assert d1 != d2 and d2.name == "2026-10-28_v0.3_essai_2"


def test_parametres_sauvegardes_sans_valeur_implicite(tmp_path):
    p = lire(ecrire(tmp_path), "params.json")
    assert p["couts"] == {"spread_mode": "historique", "spread_points": 10, "slippage_points": 5, "swaps": True}
    assert p["risque"] == {"capital": 10_000, "risque_pct": 0.01, "compose": True}
    assert p["marches"] == ["TEST"] and p["periode"]["debut"] == "2020-01-06"
    assert p["version_moteur"] == VERSION_MOTEUR and p["execution"] == "2026-10-28T12:00:00"


@pytest.mark.parametrize("cle", rapport.CLES_OBLIGATOIRES)
def test_parametre_obligatoire_manquant_refuse(tmp_path, cle):
    trades, ev = scenario()
    p = params()
    del p[cle]
    with pytest.raises(rapport.RapportInvalide, match=cle):
        rapport.ecrire("x", p, trades, ev, racine=tmp_path, git=GIT_PROPRE, maintenant=QUAND)


def test_resultats_sauvegardes_tous_les_trades(tmp_path):
    d = ecrire(tmp_path)
    r = pd.read_csv(d / "resultats.csv", sep=";")
    assert len(r) == 3
    assert r["raison"].tolist() == ["objectif", "stop", "stop"]
    assert {"R", "R_execution", "swap_R", "R_net", "statut_swap", "traverse_gap"} <= set(r.columns)


# ---------------- résumé brut -> coûts -> net ----------------

def test_resume_brut_couts_net(tmp_path):
    s = lire(ecrire(tmp_path), "resume.json")
    b = s["brut"]
    assert b["trades"] == 3 and b["total_R"] == pytest.approx(2 - 1 - 1)
    assert b["taux_reussite"] == pytest.approx(1 / 3)
    assert b["profit_factor"] == pytest.approx(1.0)
    assert b["pire_serie_pertes"] == 2 and b["meilleure_serie_gains"] == 1
    c, n = s["couts_R"], s["net"]
    assert c["spread"] > 0 and c["slippage"] > 0 and c["swap_connu"] < 0
    assert n["total_R"] == pytest.approx(b["total_R"] - c["total_connu"])
    assert n["total_R"] < b["total_R"]
    assert n["resultat_monetaire"] < b["resultat_monetaire"]
    # equity composée : 10 000 -> 10 200 -> 10 098 -> 9 997,02 ; plus haut 10 200
    assert b["drawdown_realise"] == pytest.approx(10_200 * (1 - 0.99 ** 2))
    assert b["drawdown_realise_pct"] == pytest.approx(1 - 0.99 ** 2)


def test_resume_data_gap_traverses_et_refuses(tmp_path):
    s = lire(ecrire(tmp_path), "resume.json")
    assert s["data_gap"] == {"trous": 2, "trades_traversant": 1, "entrees_refusees": 1}


def test_aucun_trade(tmp_path):
    trades, ev = scenario()
    d = rapport.ecrire("vide", params(), trades.iloc[0:0], ev.iloc[0:0], racine=tmp_path, git=GIT_PROPRE,
                       maintenant=QUAND)
    s = lire(d, "resume.json")
    assert s["brut"]["trades"] == 0 and s["brut"]["capital_final"] == 10_000


# ---------------- états explicites ----------------

def test_etat_data_gap_conserve(tmp_path):
    d = ecrire(tmp_path)
    ev = pd.read_csv(d / "evenements.csv", sep=";")
    assert (ev["statut"] == STATUT_GAP).all() and len(ev) == 2
    r = pd.read_csv(d / "resultats.csv", sep=";")
    assert r["traverse_gap"].tolist() == [False, False, True]


def test_swap_unavailable_conserve_et_net_non_calcule(tmp_path):
    d = ecrire(tmp_path, info={**INFO, "symbol": "INDICE", "swap_mode": 3})
    r = pd.read_csv(d / "resultats.csv", sep=";")
    assert (r["statut_swap"] == SWAP_UNAVAILABLE).any()
    assert r.loc[r["statut_swap"] == SWAP_UNAVAILABLE, "R_net"].isna().all()  # NaN, jamais 0
    s = lire(d, "resume.json")
    assert s["net"]["statut"] == SWAP_UNAVAILABLE and s["couts_R"]["trades_swap_unavailable"] >= 1
    assert "brut" in s and s["brut"]["trades"] == 3  # le brut reste mesurable
    assert f"{SWAP_UNAVAILABLE} : swap non convertible pour INDICE" in (d / "avertissements.txt").read_text("utf-8")


# ---------------- avertissements ----------------

def test_avertissements_presents(tmp_path):
    qual = pd.DataFrame({"symbol": ["TEST"], "plates_depuis_ref": [3]})
    a = (ecrire(tmp_path, qualite=qual) / "avertissements.txt").read_text("utf-8")
    for mot in ("SOURCE", "SPREAD : historique MT5 avec plancher de 10", "SLIPPAGE : 5",
                "SWAPS : valeurs actuelles", "DATA_GAP : 2 trou(s)", "1 entrée(s) refusée(s)",
                "BOUGIES PLATES : TEST"):
        assert mot in a, mot
    assert "GIT" not in a  # dépôt propre : pas d'alerte


def test_avertissements_slippage_nul_et_swaps_desactives(tmp_path):
    a = (ecrire(tmp_path, h=Hypotheses("fixe", 20, 0, swaps=False)) / "avertissements.txt").read_text("utf-8")
    assert "SLIPPAGE : 0" in a and "SWAPS : désactivés" in a and "valeur FIXE de 20" in a


# ---------------- Git ----------------

def test_commit_git_enregistre(tmp_path):
    assert lire(ecrire(tmp_path), "params.json")["git"]["commit"] == "a" * 40


def test_depot_dirty_signale(tmp_path):
    d = ecrire(tmp_path, git={**GIT_PROPRE, "dirty": True})
    assert "GIT : dépôt modifié (dirty)" in (d / "avertissements.txt").read_text("utf-8")


def test_commit_absent_signale(tmp_path):
    d = ecrire(tmp_path, git={"commit": None, "tag": None, "dirty": None})
    assert "GIT : commit introuvable" in (d / "avertissements.txt").read_text("utf-8")


def _git(d, *args):
    subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)


def test_etat_git_reel_propre_puis_dirty(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "f.txt").write_text("a")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    g = rapport.etat_git(tmp_path)
    assert len(g["commit"]) == 40 and g["dirty"] is False
    (tmp_path / "f.txt").write_text("b")
    assert rapport.etat_git(tmp_path)["dirty"] is True


def test_etat_git_hors_depot(tmp_path):
    assert rapport.etat_git(tmp_path)["commit"] is None


# ---------------- reproductibilité ----------------

def test_deux_executions_identiques_produisent_les_memes_fichiers(tmp_path):
    d1, d2 = ecrire(tmp_path / "a"), ecrire(tmp_path / "b")
    for f in ("resultats.csv", "evenements.csv", "resume.json", "avertissements.txt", "params.json"):
        assert (d1 / f).read_bytes() == (d2 / f).read_bytes(), f


def test_rapport_ne_modifie_pas_les_trades(tmp_path):
    trades, ev = scenario()
    avant = trades.copy()
    rapport.ecrire("x", params(), trades, ev, racine=tmp_path, git=GIT_PROPRE, maintenant=QUAND)
    pd.testing.assert_frame_equal(trades, avant)


def test_stats_refuse_r_manquant():
    with pytest.raises(rapport.RapportInvalide):
        rapport.stats_r([1.0, math.nan])


def test_avertissement_fin_des_donnees():
    trades, ev = scenario()
    trades.loc[2, "raison"] = "fin_donnees"
    assert any("FIN DES DONNÉES" in x for x in rapport.avertissements(params(), trades, ev, GIT_PROPRE))


def test_fichier_non_suivi_ne_rend_pas_dirty(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "f.txt").write_text("a")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    (tmp_path / "nouveau_rapport.csv").write_text("x")
    assert rapport.etat_git(tmp_path)["dirty"] is False


def test_fichiers_reproductibles_sans_horodatage(tmp_path):
    t1 = datetime(2026, 1, 1, 9, 0, 0)
    t2 = datetime(2026, 1, 1, 18, 30, 0)
    trades, ev = scenario()
    d1 = rapport.ecrire("x", params(), trades, ev, racine=tmp_path / "a", git=GIT_PROPRE, maintenant=t1)
    d2 = rapport.ecrire("x", params(), trades, ev, racine=tmp_path / "b", git=GIT_PROPRE, maintenant=t2)
    for f in ("resultats.csv", "evenements.csv", "resume.json", "avertissements.txt"):
        assert (d1 / f).read_bytes() == (d2 / f).read_bytes(), f  # l'heure n'y apparaît pas
    assert (d1 / "params.json").read_bytes() != (d2 / "params.json").read_bytes()  # elle est dans params.json
