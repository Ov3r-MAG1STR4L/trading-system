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
        trades, ev = backtest(df, s["signal"], s["stop_dist"], params, s.get("sortie"))
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
    for k in range(len(t)):
        avant = sortie[:k] < entree[k]  # trades déjà alloués (entrés avant) ET sortis avant cette entrée
        c = capital + pnl[:k][avant].sum() if not np.isnan(pnl[:k][avant]).any() else np.nan
        if np.isnan(c):
            continue  # capital inconnu (R manquant plus tôt) : on ne l'invente pas
        cap[k] = c
        risq[k] = risque.montant_risque(c, risque_pct)
        pnl[k] = r[k] * risq[k]  # NaN si R inconnu
    return pd.DataFrame({"symbol": t["symbol"], "entry_time": t["entry_time"], "exit_time": t["exit_time"],
                         "capital_entree": cap, "risque_initial": risq, "pnl": pnl})


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
        return {"statut": SWAP_UNAVAILABLE, "drawdown_realise": None, "drawdown_realise_pct": None}
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
             risque_pct: float, debut) -> dict:
    """Tout ce que le rapport portefeuille enregistre : tables + résumé."""
    allocs = {n: allouer(trades, capital, risque_pct, n) for n in NIVEAUX}
    equities = {n: equity(a, capital, debut) for n, a in allocs.items()}
    expo = exposition(allocs["brut"])
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
    res["marches_swap_unavailable"] = sorted(trades.loc[trades["statut_swap"] == SWAP_UNAVAILABLE, "symbol"].unique()) \
        if len(trades) else []
    detail = trier(trades).assign(capital_entree=allocs["brut"]["capital_entree"].to_numpy(),
                                  risque_initial=allocs["brut"]["risque_initial"].to_numpy(),
                                  pnl_brut=allocs["brut"]["pnl"].to_numpy(),
                                  pnl_execution=allocs["execution"]["pnl"].to_numpy(),
                                  pnl_net=allocs["net"]["pnl"].to_numpy())
    tables = {"equity.csv": eq, "exposition.csv": expo, "par_marche.csv": pm,
              "allocation_brut.csv": allocs["brut"]}
    return {"resume": res, "tables": tables, "allocations": allocs, "trades": detail}
