"""Full-application-heap area-load benchmark for physical HP Prime. [PRIMESUD]

Do not run this file directly. Build with:

    python tools/build_dist.py --area-bench --zip

The build copies a minified form to ``area_load_bench.txt`` and enables the
benchmark branch in the transfer copy only. PrimeSUD initializes its normal
application heap, skips save loading/gameplay, runs these cases, and writes
``area_load_bench.log`` after every case so a partial log survives a failure.
"""

import gc

import config
import mob
import world
from mob import create_area_states
from player import create_char
from prime_platform import ticks
from util import num_str


LOG_FILE = "area_load_bench.log"

# Small / middle / largest generated files. Foreign-template owners are
# preloaded so every measured pass is a realistic eviction reload, not a
# first-load cascade.
_TARGETS = (
    ("pestates", ()),
    ("catacomb", ()),
    ("newthalos", ("midgaard",)),
)

_lines = []
_terminal = None


def _free():
    """Return raw free heap, or -1 on desktop runtimes. [PRIMESUD]"""
    return gc.mem_free() if hasattr(gc, "mem_free") else -1


def _write_log():
    """Checkpoint complete results with one write. [PRIMESUD]"""
    with open(LOG_FILE, "w") as f:
        f.write("\n".join(_lines))


def _checkpoint(line):
    """Append one line and persist all results. [PRIMESUD]"""
    _lines.append(line)
    _write_log()
    _terminal.print(line)


def _quiet_notice(_tag):
    """Suppress rendering so timings cover loading, not terminal output. [PRIMESUD]"""
    return


def _target_vnum(tag):
    """Return static low VNUM for an area tag. [PRIMESUD]"""
    for _fname, _tag, _name, lo, _hi in world._AREA_FILES:
        if _tag == tag:
            return lo
    return 0


def _setup_world(tag, dependencies, pressured):
    """Create repeatable unloaded-target state. [PRIMESUD]"""
    world.reset_lazy()
    world.areas = create_area_states()
    mob._RACE_CACHE.clear()
    player = create_char()
    world.chars[1] = player

    for dep in dependencies:
        world._load_area(dep)

    if pressured:
        for _fname, other, _name, _lo, _hi in world._AREA_FILES:
            if len(world._LOADED_AREAS) >= config.AREA_CACHE_MAX:
                break
            if (other == tag or other in dependencies
                    or other in world._LOADED_AREAS):
                continue
            world._load_area(other)

    # Seed target once, then evict it. All measured cases therefore replay
    # identical pending deltas and keep foreign-template dependencies resident.
    if tag not in world._LOADED_AREAS:
        world._load_area(tag)
    world._unload_area(tag)
    if pressured:
        # A single load can cascade past the cap. Trim with production
        # keep-set/LRU behavior so every pressure case starts exactly full.
        player["room"] = _target_vnum(tag)
        world.maybe_evict(player, True)
    gc.collect()
    return player


def _result_line(label, load_ms, reset_ms, pre_ms, post_ms,
                 areas0, areas1, free0, free1):
    """Render one firmware-safe result row. [PRIMESUD]"""
    return ("case=" + label
            + "|load_ms=" + num_str(load_ms)
            + "|reset_ms=" + num_str(reset_ms)
            + "|other_ms=" + num_str(load_ms - reset_ms)
            + "|pre_ms=" + num_str(pre_ms)
            + "|post_ms=" + num_str(post_ms)
            + "|total_ms=" + num_str(pre_ms + load_ms + post_ms)
            + "|areas0=" + num_str(areas0)
            + "|areas1=" + num_str(areas1)
            + "|free0=" + num_str(free0)
            + "|free1=" + num_str(free1))


def _load_once(tag, label, original_file, shared):
    """Measure one target reload without cache eviction. [PRIMESUD]"""
    world._TAG_TO_FILE[tag] = ("bench_" + original_file
                               if shared else original_file)
    reset_ms = [0]
    original_reset = world._reset_loaded_area

    def timed_reset(*args):
        t0 = ticks()
        original_reset(*args)
        reset_ms[0] += ticks() - t0

    world._reset_loaded_area = timed_reset
    areas0 = len(world._LOADED_AREAS)
    free0 = _free()
    try:
        t0 = ticks()
        world._load_area(tag)
        load_ms = ticks() - t0
    finally:
        world._reset_loaded_area = original_reset
        world._TAG_TO_FILE[tag] = original_file
    return _result_line(label, load_ms, reset_ms[0], 0, 0,
                        areas0, len(world._LOADED_AREAS), free0, _free())


def _run_reload_group(tag, dependencies, pressured, original_file):
    """Compare a baseline reload with the shared-flag area variant. [PRIMESUD]"""
    player = _setup_world(tag, dependencies, pressured)
    prefix = ("pressure/" if pressured else "reload/") + tag + "/"
    cases = (
        ("baseline", False),
        ("shared_flags", True),
    )
    _checkpoint("state=" + prefix[:-1]
                + "|areas=" + num_str(len(world._LOADED_AREAS))
                + "|free=" + num_str(_free()))
    for name, shared in cases:
        label = prefix + name
        _checkpoint("begin=" + label)
        gc.collect()
        line = _load_once(tag, label, original_file, shared)
        _checkpoint(line)
        player["room"] = config.R_STARTING_ROOM
        world._unload_area(tag)
        gc.collect()


def _eviction_case(tag, dependencies, original_file,
                   label, pre_evict, shared):
    """Compare existing post-load eviction with reserved-slot eviction. [PRIMESUD]"""
    player = _setup_world(tag, dependencies, True)
    _checkpoint("begin=" + label)
    gc.collect()
    world._TAG_TO_FILE[tag] = ("bench_" + original_file
                               if shared else original_file)
    reset_ms = [0]
    original_reset = world._reset_loaded_area
    old_cap = config.AREA_CACHE_MAX
    pre_ms = 0
    post_ms = 0
    areas0 = len(world._LOADED_AREAS)
    free0 = _free()
    player["room"] = _target_vnum(tag)

    def timed_reset(*args):
        t0 = ticks()
        original_reset(*args)
        reset_ms[0] += ticks() - t0

    try:
        if pre_evict:
            # Reuse production keep-set/LRU logic, temporarily asking it to
            # leave one slot for incoming area.
            config.AREA_CACHE_MAX = max(0, old_cap - 1)
            t0 = ticks()
            world.maybe_evict(player, True)
            pre_ms = ticks() - t0
            config.AREA_CACHE_MAX = old_cap

        world._reset_loaded_area = timed_reset
        t0 = ticks()
        world._load_area(tag)
        load_ms = ticks() - t0
        world._reset_loaded_area = original_reset

        if not pre_evict:
            t0 = ticks()
            world.maybe_evict(player, True)
            post_ms = ticks() - t0
    finally:
        config.AREA_CACHE_MAX = old_cap
        world._reset_loaded_area = original_reset
        world._TAG_TO_FILE[tag] = original_file

    _checkpoint(_result_line(label, load_ms, reset_ms[0], pre_ms, post_ms,
                             areas0, len(world._LOADED_AREAS), free0, _free()))


def run(game):
    """Run full benchmark and checkpoint ``area_load_bench.log``. [PRIMESUD]"""
    global _terminal
    _terminal = game.tr
    del _lines[:]
    original_notice = world._loading_notice
    original_files = {}
    for _tag, _deps in _TARGETS:
        original_files[_tag] = world._TAG_TO_FILE[_tag]

    failed = None
    try:
        world._loading_notice = _quiet_notice
        _checkpoint("PrimeSUD area-load benchmark v3")
        _checkpoint("notices=off|cache_max=" + num_str(config.AREA_CACHE_MAX)
                    + "|full_heap_free=" + num_str(_free()))
        _checkpoint("columns=load/reset/other/pre/post/total ms; raw free heap")

        for tag, dependencies in _TARGETS:
            _run_reload_group(tag, dependencies, False, original_files[tag])

        tag = "newthalos"
        deps = ("midgaard",)
        _run_reload_group(tag, deps, True, original_files[tag])
        _eviction_case(tag, deps, original_files[tag],
                       "pressure/newthalos/post_evict_baseline",
                       False, False)
        _eviction_case(tag, deps, original_files[tag],
                       "pressure/newthalos/pre_evict",
                       True, False)
        _eviction_case(tag, deps, original_files[tag],
                       "pressure/newthalos/pre_evict+shared_flags",
                       True, True)
        _checkpoint("DONE")
    except Exception as exc:
        failed = type(exc).__name__ + ": " + str(exc)
        _checkpoint("ERROR=" + failed)
    finally:
        world._loading_notice = original_notice
        for tag in original_files:
            world._TAG_TO_FILE[tag] = original_files[tag]

    if failed is None:
        game.tr.print("Area benchmark complete: " + LOG_FILE)
    else:
        game.tr.print("Area benchmark failed; partial log: " + LOG_FILE)
