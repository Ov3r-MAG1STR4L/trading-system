import json

import numpy as np
import pandas as pd
import pytest

from src import recherche as rc
from src.couts import Hypotheses
from src.engine import verifier_sans_lookahead
from strategies import donchian
from tests.outils import bougies

INFO = {"symbol": "X", "swap_long": -1.0, "swap_short": -1.0, "swap_mode": 1, "unite": "points",
        "triple_swap_jour": "mercredi", "point": 0.01}


def marche(seed, n=3700):
    """Marché synthétique couvrant 2012-08-06 -> ~2026 (jours ouvrés)."""
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
    o = np.r_[100, c[:-1]]
    df = bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)), debut="2012-08-06")
    df["spread"] = 10
    return df


@pytest.fixture(scope="module")
def univers():
    marches = {s: marche(k) for k, s in enumerate("AB")}
    infos = {s: {**INFO, "symbol": s} for s in marches}
    hyp = {s: Hypotheses("historique", 10, 0) for s in marches}
    return marches, infos, hyp


# ---------------- Donchian ----------------

def test_grille_exactement_6_variantes_et_hors_grille_refusee():
    assert len(donchian.GRILLE) == 6
    assert {donchian.nom_variante(p) for p in donchian.GRILLE} == {"N20_S2", "N20_S3", "N55_S2", "N55_S3",
                                                                    "N100_S2", "N100_S3"}
    with pytest.raises(ValueError, match="hors grille"):
        donchian.variante({"n": 30, "stop_atr": 2.0})


@pytest.mark.parametrize("p", donchian.GRILLE)
def test_donchian_sans_lookahead(p):
    verifier_sans_lookahead(donchian.variante(p), marche(1, 400))


def test_donchian_breakout_sur_cas_ecrit_a_la_main():
    plat = [(100, 101, 99, 100)] * 25
    df = bougies(plat + [(100, 103, 100, 102.5)] + plat[:5] + [(100, 100, 96, 97)])
    s = donchian.signaux(df, 20, 2.0)
    assert s["signal"][25] == 1 and (s["signal"][:25] == 0).all()   # clôture 102,5 > plus haut 101 des 20 précédentes
    assert s["sortie_long"][31] and not s["sortie_short"][31]       # clôture 97 < plus bas 99 des 10 précédentes
    assert s["signal"][31] == -1                                    # et casse le plus bas des 20 : short


# ---------------- périodes et isolement de l'OOS ----------------

def test_periodes_contigues_et_figees():
    p = rc.PERIODES
    assert p["entrainement"] == ("2012-08-06", "2019-12-31")
    assert p["validation"] == ("2020-01-01", "2022-12-31") and p["oos"] == ("2023-01-01", "2026-10-27")


def test_tronquer_ne_laisse_aucune_bougie_apres_la_fin(univers):
    t = rc.tronquer(univers[0], "2019-12-31")
    assert all(df["time"].max() <= pd.Timestamp("2019-12-31") for df in t.values())


def test_entrainement_independant_des_donnees_posterieures(univers):
    marches, infos, hyp = univers
    f = donchian.variante(donchian.GRILLE[0])
    r1 = rc.evaluer(marches, f, infos, hyp, "entrainement")
    modif = {s: df.copy() for s, df in marches.items()}
    for df in modif.values():
        k = df["time"] > "2019-12-31"
        df.loc[k, ["open", "high", "low", "close"]] *= 10
    r2 = rc.evaluer(modif, f, infos, hyp, "entrainement")
    pd.testing.assert_frame_equal(r1["trades"], r2["trades"])
    assert (r1["trades"]["entry_time"] <= "2019-12-31").all() and (r1["trades"]["exit_time"] <= "2019-12-31").all()


def test_oos_interdit_sans_ouverture_explicite(univers):
    marches, infos, hyp = univers
    with pytest.raises(rc.OosDejaOuvert):
        rc.evaluer(marches, donchian.variante(donchian.GRILLE[0]), infos, hyp, "oos")


def test_ouverture_oos_unique(tmp_path):
    rc.ouvrir_oos(tmp_path, "N20_S2", "abc")
    assert json.loads((tmp_path / "oos_ouvert.json").read_text("utf-8"))["variante"] == "N20_S2"
    with pytest.raises(rc.OosDejaOuvert):
        rc.ouvrir_oos(tmp_path, "N55_S2", "abc")


def test_registre_compte_sans_doublon(tmp_path):
    reg = tmp_path / "registre.csv"
    v = [(donchian.nom_variante(p), p) for p in donchian.GRILLE]
    assert rc.enregistrer_variantes("001", v, "abc", reg) == 6
    assert rc.enregistrer_variantes("001", v, "abc", reg) == 6   # relancer n'ajoute pas de variante
    assert rc.enregistrer_variantes("002", v[:2], "abc", reg) == 8


# ---------------- métriques, critères, plateau, benchmark ----------------

def m_ok(**k):
    base = {"trades": 200, "esperance_R": 0.2, "profit_factor": 1.5, "marches_positifs": 9, "marches_eligibles": 12,
            "contribution_max": 0.2,
            "marche_contribution_max": "A", "drawdown_realise_pct": 0.1, "pire_serie_pertes": 8,
            "part_max_une_annee": 0.2}
    return {**base, **k}


def test_criteres_ok_aucun_rejet():
    assert rc.criteres(m_ok(), "entrainement") == {"rejet": [], "revue": []}


@pytest.mark.parametrize("modif,mot", [
    ({"trades": 100}, "trades"), ({"esperance_R": -0.01}, "espérance"), ({"profit_factor": 1.05}, "profit factor"),
    ({"marches_positifs": 6}, "marchés positifs"), ({"contribution_max": 0.45}, "du gain"),
    ({"drawdown_realise_pct": 0.3}, "drawdown"), ({"pire_serie_pertes": 25}, "série"),
    ({"part_annees_positives_tv": 0.5}, "années positives"),
])
def test_chaque_critere_de_rejet(modif, mot):
    assert any(mot in x for x in rc.criteres(m_ok(**modif), "entrainement")["rejet"])


def test_stress_et_benchmark_peuvent_rejeter():
    r = rc.criteres(m_ok(), "validation", stress={"trades": 100, "esperance_R": -0.01})
    assert any("stress" in x for x in r["rejet"])
    r = rc.criteres(m_ok(esperance_R=0.05), "validation", bench=np.linspace(0, 0.1, 200))
    assert any("centile" in x for x in r["rejet"])


def test_marge_de_revue():
    r = rc.criteres(m_ok(profit_factor=1.15, marches_positifs=7, part_max_une_annee=0.6), "validation")
    assert r["rejet"] == [] and len(r["revue"]) == 3


def test_plateau():
    nom = donchian.nom_variante
    esp = {nom(p): 0.1 for p in donchian.GRILLE}
    esp["N55_S3"] = -0.1
    pl = rc.plateau(esp, donchian.GRILLE, nom)
    assert not pl["N55_S2"] and not pl["N20_S3"] and not pl["N100_S3"]  # voisins de N55_S3
    assert pl["N20_S2"] and pl["N100_S2"]


def test_metriques_sur_une_periode(univers):
    marches, infos, hyp = univers
    ev = rc.evaluer(marches, donchian.variante(donchian.GRILLE[0]), infos, hyp, "validation")
    m = rc.metriques(ev, list(marches))
    assert m["trades"] == len(ev["trades"]) > 0
    assert set(m["annees"]) <= {2020, 2021, 2022}
    assert sum(m["trades_par_marche"].values()) == m["trades"]
    assert m["total_R_execution"] < m["total_R_brut"]


def test_benchmark_reproductible_et_meme_nombre_de_signaux(univers):
    marches, infos, hyp = univers
    f = donchian.variante(donchian.GRILLE[2])
    b1 = rc.benchmark_aleatoire(marches, f, infos, hyp, "validation", {"A": 20, "B": 20}, n_tirages=3, seed=1)
    b2 = rc.benchmark_aleatoire(marches, f, infos, hyp, "validation", {"A": 20, "B": 20}, n_tirages=3, seed=1)
    np.testing.assert_array_equal(b1, b2)
    assert np.isfinite(b1).all()


# ---------------- protocole v0.4.1 : éligibilité des marchés ----------------

def ev_synthetique(trades_par_marche: dict, r_par_marche: dict):
    """Évaluation minimale : n trades par marché, tous au même R."""
    lignes = [{"symbol": s, "entry_time": pd.Timestamp("2020-01-06") + pd.Timedelta(days=k), "R": r_par_marche[s],
               "R_execution": r_par_marche[s], "R_net": r_par_marche[s], "statut_swap": "OK", "cout_spread_R": 0.0,
               "cout_slippage_R": 0.0, "traverse_gap": False}
              for s, n in trades_par_marche.items() for k in range(n)]
    res = {"execution": {"resultat_monetaire": 0.0, "drawdown_realise_pct": 0.0},
           "exposition_journaliere": {"risque_ouvert_max_pct": 0.0, "positions_max": 0}}
    return {"trades": pd.DataFrame(lignes), "evenements": pd.DataFrame(), "analyse": {"resume": res}}


@pytest.mark.parametrize("n,statut", [(4, rc.INSUFFICIENT_SAMPLE), (5, "ELIGIBLE"), (14, "ELIGIBLE"),
                                      (15, "BIEN_ECHANTILLONNE")])
def test_seuils_d_echantillon_par_marche(n, statut):
    m = rc.metriques(ev_synthetique({"A": n}, {"A": 1.0}), ["A"])
    assert m["statut_echantillon_par_marche"]["A"] == statut
    assert m["marches_eligibles"] == (0 if n < 5 else 1)
    assert m["marches_bien_echantillonnes"] == (1 if n >= 15 else 0)


def test_marche_insuffisant_ni_positif_ni_negatif_et_hors_denominateur():
    m = rc.metriques(ev_synthetique({"A": 4, "B": 4, "C": 6, "D": 6}, {"A": 2.0, "B": -2.0, "C": 1.0, "D": -1.0}),
                     ["A", "B", "C", "D", "E"])
    assert m["marches_eligibles"] == 2 and m["marches_positifs"] == 1 and m["marches_negatifs"] == 1
    assert m["marches_insufficient_sample"] == 3  # A, B (4 trades) et E (aucun trade)
    assert m["statut_echantillon_par_marche"]["E"] == rc.INSUFFICIENT_SAMPLE


@pytest.mark.parametrize("pos,elig,rejete", [
    (4, 4, True),    # moins de 5 positifs, même à 100 %
    (5, 12, True),   # 5 positifs mais minorité (5/12)
    (6, 12, True),   # exactement la moitié : pas une majorité
    (7, 12, False),  # 7/12 : comme l'ancienne règle
    (5, 8, False),   # 5/8 : majorité parmi les éligibles
    (5, 9, False),
    (5, 10, True),   # 5/10 = moitié
])
def test_critere_marches_positifs_sur_eligibles_seulement(pos, elig, rejete):
    r = rc.criteres(m_ok(marches_positifs=pos, marches_eligibles=elig), "validation")
    assert any("marchés positifs" in x for x in r["rejet"]) == rejete


def test_meme_regle_en_entrainement_et_validation():
    for p in ("entrainement", "validation"):
        assert any("pas une majorité" in x for x in rc.criteres(m_ok(marches_positifs=5, marches_eligibles=12), p)["rejet"])


def test_quinze_trades_n_est_jamais_un_critere_de_rejet():
    m = rc.metriques(ev_synthetique({s: 6 for s in "ABCDEFGH"}, {s: 1.0 for s in "ABCDEFGH"}), list("ABCDEFGH"))
    assert m["marches_bien_echantillonnes"] == 0
    r = rc.criteres({**m, "trades": 200, "drawdown_realise_pct": 0.0, "part_max_une_annee": 0.1}, "validation")
    assert not any("marchés positifs" in x for x in r["rejet"])


EXP001 = rc.EXPERIMENTS / "001-donchian-baseline"


@pytest.mark.skipif(not (EXP001 / "decision.json").exists(), reason="expérience 001 absente")
def test_experience_001_reste_historique():
    d = json.loads((EXP001 / "decision.json").read_text("utf-8"))
    assert [v["statut"] for v in d["variantes"].values()] == ["REJECT"] * 6 and d["oos_ouvert_pour"] is None
    e = json.loads((EXP001 / "experience.json").read_text("utf-8"))
    assert e["criteres"]["trades_min_marche"] == 15 and e["criteres"]["marches_positifs_min"] == 7  # règles d'origine
    assert not (EXP001 / "oos_ouvert.json").exists()  # OOS toujours verrouillé et jamais lu
    reg = pd.read_csv(rc.REGISTRE, sep=";", dtype=str)
    reg001 = reg[reg["experience"] == "001"]  # les expériences suivantes s'ajoutent, 001 ne change pas
    assert reg001["variante"].tolist() == ["N20_S2", "N20_S3", "N55_S2", "N55_S3", "N100_S2", "N100_S3"]
    assert set(reg001["commit"].str[:7]) == {"94be67c"}


def test_script_001_refuse_de_rejuger(tmp_path, monkeypatch):
    import scripts.experience_001 as x
    monkeypatch.setattr(x, "DOSSIER", tmp_path)
    (tmp_path / "decision.json").write_text("{}")
    with pytest.raises(SystemExit, match="déjà jugée"):
        x.main()
