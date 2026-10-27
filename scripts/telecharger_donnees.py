"""
Télécharge les bougies D1 des marchés de config/marches.csv depuis MT5,
contrôle leur qualité et écrit un rapport par symbole.

Lancement (MT5 ouvert et connecté, compte DÉMO) :
  python scripts/telecharger_donnees.py
  python scripts/telecharger_donnees.py --selftest   # teste les contrôles, sans MT5

Sorties :
  data/<SYMBOLE>_D1.csv                       (non versionné, voir .gitignore)
  reports/AAAA-MM-JJ_v0.2_donnees/qualite.csv (un rapport par symbole)
  reports/AAAA-MM-JJ_v0.2_donnees/params.json

Ce script ne passe aucun ordre. Il lit seulement des données.
Code de sortie 0 = aucun symbole en ERREUR, 1 sinon.
"""
import json
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
MARCHES = ROOT / "config" / "marches.csv"
DATA = ROOT / "data"

PARAMS = {
    "timeframe": "D1",
    "date_debut_max": "2012-12-31",  # l'historique doit commencer avant cette date
    "bougies_min": 2500,             # ~10 ans de séances
    "trou_max_jours": 5,             # écart calendaire au-delà duquel on signale un trou
    "z_aberrant": 12,                # rendement à plus de 12 écarts robustes (MAD) = aberrant
    "derniere_bougie_max_jours": 7,  # données périmées au-delà
    "attente_max_s": 60,             # attente max du téléchargement initial MT5
    "debut_reference": "2012-08-06", # début de la période commune des backtests de portefeuille
    "plates_max_ref_pct": 0.5,       # % max de bougies plates tolérées sur la période de référence
}


def controler(df: pd.DataFrame, p: dict = PARAMS) -> dict:
    """Contrôles qualité sur un DataFrame time/open/high/low/close. Ne modifie pas df."""
    r = {"bougies": len(df), "erreurs": [], "avertissements": []}
    if df.empty:
        r["erreurs"].append("aucune donnée")
        return r

    t = df["time"]
    r["debut"], r["fin"] = t.min().date(), t.max().date()

    if not t.is_monotonic_increasing:
        r["erreurs"].append("dates non triées")
    n_dup = int(t.duplicated().sum())
    r["doublons"] = n_dup
    if n_dup:
        r["erreurs"].append(f"{n_dup} doublon(s) de date")

    prix = df[["open", "high", "low", "close"]]
    n_nan = int(prix.isna().any(axis=1).sum())
    n_neg = int((prix <= 0).any(axis=1).sum())
    r["manquantes"] = n_nan + n_neg
    if n_nan:
        r["erreurs"].append(f"{n_nan} bougie(s) avec prix manquant")
    if n_neg:
        r["erreurs"].append(f"{n_neg} bougie(s) avec prix <= 0")

    incoh = (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1)) \
        | (df["high"] < df["low"])
    r["ohlc_incoherents"] = int(incoh.sum())
    if incoh.any():
        r["erreurs"].append(f"{int(incoh.sum())} bougie(s) OHLC incohérente(s)")

    if r["debut"] > date.fromisoformat(p["date_debut_max"]) or len(df) < p["bougies_min"]:
        r["erreurs"].append(f"historique insuffisant ({len(df)} bougies depuis {r['debut']})")

    ts = t.sort_values().drop_duplicates().reset_index(drop=True)
    ecarts = ts.diff().dt.days
    trous = ecarts[ecarts > p["trou_max_jours"]]
    r["trous"] = len(trous)
    r["plus_grand_trou_j"] = int(ecarts.max()) if len(ecarts) > 1 else 0
    # liste datée de chaque trou : dernière bougie avant -> première bougie après
    r["trous_liste"] = [(ts[i - 1].date(), ts[i].date(), int(ecarts[i])) for i in trous.index]
    if len(trous):
        pire = trous.idxmax()
        r["avertissements"].append(
            f"{len(trous)} trou(s) > {p['trou_max_jours']} j, le plus grand : {int(trous.max())} j avant le {ts[pire].date()}")

    rend = np.log(df["close"]).diff().dropna()
    mad = (rend - rend.median()).abs().median() * 1.4826
    r["aberrants"] = 0
    if mad > 0:
        z = (rend - rend.median()).abs() / mad
        aberr = z[z > p["z_aberrant"]]
        r["aberrants"] = len(aberr)
        r["extremes_liste"] = [(df["time"][i].date(), float(rend[i])) for i in aberr.index]
        if len(aberr):
            exemples = ", ".join(f"{df['time'][i].date()} ({rend[i]:+.1%})" for i in aberr.nlargest(3).index)
            r["avertissements"].append(f"{len(aberr)} rendement(s) aberrant(s), ex. {exemples}")
    else:
        r["erreurs"].append("prix constants (MAD nulle)")

    n_plat = int((df["high"] == df["low"]).sum())
    r["bougies_plates"] = n_plat
    if n_plat:
        r["avertissements"].append(f"{n_plat} bougie(s) plate(s) (high = low)")
    ref = t >= pd.Timestamp(p["debut_reference"])
    r["plates_depuis_ref"] = int(((df["high"] == df["low"]) & ref).sum())
    r["plates_depuis_ref_pct"] = round(100 * r["plates_depuis_ref"] / max(int(ref.sum()), 1), 3)
    if r["plates_depuis_ref_pct"] > p["plates_max_ref_pct"]:
        r["erreurs"].append(f"{r['plates_depuis_ref_pct']} % de bougies plates depuis {p['debut_reference']}")

    age = (datetime.now(timezone.utc).date() - r["fin"]).days
    if age > p["derniere_bougie_max_jours"]:
        r["avertissements"].append(f"dernière bougie vieille de {age} j")

    return r


def telecharger(mt5, symbol: str, p: dict = PARAMS) -> pd.DataFrame:
    """Attend que MT5 ait fini de télécharger l'historique : nombre de bougies non nul et stable."""
    mt5.symbol_select(symbol, True)
    debut = datetime(1970, 1, 2, tzinfo=timezone.utc)
    precedent, stable, t0 = -1, 0, time.time()
    rates = None
    while time.time() - t0 < p["attente_max_s"]:
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_D1, debut, datetime.now(timezone.utc))
        n = 0 if rates is None else len(rates)
        stable = stable + 1 if n and n == precedent else 0
        if stable >= 2:  # même nombre 3 fois de suite = téléchargement terminé
            break
        precedent = n
        time.sleep(1)
    if rates is None or not len(rates):
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume", "spread"])
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")  # heure serveur MT5
    return df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]


def main():
    import MetaTrader5 as mt5

    if not mt5.initialize():
        print("Connexion MT5 impossible :", mt5.last_error())
        return 1
    compte = mt5.account_info()
    if compte is None or compte.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        print("STOP : le compte n'est pas en mode DÉMO. Aucune donnée téléchargée.")
        mt5.shutdown()
        return 1

    symboles = pd.read_csv(MARCHES, sep=";").query("actif == 1")
    out = ROOT / "reports" / f"{date.today():%Y-%m-%d}_v0.2_donnees"
    out.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(exist_ok=True)

    lignes, trous, extremes = [], [], []
    for _, m in symboles.iterrows():
        sym = m["symbol"]
        print(f"{sym:8} ...", end=" ", flush=True)
        df = telecharger(mt5, sym)
        r = controler(df)
        if len(df):
            df.to_csv(DATA / f"{sym}_D1.csv", index=False)
        trous += [{"symbol": sym, "derniere_bougie_avant": a, "premiere_bougie_apres": b, "ecart_jours": n,
                   "dans_periode_reference": b >= date.fromisoformat(PARAMS["debut_reference"])}
                  for a, b, n in r.get("trous_liste", [])]
        extremes += [{"symbol": sym, "date": d, "rendement_log": round(x, 4),
                      "a_verifier_source_externe": sym == "XAGUSD" and d.year >= 2026}
                     for d, x in r.get("extremes_liste", [])]
        statut = "ERREUR" if r["erreurs"] else "AVERTISSEMENT" if r["avertissements"] else "OK"
        print(statut)
        lignes.append({"symbol": sym, "groupe": m["groupe"], "statut": statut,
                       **{k: r.get(k) for k in ["bougies", "debut", "fin", "doublons", "manquantes",
                                                "ohlc_incoherents", "trous", "plus_grand_trou_j",
                                                "aberrants", "bougies_plates", "plates_depuis_ref",
                                                "plates_depuis_ref_pct"]},
                       "spread_median_points": float(df["spread"].median()) if len(df) else None,
                       "details": " | ".join(r["erreurs"] + r["avertissements"])})
    mt5.shutdown()

    rapport = pd.DataFrame(lignes)
    rapport.to_csv(out / "qualite.csv", index=False, sep=";")
    # Les trous restent dans les données : ni interpolation ni bougie créée. Le moteur v0.3 les lit ici.
    pd.DataFrame(trous, columns=["symbol", "derniere_bougie_avant", "premiere_bougie_apres", "ecart_jours",
                                 "dans_periode_reference"]).to_csv(out / "trous.csv", index=False, sep=";")
    pd.DataFrame(extremes, columns=["symbol", "date", "rendement_log", "a_verifier_source_externe"])         .to_csv(out / "evenements_extremes.csv", index=False, sep=";")
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (out / "params.json").write_text(json.dumps({**PARAMS, "git": git, "serveur": compte.server,
                                                 "symboles": symboles["symbol"].tolist()}, indent=2), encoding="utf-8")

    print()
    print(rapport.drop(columns="details").to_string(index=False))
    print("\nDétails :")
    for _, l in rapport[rapport["details"] != ""].iterrows():
        print(f"- {l['symbol']} [{l['statut']}] : {l['details']}")
    print(f"\nRapport -> {out}")
    return int((rapport["statut"] == "ERREUR").any())


def selftest():
    """Chaque contrôle doit détecter le défaut qu'on injecte."""
    rng = np.random.default_rng(0)
    t = pd.bdate_range("2005-01-03", periods=4000)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(t))))
    base = pd.DataFrame({"time": t, "open": c, "high": c * 1.005, "low": c * 0.995, "close": c})
    p = {**PARAMS, "derniere_bougie_max_jours": 10**6}

    ok = controler(base, p)
    assert not ok["erreurs"] and not ok["avertissements"], ok

    d = base.copy(); d.loc[10, "high"] = d.loc[10, "low"] * 0.9
    assert controler(d, p)["ohlc_incoherents"] == 1
    d = pd.concat([base, base.iloc[[5]]]).sort_values("time").reset_index(drop=True)
    assert controler(d, p)["doublons"] == 1
    d = base.iloc[::-1].reset_index(drop=True)
    assert "dates non triées" in controler(d, p)["erreurs"]
    d = base.copy(); d.loc[20, "close"] = np.nan
    assert controler(d, p)["manquantes"] == 1
    d = base.drop(index=range(100, 120)).reset_index(drop=True)
    r = controler(d, p)
    assert r["trous"] == 1 and r["trous_liste"][0][0] == t[99].date() and r["trous_liste"][0][1] == t[120].date()
    d = base.copy(); d.loc[500:, ["open", "high", "low", "close"]] *= 1.5
    assert controler(d, p)["aberrants"] >= 1
    d = base.iloc[-1000:].reset_index(drop=True)
    assert any("insuffisant" in e for e in controler(d, p)["erreurs"])
    d = base.copy(); d.loc[3000:3100, "high"] = d.loc[3000:3100, "low"]
    assert any("bougies plates depuis" in e for e in controler(d, p)["erreurs"])
    print("selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        sys.exit(main())
