"""Pulse timer phase stagger: no two updaters may ever share a pulse.

Guards update._stagger_offsets against period retunes in config.py --
shipped PULSE_* values must admit a perfect stagger.  Simulates the
countdown/reload loop over one full LCM window, which covers all
reachable phase states.
"""
import math

import config
import update


def test_no_two_pulse_timers_ever_coincide():
    periods = (config.PULSE_VIOLENCE, config.PULSE_MOBILE, config.PULSE_MUSIC,
               config.PULSE_REGEN, config.PULSE_TICK, config.PULSE_AREA)
    offsets = update._stagger_offsets(periods)
    lcm = math.lcm(*periods)
    counters = list(offsets)
    for pulse in range(1, lcm + 1):
        hit = 0
        for i, period in enumerate(periods):
            counters[i] -= 1
            if counters[i] <= 0:
                counters[i] = period
                hit += 1
        assert hit <= 1, (
            "pulse " + str(pulse) + " fires " + str(hit) + " timers; "
            "shipped PULSE_* values no longer admit a perfect stagger"
        )


def test_first_fire_delays_stay_short():
    periods = (config.PULSE_VIOLENCE, config.PULSE_MOBILE, config.PULSE_MUSIC,
               config.PULSE_REGEN, config.PULSE_TICK, config.PULSE_AREA)
    offsets = update._stagger_offsets(periods)
    assert offsets[0] == 1  # violence first: combat round lands on pulse 1
    assert all(1 <= o <= p for o, p in zip(offsets, periods))


def test_imperfect_periods_still_return_valid_offsets():
    # five timers, all period 4: only 4 residues -> perfect stagger impossible
    offsets = update._stagger_offsets((4, 4, 4, 4, 4))
    assert len(offsets) == 5
    assert all(1 <= o <= 4 for o in offsets)
