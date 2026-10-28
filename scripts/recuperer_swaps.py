"""
Récupère les swaps (frais de portage overnight) des marchés de config/marches.csv.

Lancement (MT5 ouvert et connecté, compte DÉMO) :
  python scripts/recuperer_swaps.py

Sortie : reports/AAAA-MM-JJ_v0.4_swaps/swaps.csv (v0.4 : devises et mode de calcul ajoutés)

Attention : MT5 ne donne que les swaps ACTUELS, pas leur historique.
Appliquer ces valeurs à 2012-2026 est une approximation (les taux d'intérêt ont beaucoup varié).

Ce script ne passe aucun ordre. Il lit seulement des informations.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import MetaTrader5 as mt5

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
MARCHES = ROOT / "config" / "marches.csv"

# Unité des colonnes swap_long / swap_short selon swap_mode (doc MQL5 ENUM_SYMBOL_SWAP_MODE)
UNITES = {
    mt5.SYMBOL_SWAP_MODE_DISABLED: "pas de swap",
    mt5.SYMBOL_SWAP_MODE_POINTS: "points par lot et par nuit",
    mt5.SYMBOL_SWAP_MODE_CURRENCY_SYMBOL: "devise de base du symbole par lot",
    mt5.SYMBOL_SWAP_MODE_CURRENCY_MARGIN: "devise de marge par lot",
    mt5.SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT: "devise du compte par lot",
    mt5.SYMBOL_SWAP_MODE_INTEREST_CURRENT: "% annuel du prix courant",
    mt5.SYMBOL_SWAP_MODE_INTEREST_OPEN: "% annuel du prix d'ouverture",
    mt5.SYMBOL_SWAP_MODE_REOPEN_CURRENT: "réouverture au prix de clôture +/- points",
    mt5.SYMBOL_SWAP_MODE_REOPEN_BID: "réouverture au bid +/- points",
}
# Devise dans laquelle MT5 exprime swap_long / swap_short (doc MQL5 ENUM_SYMBOL_SWAP_MODE)
def devise_swap(i, devise_compte):
    return {mt5.SYMBOL_SWAP_MODE_POINTS: "points", mt5.SYMBOL_SWAP_MODE_CURRENCY_SYMBOL: i.currency_base,
            mt5.SYMBOL_SWAP_MODE_CURRENCY_MARGIN: i.currency_margin,
            mt5.SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT: devise_compte}.get(i.swap_mode, "inconnue")


JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]


def main():
    if not mt5.initialize():
        print("Connexion MT5 impossible :", mt5.last_error())
        return 1
    compte = mt5.account_info()
    if compte is None or compte.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        print("STOP : le compte n'est pas en mode DÉMO.")
        mt5.shutdown()
        return 1

    maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lignes = []
    for sym in pd.read_csv(MARCHES, sep=";").query("actif == 1")["symbol"]:
        i = mt5.symbol_info(sym)
        if i is None:
            print(f"{sym} : introuvable", mt5.last_error())
            continue
        lignes.append({
            "symbol": sym,
            "swap_long": i.swap_long,
            "swap_short": i.swap_short,
            "swap_mode": i.swap_mode,
            "unite": UNITES.get(i.swap_mode, f"mode inconnu {i.swap_mode}"),
            "triple_swap_jour": JOURS[i.swap_rollover3days] if 0 <= i.swap_rollover3days < 7 else i.swap_rollover3days,
            "point": i.point,
            "contrat_taille": i.trade_contract_size,
            "devise_swap": devise_swap(i, compte.currency),
            "devise_profit": i.currency_profit,
            "devise_base": i.currency_base,
            "devise_marge": i.currency_margin,
            "mode_calcul": i.trade_calc_mode,  # 0 forex, 1 futures, 2 CFD, 3 CFD index, 4 CFD leverage
            "taille_tick": i.trade_tick_size,
            "valeur_tick_compte": round(i.trade_tick_value, 6),
            "devise_compte": compte.currency,
            "spread_actuel_points": i.spread,
            "date_recuperation": maintenant,
            "serveur": compte.server,
        })
    mt5.shutdown()

    df = pd.DataFrame(lignes)
    out = ROOT / "reports" / f"{datetime.now():%Y-%m-%d}_v0.4_swaps"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "swaps.csv", index=False, sep=";")
    print(df[["symbol", "swap_long", "swap_short", "swap_mode", "devise_swap", "devise_profit", "mode_calcul",
              "contrat_taille", "triple_swap_jour"]].to_string(index=False))
    print(f"\n{len(df)} symboles -> {out / 'swaps.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
