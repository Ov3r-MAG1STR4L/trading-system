"""
Vérifie que l'environnement de recherche est prêt ET sûr.

Lancement (depuis le dossier trading-system, MT5 ouvert) :
  python scripts/check_env.py

Ce script ne passe aucun ordre. Il lit seulement des informations.
Code de sortie 0 = tout est bon, 1 = au moins un problème.
"""
import sys
import platform

sys.stdout.reconfigure(encoding="utf-8")  # console Windows cp1252 : évite le crash sur ✅/❌

ok = True


def check(label, cond, detail=""):
    global ok
    mark = "OK " if cond else "ERR"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    ok = ok and cond


# 1. Python
check("Python >= 3.10", sys.version_info >= (3, 10), platform.python_version())

# 2. Paquets
try:
    import numpy, pandas  # noqa: E401
    check("numpy / pandas", True, f"numpy {numpy.__version__}, pandas {pandas.__version__}")
except ImportError as e:
    check("numpy / pandas", False, f"{e} -> python -m pip install -r requirements.txt")

try:
    import MetaTrader5 as mt5
    check("Paquet MetaTrader5", True, str(getattr(mt5, "__version__", "?")))
except ImportError as e:
    check("Paquet MetaTrader5", False, f"{e} -> python -m pip install -r requirements.txt")
    sys.exit(1)

# 3. Connexion au terminal MT5
if not mt5.initialize():
    check("Connexion au terminal MT5", False,
          f"{mt5.last_error()} -> ouvre MT5 et connecte-toi au compte démo")
    sys.exit(1)

term = mt5.terminal_info()
check("Terminal MT5 connecté au serveur", bool(term and term.connected),
      term.name if term else "")

# 4. Sécurité : le compte DOIT être un compte démo
acc = mt5.account_info()
if acc is None:
    check("Compte de trading", False, "aucun compte connecté")
else:
    modes = {mt5.ACCOUNT_TRADE_MODE_DEMO: "DÉMO",
             mt5.ACCOUNT_TRADE_MODE_CONTEST: "CONCOURS",
             mt5.ACCOUNT_TRADE_MODE_REAL: "RÉEL"}
    mode = modes.get(acc.trade_mode, f"inconnu ({acc.trade_mode})")
    check("Compte en mode DÉMO", acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO,
          f"mode {mode}, serveur {acc.server}, devise {acc.currency}")
    if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL:
        print("\n!!! COMPTE RÉEL DÉTECTÉ — le projet est interdit en réel à ce stade. !!!")

# 5. Accès aux données
mt5.symbol_select("EURUSD", True)
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_D1, 0, 10)
check("Lecture de données (EURUSD D1)", rates is not None and len(rates) > 0,
      f"{0 if rates is None else len(rates)} bougies lues")

mt5.shutdown()

print("\nRésultat :", "environnement prêt ✅" if ok else "à corriger ❌")
sys.exit(0 if ok else 1)
