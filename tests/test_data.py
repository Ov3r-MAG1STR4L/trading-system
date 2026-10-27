import numpy as np
import pandas as pd
import pytest

from src import data
from tests.outils import bougies


def test_valider_refuse_prix_manquants():
    df = bougies([(1, 2, 0.5, 1.5)] * 3)
    df.loc[1, "close"] = np.nan
    with pytest.raises(data.DonneesInvalides, match="manquants"):
        data.valider(df)


def test_valider_refuse_doublons_et_desordre():
    df = bougies([(1, 2, 0.5, 1.5)] * 3)
    with pytest.raises(data.DonneesInvalides):
        data.valider(pd.concat([df, df.iloc[[1]]]))
    with pytest.raises(data.DonneesInvalides):
        data.valider(df.iloc[::-1])


def test_valider_refuse_vide_et_colonne_absente():
    with pytest.raises(data.DonneesInvalides):
        data.valider(bougies([]))
    with pytest.raises(data.DonneesInvalides, match="colonnes"):
        data.valider(bougies([(1, 2, 0.5, 1.5)]).drop(columns="spread"))


def test_marquer_trous_ne_cree_ni_ne_modifie_aucune_bougie():
    df = bougies([(1, 2, 0.5, 1.5)] * 5)
    trous = pd.DataFrame({"premiere_bougie_apres": [df["time"][3]]})
    out = data.marquer_trous(df.drop(columns="gap_avant"), trous)
    assert len(out) == len(df)
    pd.testing.assert_frame_equal(out[["time", "open", "high", "low", "close"]],
                                  df[["time", "open", "high", "low", "close"]])
    assert out["gap_avant"].tolist() == [False, False, False, True, False]


# ---- sur les vraies données v0.2 (ignoré si data/ est vide) ----
reel = pytest.mark.skipif(not (data.DATA_DIR / "US500_D1.csv").exists(), reason="données v0.2 absentes")


@reel
def test_charger_respecte_la_periode_et_ne_change_pas_les_prix():
    brut = pd.read_csv(data.DATA_DIR / "EURUSD_D1.csv", parse_dates=["time"])
    df = data.charger("EURUSD")
    assert df["time"].min() >= pd.Timestamp(data.DEBUT_REFERENCE)
    attendu = brut[brut["time"] >= pd.Timestamp(data.DEBUT_REFERENCE)].reset_index(drop=True)
    pd.testing.assert_frame_equal(df[data.COLONNES], attendu[data.COLONNES])


@reel
def test_trou_us500_2025_marque_et_non_rempli():
    df = data.charger("US500")
    reprise = df[df["time"] == "2025-09-09"]
    assert len(reprise) == 1 and reprise["gap_avant"].iloc[0]
    dedans = df[(df["time"] > "2025-07-16") & (df["time"] < "2025-09-09")]
    assert dedans.empty, "aucune bougie ne doit exister pendant le trou"
