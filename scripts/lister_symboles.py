"""
Cherche chez ton broker MT5 les indices, matières premières et paires forex
utiles pour un portefeuille de suivi de tendance, et vérifie l'historique dispo.

Lancement (MT5 ouvert et connecté) :
  python scripts/lister_symboles.py

Sortie : reports/symboles_dispo.csv
"""
import re
from pathlib import Path
import pandas as pd
import MetaTrader5 as mt5

OUT = Path(__file__).resolve().parent.parent / "reports" / "symboles_dispo.csv"

# Mots-clés recherchés dans le nom ou la catégorie du symbole
KEYWORDS = [
    # indices
    "US500", "SPX", "SP500", "US30", "DJ", "NAS", "US100", "USTEC", "GER", "DAX", "DE40",
    "UK100", "FTSE", "JP225", "NIKKEI", "FRA40", "CAC", "EU50", "STOXX", "AUS200",
    # matières premières
    "XAU", "GOLD", "XAG", "SILVER", "WTI", "BRENT", "OIL", "XTI", "XBR", "NGAS", "COPPER",
    # obligations
    "BUND", "TNOTE", "UST",
]
FX = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
      "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "EURCHF"]


def main():
    if not mt5.initialize():
        print("Connexion MT5 impossible :", mt5.last_error())
        return

    rows = []
    for s in mt5.symbols_get() or []:
        name, path = s.name.upper(), (s.path or "").upper()
        is_fx = any(name.startswith(f) for f in FX)
        is_other = any(k in name for k in KEYWORDS)
        if not (is_fx or is_other):
            continue
        # on évite les actions individuelles et les dérivés exotiques
        if re.search(r"STOCK|SHARE|EQUIT|ETF", path) and not is_fx:
            continue

        mt5.symbol_select(s.name, True)
        rates = mt5.copy_rates_from_pos(s.name, mt5.TIMEFRAME_D1, 0, 20000)
        n_bars = 0 if rates is None else len(rates)
        first = pd.to_datetime(rates[0]["time"], unit="s").date() if n_bars else None

        rows.append({
            "symbol": s.name,
            "category": s.path,
            "description": s.description,
            "D1_bars": n_bars,
            "first_date": first,
            "swap_long": s.swap_long,
            "swap_short": s.swap_short,
            "swap_mode": s.swap_mode,
            "spread_points": s.spread,
        })

    mt5.shutdown()
    df = pd.DataFrame(rows).sort_values(["category", "symbol"])
    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False, sep=";", decimal=",")
    print(df[["symbol", "category", "D1_bars", "first_date"]].to_string(index=False))
    print(f"\n{len(df)} symboles trouvés -> {OUT}")


if __name__ == "__main__":
    main()
