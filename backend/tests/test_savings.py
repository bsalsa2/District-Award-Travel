import pytest
from backend.main import (
    calc_gross_savings,
    calc_fee,
    calc_cpp_tenths,
    is_valid_transition,
)

# ── calc_gross_savings ──────────────────────────────────────────────────────
def test_gross_savings_basic():
    assert calc_gross_savings(400000, 30000, 10000) == 360000

def test_gross_savings_zero_costs():
    assert calc_gross_savings(200000, 0, 0) == 200000

def test_gross_savings_negative_result():
    # benchmark less than costs — gross can be negative
    assert calc_gross_savings(10000, 15000, 0) == -5000

# ── calc_fee ─────────────────────────────────────────────────────────────────
def test_fee_round_half_up():
    # 10% of $1 = $0.10 = 10 cents; no rounding ambiguity
    assert calc_fee(100, 1000) == 10

def test_fee_round_half_up_edge():
    # gross = 5 cents, rate = 10% → 0.5 cents → rounds up to 1
    assert calc_fee(5, 1000) == 1

def test_fee_round_down_edge():
    # gross = 4 cents, rate = 10% → 0.4 cents → rounds down to 0
    assert calc_fee(4, 1000) == 0

def test_fee_zero_on_negative_savings():
    assert calc_fee(-100, 1000) == 0

def test_fee_zero_on_zero_savings():
    assert calc_fee(0, 1000) == 0

def test_fee_large_realistic():
    # $3,550 savings at 10% = $355.00 = 35500 cents
    assert calc_fee(355000, 1000) == 35500

def test_fee_custom_rate():
    # 15% rate (1500 bps) on $1000 = $150 = 15000 cents
    assert calc_fee(100000, 1500) == 15000

# ── calc_cpp_tenths ──────────────────────────────────────────────────────────
def test_cpp_basic():
    # $355 savings / 75000 pts = 0.4733... cpp → *1000 = 473 tenths
    assert calc_cpp_tenths(35500, 75000) == 473

def test_cpp_zero_points():
    assert calc_cpp_tenths(35500, 0) == 0

def test_cpp_zero_savings():
    assert calc_cpp_tenths(0, 75000) == 0

def test_cpp_exact():
    # 100 cents / 100 points = 1.0 cpp → 1000 tenths
    assert calc_cpp_tenths(100, 100) == 1000

# ── is_valid_transition ──────────────────────────────────────────────────────
def test_transition_draft_to_presented():
    assert is_valid_transition("draft", "presented") is True

def test_transition_draft_to_void():
    assert is_valid_transition("draft", "void") is True

def test_transition_skip_not_allowed():
    assert is_valid_transition("draft", "booked") is False

def test_transition_paid_to_void():
    assert is_valid_transition("paid", "void") is True

def test_transition_void_is_terminal():
    assert is_valid_transition("void", "draft") is False

def test_transition_backward_not_allowed():
    assert is_valid_transition("booked", "draft") is False

def test_transition_invoiced_to_paid():
    assert is_valid_transition("invoiced", "paid") is True
