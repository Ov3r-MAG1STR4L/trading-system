"""
Chargement des données D1 produites en v0.2 (data/<SYMBOLE>_D1.csv) et des trous (trous.csv).

Principe : on ne modifie, n'interpole et ne crée aucune bougie.
Un trou de données est seulement *marqué* : colonne `gap_avant` = True sur la première bougie
réellement disponible après le trou. Le moteur en déduit le statut DATA_GAP / NON_TRADABLE.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TROUS_CSV = ROOT / "reports" / "2026-10-28_v0.2_donnees" / "trous.csv"
DEBUT_REFERENCE = "2012-08-06"
COLONNES = ["time", "open", "high", "low", "close", "spread"]
STATUT_GAP = "DATA_GAP / NON_TRADABLE"


class DonneesInvalides(ValueError):
    """Données inutilisables : on préfère arrêter plutôt que backtester en silence sur du faux."""


def valider(df: pd.DataFrame, symbol: str = "?") -> None:
    if df.empty:
        raise DonneesInvalides(f"{symbol} : aucune bougie sur la période")
    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        raise DonneesInvalides(f"{symbol} : colonnes manquantes {manquantes}")
    if df[["open", "high", "low", "close"]].isna().any().any():
        raise DonneesInvalides(f"{symbol} : prix manquants (NaN)")
    if not df["time"].is_monotonic_increasing or df["time"].duplicated().any():
        raise DonneesInvalides(f"{symbol} : dates non triées ou en double")


def charger_trous(symbol: str, trous_csv: Path = TROUS_CSV) -> pd.DataFrame:
    """Trous de la v0.2 pour un symbole : dernière bougie avant -> première bougie après."""
    t = pd.read_csv(trous_csv, sep=";", parse_dates=["derniere_bougie_avant", "premiere_bougie_apres"])
    return t.loc[t["symbol"] == symbol, ["derniere_bougie_avant", "premiere_bougie_apres", "ecart_jours"]] \
        .reset_index(drop=True)


def marquer_trous(df: pd.DataFrame, trous: pd.DataFrame) -> pd.DataFrame:
    """Ajoute `gap_avant` sans toucher aux prix ni ajouter de ligne."""
    out = df.copy()
    reprises = set(pd.to_datetime(trous["premiere_bougie_apres"]).dt.normalize())
    out["gap_avant"] = out["time"].dt.normalize().isin(reprises)
    # la première bougie de la période n'a pas de bougie avant elle : pas de trou à signaler
    if len(out):
        out.loc[out.index[0], "gap_avant"] = False
    return out


def charger(symbol: str, debut: str = DEBUT_REFERENCE, fin: str | None = None,
            data_dir: Path = DATA_DIR, trous_csv: Path = TROUS_CSV) -> pd.DataFrame:
    """Bougies D1 d'un symbole sur [debut, fin], validées et avec les trous marqués."""
    df = pd.read_csv(data_dir / f"{symbol}_D1.csv", parse_dates=["time"])
    valider(df, symbol)  # sur le fichier brut complet
    masque = df["time"] >= pd.Timestamp(debut)
    if fin is not None:
        masque &= df["time"] <= pd.Timestamp(fin)
    df = df.loc[masque, COLONNES].reset_index(drop=True)
    valider(df, symbol)
    return marquer_trous(df, charger_trous(symbol, trous_csv))
