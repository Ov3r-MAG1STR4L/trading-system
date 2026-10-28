"""
Signal MÉCANIQUE servant uniquement à faire tourner le moteur sur des données réelles (v0.3).
Ce n'est PAS une stratégie testée ni à valider : aucune hypothèse, aucun réglage optimisé.

Croisement EMA 20 / EMA 50 ; stop = 2 x ATR(14) ; objectif fixé par le moteur (Params.target_r).
"""
import pandas as pd

from src.indicateurs import atr, ema

NOM = "exemple_mecanique_ema20_50"
PARAMS = {"ema_rapide": 20, "ema_lente": 50, "atr": 14, "stop_atr": 2.0, "chauffe": 60}


def signaux(df: pd.DataFrame, p: dict = PARAMS) -> dict:
    rapide, lente = ema(df["close"], p["ema_rapide"]), ema(df["close"], p["ema_lente"])
    haut = rapide > lente
    signal = (haut & ~haut.shift(1, fill_value=False)).astype(float) \
        - (~haut & haut.shift(1, fill_value=False)).astype(float)
    signal.iloc[:p["chauffe"]] = 0.0  # indicateurs pas encore stabilisés
    return {"signal": signal, "stop_dist": atr(df, p["atr"]) * p["stop_atr"]}
