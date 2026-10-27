"""
Backtest multi-paires / multi-stratégies avec les données MetaTrader 5.  (v0.3)

Prérequis :
  - MetaTrader 5 installé, connecté à un compte DÉMO, et ouvert pendant l'exécution
  - python -m pip install -r requirements.txt

Lancement (depuis le dossier trading-system) :
  python scripts/backtest.py

Sorties (dans reports/latest/) :
  results_summary.csv  -> une ligne par (paire, unité de temps, stratégie)
  trades.csv           -> le détail de chaque trade (non versionné, régénérable)

Limites connues (voir docs/regles-de-risque.md) : swaps, slippage et commissions non inclus.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

OUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "latest"

# ------------------------------------------------------------------
# Réglages
# ------------------------------------------------------------------
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
TIMEFRAMES = {"H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}
N_BARS = 20000        # nombre de bougies demandées (le broker peut en donner moins)
RISK = 0.01           # 1 % du capital risqué par trade
WARMUP = 210          # bougies ignorées au début (le temps que la MM 200 se calcule)


# ------------------------------------------------------------------
# Indicateurs (mêmes formules que TradingView)
# ------------------------------------------------------------------
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rma(s, n):
    return s.ewm(alpha=1 / n, adjust=False).mean()


def rsi(close, n=14):
    delta = close.diff()
    up = rma(delta.clip(lower=0), n)
    down = rma(-delta.clip(upper=0), n)
    return 100 - 100 / (1 + up / down)


def atr(df, n=14):
    prev_close = df["close"].shift()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return rma(tr, n)


def cross_up(a, b):
    return (a > b) & (a.shift() <= b.shift())


def cross_down(a, b):
    return (a < b) & (a.shift() >= b.shift())


# ------------------------------------------------------------------
# Stratégies : chacune renvoie les signaux + les règles de sortie
# ------------------------------------------------------------------
def strat_ma_cross(df):
    fast, slow, trend = ema(df["close"], 20), ema(df["close"], 50), ema(df["close"], 200)
    return {
        "long": cross_up(fast, slow) & (df["close"] > trend),
        "short": cross_down(fast, slow) & (df["close"] < trend),
        "exit_long": pd.Series(False, index=df.index),
        "exit_short": pd.Series(False, index=df.index),
        "stop_mult": 2.0,     # stop = 2 x ATR
        "target_r": 2.0,      # objectif = 2 x le risque
    }


def strat_rsi_mr(df):
    r, trend = rsi(df["close"], 14), ema(df["close"], 200)
    return {
        "long": cross_up(r, pd.Series(30, index=df.index)) & (df["close"] > trend),
        "short": cross_down(r, pd.Series(70, index=df.index)) & (df["close"] < trend),
        "exit_long": r > 50,
        "exit_short": r < 50,
        "stop_mult": 2.0,
        "target_r": None,     # pas d'objectif fixe, sortie au RSI 50
    }


STRATEGIES = {
    "MA_cross_trend": strat_ma_cross,
    "RSI_mean_rev": strat_rsi_mr,
}


# ------------------------------------------------------------------
# Moteur de backtest (résultats en multiples de risque "R")
#   - signal à la clôture d'une bougie -> entrée à l'ouverture de la suivante
#   - si stop et objectif touchés dans la même bougie -> on compte le stop (prudent)
#   - le spread du broker est déduit de chaque trade
# ------------------------------------------------------------------
def backtest(df, sig, symbol, tf_name, strat_name):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = atr(df).to_numpy()
    spread = df["spread_px"].to_numpy()
    longs, shorts = sig["long"].to_numpy(), sig["short"].to_numpy()
    ex_l, ex_s = sig["exit_long"].to_numpy(), sig["exit_short"].to_numpy()

    trades, pos = [], None
    n = len(df)
    for i in range(WARMUP, n):
        if pos is not None:
            d, exit_px, reason = pos["dir"], None, None
            if d == 1:
                if l[i] <= pos["stop"]:
                    exit_px, reason = min(o[i], pos["stop"]), "stop"
                elif pos["target"] is not None and h[i] >= pos["target"]:
                    exit_px, reason = max(o[i], pos["target"]), "target"
                elif ex_l[i]:
                    exit_px, reason = c[i], "signal"
            else:
                if h[i] >= pos["stop"]:
                    exit_px, reason = max(o[i], pos["stop"]), "stop"
                elif pos["target"] is not None and l[i] <= pos["target"]:
                    exit_px, reason = min(o[i], pos["target"]), "target"
                elif ex_s[i]:
                    exit_px, reason = c[i], "signal"

            if exit_px is not None:
                r = (exit_px - pos["entry"]) * d / pos["dist"] - pos["spread"] / pos["dist"]
                trades.append({
                    "symbol": symbol, "timeframe": tf_name, "strategy": strat_name,
                    "direction": "long" if d == 1 else "short",
                    "entry_time": pos["time"], "exit_time": df["time"].iloc[i],
                    "entry": pos["entry"], "exit": exit_px, "reason": reason, "R": r,
                })
                pos = None
            continue

        if i + 1 < n and (longs[i] or shorts[i]) and a[i] > 0:
            d = 1 if longs[i] else -1
            entry = o[i + 1]
            dist = a[i] * sig["stop_mult"]
            target = entry + d * dist * sig["target_r"] if sig["target_r"] else None
            pos = {"dir": d, "entry": entry, "dist": dist, "stop": entry - d * dist,
                   "target": target, "spread": spread[i], "time": df["time"].iloc[i + 1]}
    return trades


def summarize(trades, df, symbol, tf_name, strat_name):
    base = {"symbol": symbol, "timeframe": tf_name, "strategy": strat_name,
            "from": df["time"].iloc[WARMUP].date(), "to": df["time"].iloc[-1].date()}
    if not trades:
        return {**base, "trades": 0}
    r = np.array([t["R"] for t in trades])
    equity = np.cumprod(1 + RISK * r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))[1:]
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return {
        **base,
        "trades": len(r),
        "win_rate_%": round(100 * (r > 0).mean(), 1),
        "profit_factor": round(gains / losses, 3) if losses > 0 else None,
        "expectancy_R": round(r.mean(), 3),
        "total_return_%": round(100 * (equity[-1] - 1), 2),
        "max_drawdown_%": round(100 * (1 - equity / peak).max(), 2),
        "worst_loss_streak": max_streak(r < 0),
    }


def max_streak(mask):
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


# ------------------------------------------------------------------
# Données MT5
# ------------------------------------------------------------------
def resolve_symbol(name):
    """Certains brokers ajoutent un suffixe (EURUSD.m, EURUSDpro...)."""
    if mt5.symbol_info(name) is not None:
        return name
    matches = mt5.symbols_get(f"*{name}*") or []
    return matches[0].name if matches else None


def get_data(symbol, tf):
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, N_BARS)
    if rates is None or len(rates) <= WARMUP:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df["spread_px"] = df["spread"] * mt5.symbol_info(symbol).point
    return df


def main():
    if not mt5.initialize():
        print("Connexion à MetaTrader 5 impossible :", mt5.last_error())
        print("-> Vérifie que MT5 est ouvert et connecté à ton compte démo.")
        sys.exit(1)

    all_trades, summary = [], []
    for base_name in SYMBOLS:
        symbol = resolve_symbol(base_name)
        if symbol is None:
            print(f"[!] {base_name} introuvable chez ce broker, ignoré.")
            continue
        for tf_name, tf in TIMEFRAMES.items():
            df = get_data(symbol, tf)
            if df is None:
                print(f"[!] Pas assez de données pour {symbol} {tf_name}.")
                continue
            for strat_name, strat in STRATEGIES.items():
                trades = backtest(df, strat(df), base_name, tf_name, strat_name)
                all_trades += trades
                summary.append(summarize(trades, df, base_name, tf_name, strat_name))
                print(f"OK  {base_name:7} {tf_name}  {strat_name:15} {len(trades):4} trades")

    mt5.shutdown()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    res = pd.DataFrame(summary)
    res.to_csv(OUT_DIR / "results_summary.csv", index=False, sep=";", decimal=",")
    pd.DataFrame(all_trades).to_csv(OUT_DIR / "trades.csv", index=False, sep=";", decimal=",")

    print("\n" + res.to_string(index=False))
    print(f"\nFichiers créés dans {OUT_DIR}")


if __name__ == "__main__":
    main()
