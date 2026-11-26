# Missed Trade Audit (generated with AUDIT_ENHANCEMENTS.md)

**Date:** 2026-11-25 (Auto-Generated via audit_missed.py)  
**Window:** 2026-11-25 (full IST day)  
**Symbols audited:** 17 of 17

```text
A) Unique setups by final outcome (what actually happened to each setup)
      72  NO_REACHABLE_TARGETS
      27  ALERT
       6  COST_GATE

B) 5M bars by first blocking gate (time spent blocked, not trade count)
    1547  SETUP_EXPIRED
    1450  SETUP_WRONG_WAY
     798  NO_REACHABLE_TARGETS
     560  SETUP_MITIGATED
     305  ALERT
     194  COST_GATE
      18  MISSED_ENTRY
      16  INVALIDATED
       8  EXPIRED

D) Where to look (report only, nothing here is applied automatically)

   NO_REACHABLE_TARGETS  (72)
      file : risk.py
      where: _rupee_targets() (about line 331), TP_R_LADDER (about line 56); structure_limit is passed from live_signal.py (~143) and backtest.py (~311)
      find : grep -n "TP_R_LADDER\|structure_limit\|def _rupee_targets" risk.py services/live_signal.py backtest.py
      try  : A/B: lower the minimum R of TP1 in TP_R_LADDER (1.5 -> 1.0), behind a flag, default unchanged
      try  : A/B: structure_limit = farthest swing instead of the nearest, behind a flag
      try  : Check stop width first: a very wide OB-wick stop makes 1.5R unreachable by construction
      note : Live does not pass atr to size_position(); backtest does. Align that before comparing.

   COST_GATE  (6)
      file : backtest.py / services/live_signal.py
      where: MAX_COST_IN_R env (default 0.75)
      find : grep -n "MAX_COST_IN_R" backtest.py services/live_signal.py
      try  : Cost gate exists because fees eat the trade when the stop is tight. Leave it.

C) Last bar of the window, per symbol

BTC
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-25 18:25:00, 6 setups seen)

ETH
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-25 18:25:00, 5 setups seen)

SOL
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 7 setups seen)

XRP
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-25 18:25:00, 6 setups seen)

AVAX
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 8 setups seen)

LINK
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 8 setups seen)

DOGE
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 6 setups seen)

ADA
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 6 setups seen)

DEXE
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 3 setups seen)

BANK
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-25 18:25:00, 4 setups seen)

BNB
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-25 18:25:00, 7 setups seen)

SUI
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 8 setups seen)

HBAR
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 5 setups seen)

LTC
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 5 setups seen)

BCH
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-25 18:25:00, 5 setups seen)

DOT
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 8 setups seen)

1000PEPE
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-25 18:25:00, 8 setups seen)
```

> This shows WHICH gate blocked a trade, not whether the gate was wrong. A gate is only relaxed after out-of-sample evidence.

---
*Note: updated by the same daily GitHub Action as AUDIT_ENHANCEMENTS.md.*
