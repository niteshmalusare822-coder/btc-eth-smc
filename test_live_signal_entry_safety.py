from services.live_signal import _limit_entry_status


def test_sell_pending_only_while_price_is_below_limit_and_stop():
    assert _limit_entry_status("bear", 48.9, 49.05, 49.24, False) == "PENDING_LIMIT"


def test_sell_touched_is_not_a_verified_fill():
    assert _limit_entry_status("bear", 48.9, 49.05, 49.24, True) == "TOUCHED_UNVERIFIED"


def test_sell_price_past_limit_is_missed_not_a_fresh_entry():
    assert _limit_entry_status("bear", 49.06, 49.05, 49.24, False) == "MISSED_ENTRY"


def test_sell_stop_crossed_invalidates_setup():
    assert _limit_entry_status("bear", 49.25, 49.05, 49.24, True) == "INVALIDATED"


def test_buy_limit_status_is_mirrored():
    assert _limit_entry_status("bull", 100.5, 100.0, 99.0, False) == "PENDING_LIMIT"
    assert _limit_entry_status("bull", 99.9, 100.0, 99.0, False) == "MISSED_ENTRY"
    assert _limit_entry_status("bull", 98.9, 100.0, 99.0, True) == "INVALIDATED"
