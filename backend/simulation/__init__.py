"""Training-session simulation engines for Algorithm 3 realtime (Phase B).

- fire_spread.py : FireGrid — fire index map parallel to the real map (spawn + spread).
- extinguish.py  : spray-cone hit detection + intensity reduction + water depletion.
- scoring.py     : per-device scoring (parameters at the top of the file).
- simulator.py   : SessionSimulation — ties the three engines together, stepped per tick.

Tất cả tham số tinh chỉnh được đặt ở ĐẦU mỗi file tương ứng.
"""
from .simulator import SessionSimulation

__all__ = ["SessionSimulation"]
