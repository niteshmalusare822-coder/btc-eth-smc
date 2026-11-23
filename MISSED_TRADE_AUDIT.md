# Missed Trade Audit (generated with AUDIT_ENHANCEMENTS.md)

**Date:** 2026-11-22 (Auto-Generated via audit_missed.py)  
**Window:** 2026-11-22 (full IST day)  
**Symbols audited:** 17 of 17

```text
A) Unique setups by final outcome (what actually happened to each setup)
      57  ALERT
      38  NO_REACHABLE_TARGETS
       3  COST_GATE

B) 5M bars by first blocking gate (time spent blocked, not trade count)
    1380  SETUP_EXPIRED
    1318  SETUP_WRONG_WAY
    1054  ALERT
     792  NO_REACHABLE_TARGETS
     282  SETUP_MITIGATED
      33  MISSED_ENTRY
      16  EXPIRED
      11  INVALIDATED
      10  COST_GATE

D) Where to look (report only, nothing here is applied automatically)

   NO_REACHABLE_TARGETS  (38)
      file : risk.py
      where: _rupee_targets() (about line 331), TP_R_LADDER (about line 56); structure_limit is passed from live_signal.py (~143) and backtest.py (~311)
      find : grep -n "TP_R_LADDER\|structure_limit\|def _rupee_targets" risk.py services/live_signal.py backtest.py
      try  : A/B: lower the minimum R of TP1 in TP_R_LADDER (1.5 -> 1.0), behind a flag, default unchanged
      try  : A/B: structure_limit = farthest swing instead of the nearest, behind a flag
      try  : Check stop width first: a very wide OB-wick stop makes 1.5R unreachable by construction
      note : Live does not pass atr to size_position(); backtest does. Align that before comparing.

   COST_GATE  (3)
      file : backtest.py / services/live_signal.py
      where: MAX_COST_IN_R env (default 0.75)
      find : grep -n "MAX_COST_IN_R" backtest.py services/live_signal.py
      try  : Cost gate exists because fees eat the trade when the stop is tight. Leave it.

C) Last bar of the window, per symbol

BTC
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-22 18:25:00, 8 setups seen)

ETH
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ✅
  Entry Valid        ✅
  Cost Gate          ✅
  Root cause: ALERT (setup would be shown)
  (last bar of window 2026-11-22 18:25:00, 9 setups seen)

SOL
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-22 18:25:00, 8 setups seen)

XRP
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_MITIGATED
  (last bar of window 2026-11-22 18:25:00, 5 setups seen)

AVAX
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_MITIGATED
  (last bar of window 2026-11-22 18:25:00, 5 setups seen)

LINK
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_MITIGATED
  (last bar of window 2026-11-22 18:25:00, 6 setups seen)

DOGE
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_MITIGATED
  (last bar of window 2026-11-22 18:25:00, 5 setups seen)

ADA
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ✅
  Entry Valid        ✅
  Cost Gate          ✅
  Root cause: ALERT (setup would be shown)
  (last bar of window 2026-11-22 18:25:00, 5 setups seen)

DEXE
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_EXPIRED
  (last bar of window 2026-11-22 18:25:00, 0 setups seen)

BANK
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_MITIGATED
  (last bar of window 2026-11-22 18:25:00, 8 setups seen)

BNB
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-22 18:25:00, 6 setups seen)

SUI
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_MITIGATED
  (last bar of window 2026-11-22 18:25:00, 8 setups seen)

HBAR
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-22 18:25:00, 4 setups seen)

LTC
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ❌
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_MITIGATED
  (last bar of window 2026-11-22 18:25:00, 5 setups seen)

BCH
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-22 18:25:00, 3 setups seen)

DOT
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-22 18:25:00, 7 setups seen)

1000PEPE
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-22 18:25:00, 6 setups seen)
```

> This shows WHICH gate blocked a trade, not whether the gate was wrong. A gate is only relaxed after out-of-sample evidence.

---
*Note: updated by the same daily GitHub Action as AUDIT_ENHANCEMENTS.md.*
