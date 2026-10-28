import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.couts import Hypotheses
from src.engine import Params, backtest, verifier_sans_lookahead
from src.portefeuille import executer
from strategies import momentum
from tests.outils import bougies

HYPOTHESE = Path(__file__).resolve().parent.parent / "experiments" / "002-momentum-serie-temporelle" / "hypothese.md"


def serie_prix(closes):
    """Bougies plates autour de chaque clôture (high/low à +-0,5) : contrôle exact de r."""
    return bougies([(c, c + 0.5, c - 0.5, c) for c in closes])


# ---------------- grille ----------------

def test_grille_identique_a_l_hypothese():
    assert momentum.GRILLE == [{"L": L, "k": k} for L in (60, 125, 250) for k in (3.0, 5.0)]
    assert len(momentum.GRILLE) == 6
    texte = HYPOTHESE.read_text(encoding="utf-8")
    assert re.search(r"L \(bougies de rendement\) \| 60, 125, 250", texte)
    assert re.search(r"k \(stop en ATR\) \| 3, 5", texte)
    assert "6 variantes" in texte


def test_variante_hors_grille_refusee():
    with pytest.raises(ValueError, match="hors grille"):
        momentum.variante({"L": 100, "k": 3.0})
    assert [momentum.nom_variante(p) for p in momentum.GRILLE] == \
        ["L60_K3", "L60_K5", "L125_K3", "L125_K5", "L250_K3", "L250_K5"]


# ---------------- signal ----------------

def test_entree_uniquement_au_changement_de_signe():
    L = 3
    closes = [100] * 25 + [101, 102, 103, 104, 105, 104, 103, 102, 101, 100, 99]
    s = momentum.signaux(serie_prix(closes), L, 3.0)
    r = pd.Series(closes) / pd.Series(closes).shift(L) - 1
    longs = s["signal"][s["signal"] == 1].index.tolist()
    shorts = s["signal"][s["signal"] == -1].index.tolist()
    assert longs == [25]                     # r passe de 0 à > 0 : un seul signal, pas à chaque bougie positive
    assert (r[26:30] > 0).all() and (s["signal"][26:30] == 0).all()
    assert shorts == [r[r < 0].index[0]]     # premier r < 0 après r >= 0
    assert s["sortie_long"][shorts[0]] and not s["sortie_long"][longs[0]]


def test_r_nul_n_entre_pas_mais_fait_sortir():
    s = momentum.signaux(serie_prix([100] * 30), 3, 3.0)
    assert (s["signal"] == 0).all()
    assert s["sortie_long"][29] and s["sortie_short"][29]  # r = 0 : un long ET un short sortiraient


def test_chauffe_L_plus_20():
    L = 5
    closes = [100 - 0.1 * i for i in range(L + 20)] + [200] * 5  # changement de signe pendant la chauffe : ignoré
    s = momentum.signaux(serie_prix(closes), L, 3.0)
    assert (s["signal"][:L + 20] == 0).all() and s["signal"][L + 20] == 1


def test_stop_k_fois_atr20():
    df = serie_prix(list(np.linspace(100, 130, 300)))
    from src.indicateurs import atr
    for k in (3.0, 5.0):
        pd.testing.assert_series_equal(momentum.signaux(df, 60, k)["stop_dist"], atr(df, 20) * k)


@pytest.mark.parametrize("p", momentum.GRILLE)
def test_sans_lookahead(p):
    rng = np.random.default_rng(4)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 700)))
    o = np.r_[100, c[:-1]]
    df = bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)))
    verifier_sans_lookahead(momentum.variante(p), df, coupures=(0.5, 0.7, 0.9))


# ---------------- conventions du moteur et du portefeuille ----------------

def test_cles_attendues_par_le_moteur_et_le_portefeuille():
    s = momentum.signaux(serie_prix([100] * 40), 3, 3.0)
    assert set(s) == {"signal", "stop_dist", "sortie_long", "sortie_short", "retournement"}
    assert s["retournement"] is True  # activé explicitement par la stratégie (hypothèse 002)
    assert all(len(v) == 40 for k, v in s.items() if k != "retournement")
    assert s["sortie_long"].dtype == bool and s["sortie_short"].dtype == bool


def test_stop_fixe_a_l_entree_et_pas_de_reentree_apres_stop():
    L = 3
    closes = [100] * 25 + [101, 102, 103, 104, 105, 106, 107, 108, 109]
    df = serie_prix(closes)
    df.loc[29, "low"] = 50  # mèche qui touche le stop ; la clôture (105) garde r > 0
    s = momentum.signaux(df, L, 3.0)
    t, _ = backtest(df, s["signal"], s["stop_dist"], Params(None), None, s["sortie_long"], s["sortie_short"])
    assert t["raison"].iloc[0] == "stop" and t["entry"].iloc[0] == 102     # entrée à l'ouverture après le signal
    assert t["stop"].iloc[0] == pytest.approx(102 - s["stop_dist"][25])     # stop de la bougie du signal, inchangé
    assert t["exit"].iloc[0] == pytest.approx(t["stop"].iloc[0])
    # r reste > 0 après le stop : aucun nouveau changement de signe, donc aucune réentrée
    assert len(t) == 1


def test_sortie_au_changement_de_signe_a_l_ouverture_suivante():
    L = 3
    closes = [100] * 25 + [101, 102, 103, 102.5, 102, 101.5, 101, 100.5]
    df = serie_prix(closes)
    s = momentum.signaux(df, L, 5.0)
    t, _ = backtest(df, s["signal"], s["stop_dist"], Params(None), None, s["sortie_long"], s["sortie_short"])
    i_sortie = s["sortie_long"][26:].idxmax()
    assert t["raison"].iloc[0] == "signal" and t["exit_time"].iloc[0] == df["time"][i_sortie + 1]


def lancer(df, s, retournement):
    return backtest(df, s["signal"], s["stop_dist"], Params(None), None, s["sortie_long"], s["sortie_short"],
                    retournement=retournement)[0]


def test_retournement_long_vers_short_avec_la_strategie():
    L = 3
    closes = [100] * 25 + [101, 102, 103, 104, 103, 102, 101, 100, 99, 98, 97]
    df = serie_prix(closes)
    s = momentum.signaux(df, L, 5.0)
    assert (s["signal"] == -1).sum() == 1
    # sans retournement (comportement par défaut du moteur) : le short du changement de signe est perdu
    assert lancer(df, s, False)["direction"].tolist() == ["long"]
    # avec le retournement demandé par la stratégie : long puis short, à la même ouverture
    t = lancer(df, s, s["retournement"])
    assert t["direction"].tolist() == ["long", "short"]
    assert t["exit_time"].iloc[0] == t["entry_time"].iloc[1] and t["exit"].iloc[0] == t["entry"].iloc[1]
    assert t["retournement"].tolist() == [False, True]


def test_portefeuille_execute_la_strategie():
    rng = np.random.default_rng(5)
    marches = {}
    for sym in "AB":
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 500)))
        o = np.r_[100, c[:-1]]
        df = bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)))
        df["spread"] = 10
        marches[sym] = df
    infos = {s: {"symbol": s, "swap_long": -1.0, "swap_short": -1.0, "swap_mode": 1, "unite": "points",
                 "triple_swap_jour": "mercredi", "point": 0.01} for s in marches}
    t, _ = executer(marches, momentum.variante(momentum.GRILLE[0]), Params(None), infos, Hypotheses("fixe", 10, 0))
    assert len(t) > 0 and set(t["symbol"]) == {"A", "B"} and t["target"].isna().all()
