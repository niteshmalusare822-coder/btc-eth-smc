# Missed Trade Audit (generated with AUDIT_ENHANCEMENTS.md)

**Date:** 2026-11-27 (Auto-Generated via audit_missed.py)  
**Window:** 2026-11-27 (full IST day)  
**Symbols audited:** 17 of 17

```text
A) Unique setups by final outcome (what actually happened to each setup)
     134  NO_REACHABLE_TARGETS
      29  ALERT
       8  COST_GATE
       1  INVALIDATED
       1  MISSED_ENTRY

B) 5M bars by first blocking gate (time spent blocked, not trade count)
    1855  NO_REACHABLE_TARGETS
    1356  SETUP_WRONG_WAY
     643  SETUP_MITIGATED
     598  SETUP_EXPIRED
     357  ALERT
      38  COST_GATE
      34  MISSED_ENTRY
       9  INVALIDATED
       6  EXPIRED

D) Where to look (report only, nothing here is applied automatically)

   NO_REACHABLE_TARGETS  (134)
      file : risk.py
      where: _rupee_targets() (about line 331), TP_R_LADDER (about line 56); structure_limit is passed from live_signal.py (~143) and backtest.py (~311)
      find : grep -n "TP_R_LADDER\|structure_limit\|def _rupee_targets" risk.py services/live_signal.py backtest.py
      try  : A/B: lower the minimum R of TP1 in TP_R_LADDER (1.5 -> 1.0), behind a flag, default unchanged
      try  : A/B: structure_limit = farthest swing instead of the nearest, behind a flag
      try  : Check stop width first: a very wide OB-wick stop makes 1.5R unreachable by construction
      note : Live does not pass atr to size_position(); backtest does. Align that before comparing.

   COST_GATE  (8)
      file : backtest.py / services/live_signal.py
      where: MAX_COST_IN_R env (default 0.75)
      find : grep -n "MAX_COST_IN_R" backtest.py services/live_signal.py
      try  : Cost gate exists because fees eat the trade when the stop is tight. Leave it.

   INVALIDATED  (1)
      file : services/live_signal.py
      where: classify_entry_state() (about line 49)
      find : grep -n "def classify_entry_state" services/live_signal.py
      try  : Not a strategy fault: price crossed the stop before entry.

   MISSED_ENTRY  (1)
      file : services/live_signal.py
      where: classify_entry_state() (about line 49)
      find : grep -n "def classify_entry_state" services/live_signal.py
      try  : Not a strategy fault: price already went through the limit. Do not chase.

C) Last bar of the window, per symbol

BTC
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ✅
  Entry Valid        ✅
  Cost Gate          ✅
  Root cause: ALERT (setup would be shown)
  (last bar of window 2026-11-27 18:25:00, 13 setups seen)

ETH
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 15 setups seen)

SOL
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-27 18:25:00, 11 setups seen)

XRP
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-27 18:25:00, 11 setups seen)

AVAX
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 7 setups seen)

LINK
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 13 setups seen)

DOGE
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-27 18:25:00, 11 setups seen)

ADA
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 9 setups seen)

DEXE
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 7 setups seen)

BANK
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 11 setups seen)

BNB
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 12 setups seen)

SUI
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ✅
  Entry Valid        ✅
  Cost Gate          ✅
  Root cause: ALERT (setup would be shown)
  (last bar of window 2026-11-27 18:25:00, 10 setups seen)

HBAR
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-27 18:25:00, 8 setups seen)

LTC
  4H Bias            ✅
  15M Setup          ❌
  Setup Alive        -
  Target Reachable   -
  Entry Valid        -
  Cost Gate          -
  Root cause: SETUP_WRONG_WAY
  (last bar of window 2026-11-27 18:25:00, 8 setups seen)

BCH
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ❌
  Entry Valid        -
  Cost Gate          -
  Root cause: NO_REACHABLE_TARGETS
  (last bar of window 2026-11-27 18:25:00, 11 setups seen)

DOT
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ✅
  Entry Valid        ❌
  Cost Gate          -
  Root cause: MISSED_ENTRY
  (last bar of window 2026-11-27 18:25:00, 8 setups seen)

1000PEPE
  4H Bias            ✅
  15M Setup          ✅
  Setup Alive        ✅
  Target Reachable   ✅
  Entry Valid        ✅
  Cost Gate          ✅
  Root cause: ALERT (setup would be shown)
  (last bar of window 2026-11-27 18:25:00, 8 setups seen)
```

> This shows WHICH gate blocked a trade, not whether the gate was wrong. A gate is only relaxed after out-of-sample evidence.

---
*Note: updated by the same daily GitHub Action as AUDIT_ENHANCEMENTS.md.*
