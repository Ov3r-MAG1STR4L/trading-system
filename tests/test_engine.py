import numpy as np
import pandas as pd
import pytest

from src.data import STATUT_GAP
from src.engine import Params, backtest, verifier_sans_lookahead
from tests.outils import PLAT, bougies, serie

def run(ohlc, signal_idx=1, direction=1, target_r=2.0, gaps_avant=(), sortie_idx=None):
    df = bougies(ohlc, gaps_avant=gaps_avant)
    n = len(df)
    sortie = None if sortie_idx is None else serie(n, **{str(sortie_idx): 1}).astype(bool)
    return backtest(df, serie(n, **{str(signal_idx): direction}), pd.Series(5.0, index=range(n)),
                    Params(target_r=target_r), sortie)


# ---------------- entrée à l'ouverture suivante ----------------

def test_entree_a_l_ouverture_suivante():
    df = bougies([PLAT, PLAT, (100, 101, 99, 100), PLAT])
    trades, _ = run([PLAT, PLAT, (100, 101, 99, 100), PLAT])
    assert trades["entry_time"].iloc[0] == df["time"][2]  # signal sur la bougie 1 -> entrée bougie 2
    assert trades["entry"].iloc[0] == 100


def test_entree_au_prix_d_ouverture_meme_si_different_de_la_cloture():
    trades, _ = run([PLAT, (100, 101, 99, 100), (102, 103, 101, 102), PLAT])
    assert trades["entry"].iloc[0] == 102 and trades["stop"].iloc[0] == 97


def test_signal_sur_la_derniere_bougie_ne_trade_pas():
    trades, _ = run([PLAT, PLAT, PLAT], signal_idx=2)
    assert trades.empty


# ---------------- stop / objectif ----------------

def test_stop_touche_vaut_moins_un_R():
    trades, _ = run([PLAT, PLAT, PLAT, (99, 100, 94, 96)])
    assert trades["raison"].iloc[0] == "stop" and trades["R"].iloc[0] == pytest.approx(-1)


def test_objectif_touche_vaut_plus_deux_R():
    trades, _ = run([PLAT, PLAT, PLAT, (101, 111, 100, 108)])
    assert trades["raison"].iloc[0] == "objectif" and trades["R"].iloc[0] == pytest.approx(2)


def test_aucun_niveau_touche_sortie_fin_de_donnees_a_la_cloture():
    trades, _ = run([PLAT, PLAT, PLAT, (100, 104, 97, 103)])
    t = trades.iloc[0]
    assert t["raison"] == "fin_donnees" and t["exit"] == 103 and t["R"] == pytest.approx(0.6)


def test_stop_et_objectif_dans_la_meme_bougie_compte_le_stop():
    trades, _ = run([PLAT, PLAT, PLAT, (100, 112, 94, 105)])
    assert trades["raison"].iloc[0] == "stop" and trades["R"].iloc[0] == pytest.approx(-1)


def test_stop_et_objectif_sur_la_bougie_d_entree_compte_le_stop():
    trades, _ = run([PLAT, PLAT, (100, 112, 94, 105)])
    assert trades["raison"].iloc[0] == "stop"


def test_short_stop_et_objectif():
    t, _ = run([PLAT, PLAT, PLAT, (100, 106, 99, 104)], direction=-1)
    assert t["raison"].iloc[0] == "stop" and t["R"].iloc[0] == pytest.approx(-1)
    t, _ = run([PLAT, PLAT, PLAT, (99, 100, 89, 92)], direction=-1)
    assert t["raison"].iloc[0] == "objectif" and t["R"].iloc[0] == pytest.approx(2)


def test_ouverture_sous_le_stop_sortie_au_prix_d_ouverture():
    trades, _ = run([PLAT, PLAT, PLAT, (90, 92, 88, 91)])
    t = trades.iloc[0]
    assert t["raison"] == "stop_gap" and t["exit"] == 90 and t["R"] == pytest.approx(-2)


def test_sortie_sur_signal_a_l_ouverture_suivante():
    trades, _ = run([PLAT, PLAT, PLAT, (100, 102, 99, 101), (103, 104, 102, 103)], sortie_idx=3)
    t = trades.iloc[0]
    assert t["raison"] == "signal" and t["exit"] == 103  # ouverture de la bougie 4, pas la clôture de 3


def test_une_seule_position_a_la_fois():
    df = bougies([PLAT] * 6)
    trades, _ = backtest(df, pd.Series(1.0, index=range(6)), pd.Series(5.0, index=range(6)), Params(2.0))
    assert len(trades) == 1


def test_stop_dist_invalide_pas_d_entree():
    df = bougies([PLAT] * 4)
    for d in (0.0, -1.0, np.nan):
        trades, _ = backtest(df, serie(4, **{"1": 1}), pd.Series(d, index=range(4)))
        assert trades.empty


def test_longueurs_incoherentes_refusees():
    df = bougies([PLAT] * 4)
    with pytest.raises(ValueError):
        backtest(df, serie(3), pd.Series(5.0, index=range(4)))


def test_R_du_moteur_identique_a_risque_resultat_r():
    from src.risque import resultat_r
    df = marche_aleatoire()
    s = strategie_honnete(df)
    trades, _ = backtest(df, s["signal"], s["stop_dist"], Params(2.0))
    assert len(trades) > 10
    for t in trades.itertuples():
        assert t.R == pytest.approx(resultat_r(t.entry, t.exit, t.stop))


# ---------------- look-ahead ----------------

def strategie_honnete(df):
    m = df["close"].rolling(3).mean()
    return {"signal": np.sign(df["close"] - m).fillna(0), "stop_dist": (df["high"] - df["low"]).rolling(3).mean()}


def strategie_tricheuse(df):
    return np.sign(df["close"].shift(-1) - df["close"]).fillna(0)  # regarde la clôture de demain


def marche_aleatoire(n=200, seed=1):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[100, c[:-1]]
    return bougies(list(zip(o, np.maximum(o, c) * 1.004, np.minimum(o, c) * 0.996, c)))


def test_modifier_une_bougie_future_ne_change_pas_un_signal_passe():
    verifier_sans_lookahead(strategie_honnete, marche_aleatoire())


def test_le_detecteur_attrape_une_strategie_qui_regarde_le_futur():
    with pytest.raises(AssertionError):
        verifier_sans_lookahead(strategie_tricheuse, marche_aleatoire())


def test_moteur_trades_passes_inchanges_si_le_futur_change():
    df = marche_aleatoire()
    s = strategie_honnete(df)
    trades, _ = backtest(df, s["signal"], s["stop_dist"], Params(2.0))
    coupure = df["time"][120]
    passes = trades[trades["exit_time"] <= coupure]
    assert len(passes) > 3
    futur = df.copy()
    futur.loc[121:, ["open", "high", "low", "close"]] *= 1.3
    # signaux recalculés sur les données modifiées : ceux d'avant 120 sont identiques
    s2 = strategie_honnete(futur)
    trades2, _ = backtest(futur, s2["signal"], s2["stop_dist"], Params(2.0))
    pd.testing.assert_frame_equal(passes, trades2[trades2["exit_time"] <= coupure])


# ---------------- DATA_GAP / NON_TRADABLE ----------------
# bougies 0..2 avant le trou, bougie 3 = première bougie réelle après le trou

def test_gap_pas_de_nouvelle_entree_a_la_reprise():
    """Cas « période tradable » : un signal d'avant le trou ne déclenche rien à la reprise."""
    trades, ev = run([PLAT, PLAT, PLAT, PLAT, PLAT], signal_idx=2, gaps_avant=(3,))
    assert trades.empty
    assert ev["statut"].tolist() == [STATUT_GAP] and not ev["position_ouverte"].iloc[0]
    assert ev["entree_refusee"].iloc[0]  # le refus est journalisé


def test_gap_position_conservee_et_marquee():
    trades, ev = run([PLAT, PLAT, PLAT, (101, 103, 100, 102), PLAT], signal_idx=1, gaps_avant=(3,))
    t = trades.iloc[0]
    assert t["raison"] == "fin_donnees"  # pas fermée automatiquement à la reprise
    assert t["traverse_gap"] and ev["position_ouverte"].iloc[0] and not ev["entree_refusee"].iloc[0]


def test_gap_pas_un_prix_inchange_ni_un_rendement_nul():
    """À la reprise, le saut de prix réel est encaissé : le trade ne vaut pas 0 R."""
    trades, _ = run([PLAT, PLAT, PLAT, (104, 105, 103, 104)], signal_idx=1, target_r=None, gaps_avant=(3,))
    t = trades.iloc[0]
    assert t["exit"] == 104 and t["R"] == pytest.approx(0.8)  # (104 - 100) / 5


def test_gap_ouverture_sous_le_stop_sortie_au_premier_prix_reel():
    trades, _ = run([PLAT, PLAT, PLAT, (90, 92, 88, 91)], signal_idx=1, gaps_avant=(3,))
    t = trades.iloc[0]
    assert t["raison"] == "stop_gap" and t["exit"] == 90 and t["traverse_gap"]
    assert t["exit_time"] == bougies([PLAT] * 4)["time"][3]


def test_gap_aucune_bougie_creee_ni_sortie_pendant_le_trou():
    df = bougies([PLAT, PLAT, PLAT, (90, 92, 88, 91)], gaps_avant=(3,))
    avant = df.copy()
    trades, _ = backtest(df, serie(4, **{"1": 1}), pd.Series(5.0, index=range(4)), Params(2.0))
    pd.testing.assert_frame_equal(df, avant)  # le moteur ne touche pas aux données
    assert set(trades["exit_time"]) <= set(df["time"])  # toute sortie a lieu sur une bougie réelle


# ---------------- audit v0.3 : cas limites ----------------

def test_bug_refus_journalise_si_la_position_sort_a_la_reprise():
    """Position stoppée sur la bougie de reprise + signal d'avant le trou : le refus doit être compté."""
    df = bougies([PLAT, PLAT, PLAT, (90, 92, 88, 91), PLAT], gaps_avant=(3,))
    sig = serie(5, **{"1": 1, "2": 1})  # entrée en 2 ; nouveau signal en 2, juste avant le trou
    trades, ev = backtest(df, sig, pd.Series(5.0, index=range(5)), Params(2.0))
    assert trades["raison"].tolist() == ["stop_gap"] and len(trades) == 1
    assert ev["position_ouverte"].iloc[0] and ev["entree_refusee"].iloc[0]


def miroir(df):
    """Prix p -> 400 - p : un long sur df doit se comporter exactement comme un short sur miroir(df)."""
    m = df.copy()
    m["open"], m["close"] = 400 - df["open"], 400 - df["close"]
    m["high"], m["low"] = 400 - df["low"], 400 - df["high"]
    return m


def test_symetrie_long_short_sur_prix_miroir():
    df = marche_aleatoire(300, seed=7)
    df.loc[[50, 120, 200], "gap_avant"] = True
    s = strategie_honnete(df)
    s["signal"] = s["signal"].diff().fillna(0).clip(-1, 1)  # croisements : plusieurs trades, long et short
    sortie = s["signal"] != 0  # sortir à chaque nouveau croisement : beaucoup de trades
    for target in (None, 2.0):
        tl, el = backtest(df, s["signal"], s["stop_dist"], Params(target), sortie)
        ts, es = backtest(miroir(df), -s["signal"], s["stop_dist"], Params(target), sortie)
        assert len(tl) == len(ts) > 10
        np.testing.assert_allclose(tl["R"], ts["R"], atol=1e-9)
        assert tl["raison"].tolist() == ts["raison"].tolist()
        assert tl["traverse_gap"].tolist() == ts["traverse_gap"].tolist()
        pd.testing.assert_frame_equal(el, es)


def test_ouverture_au_dela_de_l_objectif_sortie_a_l_ouverture():
    t, _ = run([PLAT, PLAT, PLAT, (112, 113, 111, 112)])
    assert t["raison"].iloc[0] == "objectif" and t["exit"].iloc[0] == 112 and t["R"].iloc[0] == pytest.approx(2.4)
    t, _ = run([PLAT, PLAT, PLAT, (88, 89, 87, 88)], direction=-1)
    assert t["raison"].iloc[0] == "objectif" and t["R"].iloc[0] == pytest.approx(2.4)


def test_short_stop_gap_et_fin_de_donnees():
    t, _ = run([PLAT, PLAT, PLAT, (110, 112, 109, 111)], direction=-1)
    assert t["raison"].iloc[0] == "stop_gap" and t["exit"].iloc[0] == 110 and t["R"].iloc[0] == pytest.approx(-2)
    t, _ = run([PLAT, PLAT, PLAT, (100, 103, 97, 98)], direction=-1)
    assert t["raison"].iloc[0] == "fin_donnees" and t["R"].iloc[0] == pytest.approx(0.4)


def test_gap_puis_objectif_a_la_reprise():
    t, _ = run([PLAT, PLAT, PLAT, (113, 114, 112, 113)], gaps_avant=(3,))
    assert t["raison"].iloc[0] == "objectif" and t["exit"].iloc[0] == 113 and t["traverse_gap"].iloc[0]


def test_gap_reprise_touche_stop_et_objectif_compte_le_stop():
    t, _ = run([PLAT, PLAT, PLAT, (100, 112, 94, 100)], gaps_avant=(3,))
    assert t["raison"].iloc[0] == "stop" and t["R"].iloc[0] == pytest.approx(-1) and t["traverse_gap"].iloc[0]


def test_gap_sortie_sur_signal_decidee_avant_le_trou_executee_au_premier_prix_reel():
    t, ev = run([PLAT, PLAT, PLAT, (103, 104, 102, 103), PLAT], sortie_idx=2, gaps_avant=(3,))
    assert t["raison"].iloc[0] == "signal" and t["exit"].iloc[0] == 103 and t["traverse_gap"].iloc[0]
    assert ev["position_ouverte"].iloc[0]


def test_gap_position_continue_puis_stop_plus_tard():
    t, _ = run([PLAT, PLAT, PLAT, PLAT, (99, 100, 94, 96)], gaps_avant=(3,))
    assert t["raison"].iloc[0] == "stop" and t["exit_time"].iloc[0] == bougies([PLAT] * 5)["time"][4]
    assert t["traverse_gap"].iloc[0]


def test_aucune_entree_sur_la_bougie_de_reprise_meme_signal_valide():
    df = bougies([PLAT] * 6, gaps_avant=(3,))
    trades, _ = backtest(df, pd.Series(1.0, index=range(6)), pd.Series(5.0, index=range(6)), Params(None))
    assert df["time"][3] not in set(trades["entry_time"])


def test_sortie_par_sens_n_affecte_que_le_sens_concerne():
    ohlc = [PLAT, PLAT, PLAT, (100, 102, 99, 101), (103, 104, 102, 103), PLAT]
    df = bougies(ohlc)
    sl = serie(6, **{"3": 1}).astype(bool)
    vide = serie(6).astype(bool)
    stop = pd.Series(5.0, index=range(6))
    t, _ = backtest(df, serie(6, **{"1": 1}), stop, Params(None), None, sl, vide)
    assert t["raison"].iloc[0] == "signal" and t["exit"].iloc[0] == 103   # long : sortie_long à l'ouverture suivante
    t, _ = backtest(df, serie(6, **{"1": -1}), stop, Params(None), None, sl, vide)
    assert t["raison"].iloc[0] == "fin_donnees"                            # short : sortie_long ignorée
    t, _ = backtest(df, serie(6, **{"1": -1}), stop, Params(None), None, vide, sl)
    assert t["raison"].iloc[0] == "signal"                                 # short : sortie_short
    with pytest.raises(ValueError):
        backtest(df, serie(6), stop, Params(None), None, serie(5).astype(bool))
