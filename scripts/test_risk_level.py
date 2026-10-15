# Run: python scripts/test_risk_level.py
import sys; sys.path.insert(0, ".")
from agents.risk import risk_level
from types import SimpleNamespace as R

assert risk_level([], 5) == "unknown"            # proposed 5, none survived verification
assert risk_level([], 0) == "unknown"            # nothing found (Bug 5)
assert risk_level([R(severity=2)], 1) == "low"   # weak verified risk
assert risk_level([R(severity=3)], 1) == "medium"
assert risk_level([R(severity=4)], 1) == "medium"
assert risk_level([R(severity=4), R(severity=5)], 2) == "high"
print("PASS risk_level (6/6)")
