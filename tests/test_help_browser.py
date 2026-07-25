"""Tests for the [PRIMESUD] bare-`help` browser (info._help_browse)."""
import pytest

import info


PLAYER = {"level": 1}


@pytest.fixture
def out(monkeypatch):
    """Capture everything the browser prints, via chprintln and tpage."""
    lines = []
    monkeypatch.setattr(info, "chprintln",
                        lambda ch, s="": (lines.extend(s)
                                          if type(s) is list else lines.append(s)))
    monkeypatch.setattr(info, "tpage", lambda page: lines.extend(page))
    return lines


class _Picker:
    """Stub for picker.pick_from driven by a script of return values.

    Records (title, options, start_page) per call so the menus can be
    asserted on; a script entry of -1 is the player pressing Esc.
    """

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, title, options, start_page=0):
        self.calls.append((title, list(options), start_page))
        return self.script.pop(0) if self.script else -1


@pytest.fixture
def pick(monkeypatch):
    def install(*script):
        picker = _Picker(script)
        monkeypatch.setattr(info, "pick_from", picker)
        return picker
    return install


def test_category_menu_offers_summary_then_visible_categories(out, pick):
    picker = pick(-1)
    info.do_help(PLAYER, [])
    title, options, start_page = picker.calls[0]
    assert (title, start_page) == ("Help: pick a category", 0)
    assert options[0] == "summary (one-page command overview)"
    assert "commands (86 helps)" in options  # 87 total, BID is level 2
    assert "spells (76 helps)" in options
    # unported systems and the leftover plumbing entries all sit at level 51
    for hidden in ("immortal", "olc", "clan", "deities", "unknown"):
        assert not any(o.startswith(hidden) for o in options)
    # eight categories plus summary, well inside one picker page
    assert len(options) == 9


def test_higher_trust_sees_more_categories(out, pick):
    low = pick(-1)
    info.do_help(PLAYER, [])
    high = pick(-1)
    info.do_help({"level": 60}, [])
    assert len(high.calls[0][1]) > len(low.calls[0][1])


def test_cancelling_the_category_menu_prints_nothing(out, pick):
    pick(-1)
    info.do_help(PLAYER, [])
    assert out == []


def test_first_option_shows_the_stock_bare_help_summary(out, pick):
    pick(0, -1)  # pick summary, then Esc out of the menu
    info.do_help(PLAYER, [])
    assert any("MOVEMENT" in ln for ln in out)
    assert any("For more help, type 'help <topic>'" in ln for ln in out)


def test_picking_an_entry_shows_its_body_and_headers(out, pick):
    picker = pick(_category_choice("spells"), 0, -1, -1)
    info.do_help(PLAYER, [])
    assert picker.calls[1][0] == "Help: spells"
    keywords, _offsets = info._help_category_entries(PLAYER["level"], "spells")
    assert any(ln == "Help Keywords : %s" % keywords[0] for ln in out)
    assert any(ln == "Help Category : spells" for ln in out)


def test_entry_menu_reopens_on_the_page_of_the_last_pick(out, pick):
    picker = pick(_category_choice("commands"), 34, -1, -1)
    info.do_help(PLAYER, [])
    assert picker.calls[1][2] == 0     # opened at the first page
    assert picker.calls[2][2] == 3     # reopened where entry 34 lives


def test_entry_esc_returns_to_the_category_menu(out, pick):
    picker = pick(_category_choice("spells"), -1, -1)
    info.do_help(PLAYER, [])
    assert [c[0] for c in picker.calls] == [
        "Help: pick a category", "Help: spells", "Help: pick a category"]


def test_entry_labels_fit_one_terminal_row(out, pick):
    picker = pick(_category_choice("spells"), -1, -1)
    info.do_help(PLAYER, [])
    labels = picker.calls[1][1]
    assert max(len(l) for l in labels) <= info._HELP_LABEL_MAX
    # the longest keyword list is elided rather than dropped
    assert any(l.endswith("...") for l in labels)


def test_menu_order_matches_index_numbering(out, pick):
    picker = pick(_category_choice("spells"), 11, -1, -1)
    info.do_help(PLAYER, [])
    picked = "\n".join(out)
    del out[:]
    info.do_index(PLAYER, ["spells", "12"])  # menu is 0-based, index 1-based
    assert "\n".join(out) == picked


def test_keyword_argument_bypasses_the_browser(out, monkeypatch):
    monkeypatch.setattr(info, "pick_from",
                        lambda *a, **kw: pytest.fail("browser opened with args"))
    info.do_help(PLAYER, ["acid", "blast"])
    assert any("Help Keywords : 'ACID BLAST'" in ln for ln in out)


def test_single_letter_picker_opens_the_chosen_entry(out, pick):
    motd, = _letter_choices(pick, out, "m", "MOTD")
    picker = pick(motd, -1)
    info.do_help(PLAYER, ["m"])
    assert picker.calls[0][0] == "Help files starting with 'M'"
    assert any(ln == "Help Keywords : MOTD" for ln in out)
    # the letter list spans categories, so no category header line
    assert not any(ln.startswith("Help Category") for ln in out)


def test_single_letter_picker_loops_until_esc(out, pick):
    maps, motd = _letter_choices(pick, out, "m", "MAP MAPS", "MOTD")
    picker = pick(maps, motd, -1)
    info.do_help(PLAYER, ["m"])
    assert len(picker.calls) == 3      # two picks, then Esc
    assert any(ln == "Help Keywords : MAP MAPS" for ln in out)
    assert any(ln == "Help Keywords : MOTD" for ln in out)


def _letter_choices(pick, out, letter, *keywords):
    """Positions of keyword lists in the `help <letter>` picker.

    Runs the command once with an Esc-only picker to read the menu, then
    leaves the caller free to reinstall a real script via `pick`.
    """
    scout = pick(-1)
    info.do_help(PLAYER, [letter])
    options = scout.calls[0][1]
    del out[:]
    return [options.index(k) for k in keywords]


def _category_choice(name):
    """Index of a category in the browser's top-level menu (summary is 0)."""
    categories = info._help_visible_categories(PLAYER["level"])
    for i, (cat, _count) in enumerate(categories):
        if cat == name:
            return i + 1
    raise AssertionError("no visible category " + name)
