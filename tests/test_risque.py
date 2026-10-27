import math

import pandas as pd
import pytest

from src import risque as rq
from src.risque import RisqueInvalide

# ---------------- montant risqué, R et devise ----------------

def test_10000_euros_a_1_pourcent_donne_100_euros():
    assert rq.montant_risque(10_000, 0.01) == pytest.approx(100)


def test_moins_un_R_et_plus_deux_R_en_euros():
    assert rq.montant(-1, 100) == pytest.approx(-100)
    assert rq.montant(2, 100) == pytest.approx(200)


@pytest.mark.parametrize("entree,sortie,stop,attendu", [
    (100, 95, 95, -1),     # long, stop touché
    (100, 110, 95, 2),     # long, objectif 2R
    (100, 102.5, 95, 0.5),
    (100, 105, 105, -1),   # short, stop touché
    (100, 90, 105, 2),     # short, objectif 2R
    (100, 90, 95, -2),     # long, sortie sous le stop (gap)
])
def test_resultat_r_long_et_short(entree, sortie, stop, attendu):
    assert rq.resultat_r(entree, sortie, stop) == pytest.approx(attendu)


def test_resultat_r_refuse_stop_egal_entree_et_valeurs_manquantes():
    with pytest.raises(RisqueInvalide):
        rq.resultat_r(100, 105, 100)
    with pytest.raises(RisqueInvalide):
        rq.resultat_r(100, math.nan, 95)
    with pytest.raises(RisqueInvalide):
        rq.resultat_r(None, 105, 95)


# ---------------- taille de position ----------------

def test_taille_simple():
    # 100 € de risque, stop à 5 points, 1 €/point/unité -> 20 unités ; stop touché = -100 €
    t = rq.taille_position(10_000, 0.01, 5, valeur_point=1)
    assert t == pytest.approx(20)
    assert rq.risque_reel(t, 5, 1) == pytest.approx(100)


def test_taille_lot_forex():
    # EURUSD : 1 lot = 100 000 unités, stop 50 pips = 0.0050 -> 1 lot perd 500 $ ; on suppose 1 $ = 1 €
    t = rq.taille_position(10_000, 0.01, 0.0050, valeur_point=100_000)
    assert t == pytest.approx(0.2)


def test_taille_fractionnaire_autorisee_sans_pas():
    t = rq.taille_position(10_000, 0.01, 3, valeur_point=1)
    assert t == pytest.approx(33.3333, rel=1e-4)


def test_arrondi_vers_le_bas_ne_depasse_jamais_le_risque():
    t = rq.taille_position(10_000, 0.01, 0.0030, valeur_point=100_000, pas=0.01)  # 0.3333 lot -> 0.33
    assert t == pytest.approx(0.33)
    assert rq.risque_reel(t, 0.0030, 100_000) <= 100


def test_taille_sous_le_minimum_leve_une_erreur():
    # stop très large : 0.0007 lot théorique, minimum 0.01 lot -> refus (sinon on risquerait 14 fois plus)
    with pytest.raises(RisqueInvalide, match="minimum"):
        rq.taille_position(10_000, 0.01, 1.5, valeur_point=100_000, pas=0.01, taille_min=0.01)


def test_stop_tres_large_sans_contrainte_donne_une_petite_taille():
    t = rq.taille_position(10_000, 0.01, 1_000, valeur_point=1)
    assert t == pytest.approx(0.1)


def test_stop_tres_large_arrondi_a_zero_leve_une_erreur():
    with pytest.raises(RisqueInvalide, match="nulle"):
        rq.taille_position(10_000, 0.01, 1_000, valeur_point=1, pas=1)


@pytest.mark.parametrize("capital,risque,stop", [
    (0, 0.01, 5), (-1000, 0.01, 5),      # capital nul / négatif
    (10_000, 0, 5), (10_000, -0.01, 5),  # risque 0 % / négatif
    (10_000, 0.01, 0), (10_000, 0.01, -5),  # stop nul / négatif
    (math.nan, 0.01, 5), (10_000, math.nan, 5), (10_000, 0.01, math.nan), (10_000, 0.01, None),
])
def test_entrees_invalides_levent_une_erreur(capital, risque, stop):
    with pytest.raises(RisqueInvalide):
        rq.taille_position(capital, risque, stop)


def test_risque_trop_grand_probable_erreur_d_unite():
    with pytest.raises(RisqueInvalide, match="unité"):
        rq.montant_risque(10_000, 1)  # « 1 » au lieu de 0.01


# ---------------- equity et drawdown ----------------

def test_equity_risque_fixe_valeurs_connues():
    eq = rq.equity([1, 2, -1, -1, -1, 3], 10_000, 0.01, compose=False)
    assert eq.tolist() == pytest.approx([10_000, 10_100, 10_300, 10_200, 10_100, 10_000, 10_300])


def test_equity_composee():
    eq = rq.equity([1, 1, -1], 10_000, 0.01)
    assert eq.tolist() == pytest.approx([10_000, 10_100, 10_201, 10_098.99])


def test_equity_aucun_trade_reste_au_capital():
    assert rq.equity([], 10_000).tolist() == [10_000]


def test_drawdown_point_par_point_et_maximum():
    eq = rq.equity([1, 2, -1, -1, -1, 3], 10_000, 0.01, compose=False)
    d = rq.drawdown(eq)
    assert d["plus_haut"].tolist() == pytest.approx([10_000, 10_100, 10_300, 10_300, 10_300, 10_300, 10_300])
    assert d["dd_abs"].tolist() == pytest.approx([0, 0, 0, 100, 200, 300, 0])
    m = rq.drawdown_max(eq)
    assert m["dd_max_abs"] == pytest.approx(300)
    assert m["dd_max_pct"] == pytest.approx(300 / 10_300)
    assert m["fin_dd_max_pct"] == 5


def test_drawdown_max_absolu_et_relatif_a_des_moments_differents():
    m = rq.drawdown_max(pd.Series([100, 50, 1000, 600]))
    assert m["dd_max_pct"] == pytest.approx(0.5)  # 100 -> 50
    assert m["dd_max_abs"] == pytest.approx(400)  # 1000 -> 600 (40 % seulement)


def test_drawdown_nul_si_equity_toujours_croissante():
    assert rq.drawdown_max(rq.equity([1, 1, 1], 10_000))["dd_max_pct"] == 0


def test_drawdown_refuse_equity_invalide():
    for e in ([100, math.nan, 90], [100, 0, 90], [100, -5]):
        with pytest.raises(RisqueInvalide):
            rq.drawdown(pd.Series(e))


def test_equity_refuse_r_manquant():
    with pytest.raises(RisqueInvalide):
        rq.equity([1, math.nan], 10_000)


# ---------------- séries ----------------

@pytest.mark.parametrize("r,attendu", [
    ([], {"max_pertes": 0, "max_gains": 0, "courante": 0}),
    ([-1], {"max_pertes": 1, "max_gains": 0, "courante": -1}),
    ([2], {"max_pertes": 0, "max_gains": 1, "courante": 1}),
    ([1, 2, 0.5], {"max_pertes": 0, "max_gains": 3, "courante": 3}),
    ([-1, -1, -1, -1], {"max_pertes": 4, "max_gains": 0, "courante": -4}),
    ([1, -1, 1, -1, 1], {"max_pertes": 1, "max_gains": 1, "courante": 1}),
    ([-1, -1, 2, -1, -1, -1, 1], {"max_pertes": 3, "max_gains": 1, "courante": 1}),
    ([-1, -1, 0, -1], {"max_pertes": 2, "max_gains": 0, "courante": -1}),  # 0 R casse la série
])
def test_series(r, attendu):
    assert rq.series(r) == attendu
