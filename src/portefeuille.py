"""
Orchestration et agrégation multi-marchés. Ne fait ni la mécanique des trades (engine), ni les coûts
(couts), ni le reporting (rapport) : il les appelle et agrège.

1. Chaque marché est backtesté SÉPARÉMENT sur ses propres dates (aucun alignement par numéro de ligne,
   aucune date créée : un jour sans cotation n'existe pas pour ce marché, ce n'est pas un rendement nul).
   Le signal d'un marché ne dépend que de ses propres bougies passées.
2. Les coûts sont appliqués trade par trade (couts.appliquer) avant l'agrégation.
3. Allocation chronologique : à l'entrée d'un trade à la date E, risque = risque_pct x capital RÉALISÉ,
   capital réalisé = capital initial + P&L des trades SORTIS strictement avant E (prudent : une sortie
   le même jour n'est pas encore comptée). Chaque position garde son propre risque : les risques des
   positions simultanées s'ADDITIONNENT (pas de plafond en v0.3, l'exposition est mesurée).
4. Equity RÉALISÉE : capital + P&L cumulé aux dates de sortie. Le drawdown associé s'appelle
   `drawdown_realise` : les pertes latentes des positions ouvertes ne sont PAS comptées.
   (Ajouter le latent = valoriser chaque position ouverte à la clôture de chaque date : colonne
   `equity_latente` prévue dans la table equity, vide en v0.3.)
5. Un R manquant (SWAP_UNAVAILABLE) rend le P&L inconnu à partir de ce trade pour ce niveau de résultat :
   l'equity nette devient NaN à partir de là, jamais complétée par 0.

Hypothèse assumée : les positions sont indépendantes du capital (pas de limite de portefeuille), donc
backtester chaque marché séparément puis allouer est équivalent à une simulation pas à pas. Si une limite
de positions ou de risque total est ajoutée plus tard, il faudra une boucle événementielle commune.
"""
import numpy as np
import pandas as pd

from src import risque
from src.couts import SWAP_UNAVAILABLE, Hypotheses, appliquer
from src.engine import Params, backtest

NIVEAUX = {"brut": "R", "execution": "R_execution", "net": "R_net"}


# ---------------- 1-2 : backtests individuels + coûts ----------------

def executer(marches: dict, strategie, params: Params, infos: dict, h: Hypotheses | dict):
    """marches : {symbole: bougies de src.data} ; h : hypothèses de coûts communes ou {symbole: Hypotheses}
    (un plancher de spread en points dépend du marché). Renvoie (trades de tous les marchés, événements)."""
    tous, evs = [], []
    for sym, df in marches.items():
        s = strategie(df)
        trades, ev = backtest(df, s["signal"], s["stop_dist"], params, s.get("sortie"),
                              s.get("sortie_long"), s.get("sortie_short"))
        trades = appliquer(trades, df, infos[sym], h[sym] if isinstance(h, dict) else h)
        trades.insert(0, "symbol", sym)
        ev.insert(0, "symbol", sym)
        tous.append(trades)
        evs.append(ev)
    tous = [t for t in tous if len(t)] or tous[:1]
    evs = [e for e in evs if len(e)] or evs[:1]
    trades = pd.concat(tous, ignore_index=True) if tous else pd.DataFrame()
    ev = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame()
    return trier(trades), ev


def trier(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    return trades.sort_values(["entry_time", "symbol"], kind="stable").reset_index(drop=True)


# ---------------- 3-4 : allocation et equity ----------------

def allouer(trades: pd.DataFrame, capital: float, risque_pct: float, niveau: str = "brut") -> pd.DataFrame:
    """Par trade (ordre d'entrée) : capital réalisé à l'entrée, risque initial, P&L en devise du compte."""
    col = NIVEAUX[niveau]
    t = trier(trades)
    entree = t["entry_time"].to_numpy()
    sortie = t["exit_time"].to_numpy()
    r = t[col].to_numpy(float)
    cap, risq, pnl = np.full(len(t), np.nan), np.full(len(t), np.nan), np.full(len(t), np.nan)
    statut = np.full(len(t), "OK", dtype=object)
    for k in range(len(t)):
        avant = sortie[:k] < entree[k]  # trades déjà alloués (entrés avant) ET sortis avant cette entrée
        c = capital + pnl[:k][avant].sum() if not np.isnan(pnl[:k][avant]).any() else np.nan
        if np.isnan(c):
            statut[k] = "CAPITAL_INCONNU"  # R manquant ou ruine plus tôt : on ne l'invente pas
            continue
        cap[k] = c
        if c <= 0:
            statut[k] = "RUINE"  # plus de capital : trade non dimensionnable, P&L inconnu (NaN)
            continue
        risq[k] = risque.montant_risque(c, risque_pct)
        pnl[k] = r[k] * risq[k]  # NaN si R inconnu
    return pd.DataFrame({"symbol": t["symbol"], "entry_time": t["entry_time"], "exit_time": t["exit_time"],
                         "capital_entree": cap, "risque_initial": risq, "pnl": pnl, "statut_allocation": statut})


def equity(alloc: pd.DataFrame, capital: float, debut) -> pd.DataFrame:
    """Equity réalisée par date de sortie (plusieurs sorties le même jour = un seul point)."""
    p = alloc.groupby("exit_time", sort=True)["pnl"].sum(min_count=1)
    p = p.where(~alloc.groupby("exit_time")["pnl"].apply(lambda x: x.isna().any()))
    e = capital + p.cumsum(skipna=False)
    out = pd.DataFrame({"date": [pd.Timestamp(debut), *p.index], "equity_realisee": [capital, *e.to_numpy()]})
    out["equity_latente"] = np.nan  # non calculée en v0.3 (voir docstring)
    return out


def drawdown_realise(eq: pd.DataFrame) -> dict:
    e = eq["equity_realisee"]
    if e.isna().any():
        # P&L inconnu à partir d'un trade (SWAP_UNAVAILABLE ou RUINE) : pas de drawdown inventé
        return {"statut": "EQUITY_INCONNUE", "drawdown_realise": None, "drawdown_realise_pct": None}
    d = risque.drawdown_max(e)
    return {"drawdown_realise": d["dd_max_abs"], "drawdown_realise_pct": d["dd_max_pct"],
            "date_creux": eq["date"].iloc[d["fin_dd_max_pct"]]}


def exposition(alloc: pd.DataFrame) -> pd.DataFrame:
    """À chaque entrée : positions ouvertes et risque ouvert cumulé (une position sortie le même jour
    compte encore : prudent)."""
    lignes = []
    for a in alloc.itertuples():
        ouvertes = alloc[(alloc["entry_time"] <= a.entry_time) & (alloc["exit_time"] >= a.entry_time)]
        lignes.append({"date": a.entry_time, "symbol_entrant": a.symbol, "positions_ouvertes": len(ouvertes),
                       "marches_ouverts": ",".join(sorted(ouvertes["symbol"])),
                       "risque_ouvert": ouvertes["risque_initial"].sum(min_count=1),
                       "risque_ouvert_pct": ouvertes["risque_initial"].sum(min_count=1) / a.capital_entree})
    return pd.DataFrame(lignes, columns=["date", "symbol_entrant", "positions_ouvertes", "marches_ouverts",
                                         "risque_ouvert", "risque_ouvert_pct"])


SEUILS_EXPOSITION = (0.02, 0.03, 0.05, 0.08, 0.10)


def exposition_journaliere(alloc: pd.DataFrame, dates, capital: float) -> pd.DataFrame:
    """Pour chaque date RÉELLE (union des dates de cotation) : positions ouvertes (entrée <= date <= sortie,
    prudent), risque initial ouvert cumulé, capital réalisé (sorties strictement avant la date)."""
    dates = pd.DatetimeIndex(sorted(set(pd.to_datetime(list(dates)))))
    if alloc.empty:
        return pd.DataFrame({"date": dates, "positions": 0, "risque_ouvert": 0.0, "capital_realise": capital,
                             "risque_ouvert_pct": 0.0, "marches": ""})
    e, s = alloc["entry_time"].to_numpy(), alloc["exit_time"].to_numpy()
    risq, pnl = alloc["risque_initial"].to_numpy(float), alloc["pnl"].to_numpy(float)
    syms = alloc["symbol"].to_numpy()
    d = dates.to_numpy()[:, None]
    ouvert = (e[None, :] <= d) & (s[None, :] >= d)
    sorti = s[None, :] < d
    risque_ouvert = np.where(ouvert, risq[None, :], 0.0).sum(axis=1)
    cap = capital + np.where(sorti, pnl[None, :], 0.0).sum(axis=1)
    cap[np.isnan(np.where(sorti, pnl[None, :], 0.0)).any(axis=1)] = np.nan
    return pd.DataFrame({"date": dates, "positions": ouvert.sum(axis=1), "risque_ouvert": risque_ouvert,
                         "capital_realise": cap, "risque_ouvert_pct": risque_ouvert / cap,
                         "marches": [",".join(sorted(syms[row])) for row in ouvert]})


def _plus_longue_serie(masque) -> int:
    best = cur = 0
    for m in masque:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


def stats_exposition(ej: pd.DataFrame) -> dict:
    """Distribution du risque ouvert, jours STRICTEMENT au-dessus de chaque seuil, plus longue période
    consécutive (en jours de cotation du portefeuille) et marchés présents les jours d'exposition > 2 % / 5 %."""
    p = ej["risque_ouvert_pct"]
    out = {"positions_max": int(ej["positions"].max()) if len(ej) else 0,
           "risque_ouvert_max": float(ej["risque_ouvert"].max()) if len(ej) else 0.0,
           "risque_ouvert_max_pct": float(p.max()) if len(ej) else 0.0,
           "date_risque_max": ej.loc[p.idxmax(), "date"] if len(ej) and p.notna().any() else None,
           "jours_total": len(ej),
           "distribution_pct": {f"q{int(q * 100)}": float(p.quantile(q)) for q in (0.5, 0.75, 0.9, 0.95, 0.99)}
           if len(ej) else {},
           "jours_au_dessus": {}, "part_jours_au_dessus": {}, "plus_longue_periode_jours": {}}
    for s in SEUILS_EXPOSITION:
        k, m = f"{s:.0%}", (p > s + 1e-12)
        out["jours_au_dessus"][k] = int(m.sum())
        out["part_jours_au_dessus"][k] = float(m.mean()) if len(ej) else 0.0
        out["plus_longue_periode_jours"][k] = _plus_longue_serie(m)
    for s, nom in ((0.02, "2pct"), (0.05, "5pct")):
        compte = {}
        for ms in ej.loc[p > s + 1e-12, "marches"]:
            for sym in ms.split(","):
                compte[sym] = compte.get(sym, 0) + 1
        out[f"marches_jours_au_dessus_{nom}"] = dict(sorted(compte.items(), key=lambda x: -x[1]))
    return out


# ---------------- 5 : statistiques ----------------

def par_marche(trades: pd.DataFrame, alloc_brut: pd.DataFrame, marches: list) -> pd.DataFrame:
    t = trier(trades)
    t = t.assign(pnl_brut=alloc_brut["pnl"].to_numpy())
    total = t["pnl_brut"].sum()
    lignes = []
    for sym in marches:
        m = t[t["symbol"] == sym]
        indispo = int((m["statut_swap"] == SWAP_UNAVAILABLE).sum()) if len(m) else 0
        lignes.append({"symbol": sym, "trades": len(m),
                       "taux_reussite": float((m["R"] > 0).mean()) if len(m) else None,
                       "R_brut": m["R"].sum(), "cout_spread_R": m["cout_spread_R"].sum(),
                       "cout_slippage_R": m["cout_slippage_R"].sum(),
                       "swap_R": SWAP_UNAVAILABLE if indispo else m["swap_R"].sum(),
                       "R_net": SWAP_UNAVAILABLE if indispo else m["R_net"].sum(),
                       "pnl_brut": m["pnl_brut"].sum(),
                       "contribution_pnl_brut": m["pnl_brut"].sum() / total if total else None,
                       "traverse_gap": int(m["traverse_gap"].sum()), "swap_unavailable": indispo})
    return pd.DataFrame(lignes)


def analyser(trades: pd.DataFrame, evenements: pd.DataFrame, marches: list, capital: float,
             risque_pct: float, debut, dates=None) -> dict:
    """Tout ce que le rapport portefeuille enregistre : tables + résumé.
    dates : dates réelles de cotation (union des marchés) pour l'exposition journalière ;
    à défaut, union des dates d'entrée et de sortie."""
    allocs = {n: allouer(trades, capital, risque_pct, n) for n in NIVEAUX}
    equities = {n: equity(a, capital, debut) for n, a in allocs.items()}
    expo = exposition(allocs["brut"])
    if dates is None:
        dates = list(trades["entry_time"]) + list(trades["exit_time"]) if len(trades) else [debut]
    ej = exposition_journaliere(allocs["brut"], dates, capital)
    pm = par_marche(trades, allocs["brut"], marches)

    eq = equities["brut"][["date", "equity_realisee"]].rename(columns={"equity_realisee": "equity_brut_realisee"})
    for n in ("execution", "net"):
        eq[f"equity_{n}_realisee"] = equities[n]["equity_realisee"].to_numpy()
    eq["equity_latente"] = np.nan

    res = {"modele_equity": "réalisée aux dates de sortie ; pertes latentes NON comptées",
           "regle_risque": f"{risque_pct:.2%} du capital réalisé à l'entrée, risques simultanés additionnés, sans plafond",
           "trades_par_marche": {s: int((trades["symbol"] == s).sum()) for s in marches}}
    for n, e in equities.items():
        fin = e["equity_realisee"].iloc[-1]
        res[n] = {"capital_final": None if np.isnan(fin) else float(fin),
                  "resultat_monetaire": None if np.isnan(fin) else float(fin - capital),
                  **drawdown_realise(e)}
    res["exposition"] = {"positions_simultanees_max": int(expo["positions_ouvertes"].max()) if len(expo) else 0,
                         "risque_ouvert_max": float(expo["risque_ouvert"].max()) if len(expo) else 0.0,
                         "risque_ouvert_max_pct": float(expo["risque_ouvert_pct"].max()) if len(expo) else 0.0}
    res["exposition_journaliere"] = stats_exposition(ej)
    res["ruine"] = {n: bool((a["statut_allocation"] == "RUINE").any()) for n, a in allocs.items()}
    res["marches_swap_unavailable"] = sorted(trades.loc[trades["statut_swap"] == SWAP_UNAVAILABLE, "symbol"].unique()) \
        if len(trades) else []
    detail = trier(trades).assign(capital_entree=allocs["brut"]["capital_entree"].to_numpy(),
                                  risque_initial=allocs["brut"]["risque_initial"].to_numpy(),
                                  pnl_brut=allocs["brut"]["pnl"].to_numpy(),
                                  pnl_execution=allocs["execution"]["pnl"].to_numpy(),
                                  pnl_net=allocs["net"]["pnl"].to_numpy())
    tables = {"equity.csv": eq, "exposition.csv": expo, "exposition_journaliere.csv": ej, "par_marche.csv": pm,
              "allocation_brut.csv": allocs["brut"]}
    return {"resume": res, "tables": tables, "allocations": allocs, "trades": detail}
