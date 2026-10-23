from types import SimpleNamespace
from regions_belief import tick, place_probs, search_order

def test_search_order_prefers_high_confidence_place():
    b = SimpleNamespace(place="L", conf=0.9, t=0)
    assert search_order(b, visible_in_front=False)[0] == "L"

def test_visible_object_returns_open_only():
    b = SimpleNamespace(place="L", conf=0.9, t=0)
    assert place_probs(b, visible_in_front=True) == {"OPEN": 1.0}

def test_confidence_decays_one_half_life():
    b = SimpleNamespace(place="L", conf=1.0, t=0)
    tick(b, now=60, hidden=True)   # HALF_LIFE_S = 60
    assert 0.45 < b.conf < 0.55