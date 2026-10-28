import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import portefeuille as pf
from src.couts import Hypotheses
from src.engine import Params, backtest, verifier_sans_lookahead
from src.indicateurs import atr
from strategies import reversion
from tests.outils import bougies

PROPOSITION = Path(__file__).resolve().parent.parent / "docs" / "proposition-experience-003.md"
INFO = {"symbol": "X", "swap_long": -1.0, "swap_short": -1.0, "swap_mode": 1, "unite": "points",
        "triple_swap_jour": "mercredi", "point": 0.01}


def serie(closes):
    """Bougies de 1 point d'amplitude autour de chaque clôture : sur des clôtures plates, l'ATR(20) vaut 1."""
    return bougies([(c, c + 0.5, c - 0.5, c) for c in closes])


def plat_puis(mouvement, n_plat=30, apres=10):
    """n_plat clôtures à 100, une séance qui bouge de `mouvement`, puis `apres` séances plates au nouveau niveau."""
    return serie([100.0] * n_plat + [100.0 + mouvement] * (1 + apres))


def lancer(df, p):
    s = reversion.signaux(df, p["z"], p["H"])
    return s, backtest(df, s["signal"], s["stop_dist"], Params(None), retournement=s["retournement"],
                       duree_max=s["duree_max"])[0]


# ---------------- grille ----------------

def test_grille_identique_a_la_proposition():
    assert reversion.GRILLE == [{"z": z, "H": H} for z in (1.5, 2.0, 2.5) for H in (3, 5)]
    texte = PROPOSITION.read_text(encoding="utf-8")
    assert re.search(r"z \(seuil du mouvement, en ATR\) \| 1,5 ; 2,0 ; 2,5", texte)
    assert re.search(r"H \(séances de détention\) \| 3 ; 5", texte)
    assert [reversion.nom_variante(p) for p in reversion.GRILLE] == \
        ["Z1p5_H3", "Z1p5_H5", "Z2_H3", "Z2_H5", "Z2p5_H3", "Z2p5_H5"]


@pytest.mark.parametrize("p", [{"z": 1.0, "H": 3}, {"z": 2.0, "H": 4}, {"z": 2.0, "H": 3, "x": 1}, {"z": 2}])
def test_variante_hors_grille_refusee(p):
    with pytest.raises(ValueError, match="hors grille"):
        reversion.variante(p)


# ---------------- signal ----------------

def test_calcul_du_mouvement_avec_l_atr_de_la_veille():
    df = plat_puis(-2.0)
    m = reversion.mouvement(df)
    a = atr(df, 20)
    assert m[30] == pytest.approx((df["close"][30] - df["close"][29]) / a[29])
    assert a[29] == pytest.approx(1.0) and m[30] == pytest.approx(-2.0)


def test_la_seance_extreme_ne_gonfle_pas_sa_propre_mesure():
    df = plat_puis(-2.0)
    df2 = df.copy()
    df2.loc[30, ["high", "low"]] = [150.0, 50.0]  # amplitude énorme le jour même
    assert reversion.mouvement(df2)[30] == pytest.approx(reversion.mouvement(df)[30])


@pytest.mark.parametrize("mouvement,z,attendu", [
    (-2.0, 1.5, 1), (-2.0, 2.0, 1), (-2.0, 2.5, 0),   # forte baisse -> long ; seuil exact inclus
    (+2.0, 1.5, -1), (+2.0, 2.0, -1), (+2.0, 2.5, 0),  # forte hausse -> short
    (-1.99, 2.0, 0), (+1.99, 2.0, 0),                  # juste sous le seuil
    (0.0, 1.5, 0),                                     # rendement nul
])
def test_sens_et_seuil(mouvement, z, attendu):
    s = reversion.signaux(plat_puis(mouvement), z, 3)
    assert s["signal"][30] == attendu
    assert (s["signal"].drop(index=30) == 0).all()


def test_chauffe_et_atr_nul():
    s = reversion.signaux(plat_puis(-5.0, n_plat=15), 1.5, 3)
    assert (s["signal"] == 0).all()  # séance extrême en 15 < 21 : ignorée
    s = reversion.signaux(plat_puis(-5.0, n_plat=21), 1.5, 3)
    assert s["signal"][21] == 1
    figees = bougies([(100.0, 100.0, 100.0, 100.0)] * 30 + [(100.0, 100.0, 90.0, 90.0)])
    assert (reversion.signaux(figees, 1.5, 3)["signal"] == 0).all()  # ATR de la veille nul : pas mesurable


@pytest.mark.parametrize("p", reversion.GRILLE)
def test_sans_lookahead(p):
    rng = np.random.default_rng(6)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, 600)))
    o = np.r_[100, c[:-1]]
    df = bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)))
    verifier_sans_lookahead(reversion.variante(p), df)


# ---------------- exécution (moteur) ----------------

@pytest.mark.parametrize("H", [3, 5])
def test_entree_ouverture_suivante_stop_fixe_et_sortie_au_temps(H):
    df = plat_puis(-2.0, apres=10)
    s, t = lancer(df, {"z": 2.0, "H": H})
    e = t.iloc[0]
    a30 = atr(df, 20)[30]
    assert e["direction"] == "long" and e["entry_time"] == df["time"][31] and e["entry"] == df["open"][31]
    assert e["dist"] == pytest.approx(2 * a30) and e["stop"] == pytest.approx(df["open"][31] - 2 * a30)
    assert e["raison"] == "duree" and e["exit_time"] == df["time"][31 + H] and e["exit"] == df["open"][31 + H]
    assert e["target"] is None or pd.isna(e["target"])
    assert len(t) == 1  # pas de réentrée sans nouveau signal


def test_short_symetrique():
    df = plat_puis(+2.0, apres=10)
    _, t = lancer(df, {"z": 2.0, "H": 3})
    e = t.iloc[0]
    assert e["direction"] == "short" and e["stop"] == pytest.approx(df["open"][31] + 2 * atr(df, 20)[30])
    assert e["raison"] == "duree"


def test_pas_de_retournement_sur_un_signal_oppose():
    closes = [100.0] * 30 + [98.0, 98.0, 100.5, 100.5, 100.5, 100.5, 100.5, 100.5, 100.5, 100.5]
    df = serie(closes)
    s, t = lancer(df, {"z": 1.5, "H": 5})
    assert s["signal"][30] == 1 and s["signal"][32] == -1  # signal short pendant la position longue
    assert t["direction"].tolist() == ["long"] and not t["retournement"].any()
    assert t["raison"].iloc[0] == "duree"


def test_stop_touche_avant_H():
    df = plat_puis(-2.0, apres=10)
    df.loc[32, "low"] = 50.0  # mèche qui touche le stop pendant la détention
    _, t = lancer(df, {"z": 2.0, "H": 5})
    assert t["raison"].tolist() == ["stop"]


# ---------------- intégration portefeuille ----------------

def test_portefeuille_transmet_duree_stop_et_pas_de_retournement(monkeypatch):
    vus = []
    vrai = pf.backtest

    def espion(df, signal, stop, params, sortie, sl, ss, retournement, duree_max):
        vus.append({"stop": stop, "retournement": retournement, "duree_max": duree_max, "df": df})
        return vrai(df, signal, stop, params, sortie, sl, ss, retournement=retournement, duree_max=duree_max)
    monkeypatch.setattr(pf, "backtest", espion)
    df = plat_puis(-2.0)
    for p in reversion.GRILLE:
        pf.executer({"A": df}, reversion.variante(p), Params(None), {"A": {**INFO, "symbol": "A"}},
                    Hypotheses("fixe", 10, 0))
        v = vus[-1]
        assert v["duree_max"] == p["H"] and v["retournement"] is False
        pd.testing.assert_series_equal(v["stop"], atr(df, 20) * 2.0)


def test_marches_independants_et_couts_appliques():
    a = plat_puis(-2.0)
    b = serie([100.0] * 41)  # aucun mouvement extrême
    infos = {k: {**INFO, "symbol": k} for k in "AB"}
    h = Hypotheses("fixe", 20, 5)
    f = reversion.variante({"z": 2.0, "H": 3})
    ensemble, _ = pf.executer({"A": a, "B": b}, f, Params(None), infos, h)
    seul, _ = pf.executer({"A": a}, f, Params(None), infos, h)
    assert set(ensemble["symbol"]) == {"A"}
    pd.testing.assert_frame_equal(ensemble.reset_index(drop=True), seul.reset_index(drop=True))
    r = ensemble.iloc[0]
    assert r["raison"] == "duree" and r["R_execution"] < r["R"]  # spread + slippage appliqués à la sortie au temps
