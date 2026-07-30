"""Pulse timer phase stagger: no two updaters may ever share a pulse.

Guards the [PRIMESUD] offset scheme in update.py against period retunes
in config.py -- a changed PULSE_* constant can silently realign timers.
Simulates the countdown/reload loop over one full LCM window, which
covers all reachable phase states.
"""
import math

import config
import update


def test_no_two_pulse_timers_ever_coincide():
    timers = {
        "violence": (config.PULSE_VIOLENCE, update._pulse_violence),
        "mobile": (config.PULSE_MOBILE, update._pulse_mobile),
        "music": (config.PULSE_MUSIC, update._pulse_music),
        "regen": (config.PULSE_REGEN, update._pulse_regen),
        "tick": (config.PULSE_TICK, update._pulse_tick),
        "area": (config.PULSE_AREA, update._pulse_area),
    }
    lcm = math.lcm(*(period for period, _ in timers.values()))
    counters = {name: offset for name, (_, offset) in timers.items()}
    for pulse in range(1, lcm + 1):
        hit = []
        for name, (period, _) in timers.items():
            counters[name] -= 1
            if counters[name] <= 0:
                counters[name] = period
                hit.append(name)
        assert len(hit) <= 1, (
            "pulse " + str(pulse) + " fires " + " ".join(hit)
            + " together; re-derive offsets in update.py"
        )
