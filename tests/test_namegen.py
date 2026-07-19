"""Namegen fidelity tests (cf. 1stMud namegen.c syllable pools + genname)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import namegen


def test_pool_sizes_match_upstream():
    # word counts of init_name_profiles part[0..2] (namegen.c:56-70)
    assert [len(p) for p in namegen._PARTS] == [72, 36, 79]


def test_underscore_suffix_dropped(monkeypatch):
    monkeypatch.setattr(namegen, "randint", lambda a, b: 0)
    assert namegen.random_name() == "Aa"  # prefix "A" + middle "a" + "_" skipped


def test_names_are_valid_chargen_names():
    # any generated name must pass the chargen rules: 2-12 ASCII letters,
    # capitalized (longest possible concat is 13 chars -> the [:12] cap)
    for _ in range(300):
        n = namegen.random_name()
        assert 2 <= len(n) <= 12
        assert n[0].isupper() and n.isalpha()


# -- _prompt_name / do_rename branch logic (game_state.py) --------------------

import game_state


class TestPromptName:
    def _patch(self, monkeypatch, picks, gen=None, typed=None):
        """Drive pick_from/random_name/tr.input from canned sequences."""
        pick_seq = list(picks)
        monkeypatch.setattr(game_state, "pick_from",
                            lambda title, opts: pick_seq.pop(0))
        self.gen_calls = 0
        gen = gen or [chr(ord("A") + i) + "x" for i in range(20)]

        def fake_gen():
            self.gen_calls += 1
            return gen[self.gen_calls - 1]
        monkeypatch.setattr(namegen, "random_name", fake_gen)
        if typed is not None:
            typed_seq = list(typed)

            class _FakeTr:
                def input(self, prompt, default=None):
                    return typed_seq.pop(0)

                def print(self, *a, **k):
                    pass  # pc_shim tprint routes here for "Illegal name"
            monkeypatch.setattr(game_state.terminal, "tr", _FakeTr())

    def test_pick_returns_generated(self, monkeypatch):
        self._patch(monkeypatch, picks=[2])
        assert game_state._prompt_name() == "Cx"
        assert self.gen_calls == 6

    def test_esc_reshows_same_names(self, monkeypatch):
        # chargen: Esc is a no-op re-show -- no reroll, no typed entry
        self._patch(monkeypatch, picks=[-1, 0])
        assert game_state._prompt_name() == "Ax"
        assert self.gen_calls == 6

    def test_esc_cancels_when_allowed(self, monkeypatch):
        self._patch(monkeypatch, picks=[-1])
        assert game_state._prompt_name(allow_cancel=True) is None

    def test_more_names_rerolls(self, monkeypatch):
        self._patch(monkeypatch, picks=[6, 0])
        assert game_state._prompt_name() == "Gx"  # 7th generated
        assert self.gen_calls == 12

    def test_type_my_own_reprompts_illegal(self, monkeypatch):
        self._patch(monkeypatch, picks=[7], typed=["!!", "bob"])
        assert game_state._prompt_name() == "Bob"


class TestDoRename:
    def _msgs(self, monkeypatch):
        out = []
        monkeypatch.setattr(game_state, "chprintln",
                            lambda ch, msg: out.append(msg))
        return out

    def test_direct_arg(self, monkeypatch):
        out = self._msgs(monkeypatch)
        ch = {"name": "Hero"}
        game_state.do_rename(ch, ["bob"])
        assert ch["name"] == "Bob"
        assert out == ["You are now known as Bob."]

    def test_illegal_arg_unchanged(self, monkeypatch):
        out = self._msgs(monkeypatch)
        ch = {"name": "Hero"}
        game_state.do_rename(ch, ["x!"])
        assert ch["name"] == "Hero"
        assert out == ["Illegal name, try another."]

    def test_no_arg_picker_cancel(self, monkeypatch):
        out = self._msgs(monkeypatch)
        monkeypatch.setattr(game_state, "_prompt_name",
                            lambda default=None, allow_cancel=False: None)
        ch = {"name": "Hero"}
        game_state.do_rename(ch, [])
        assert ch["name"] == "Hero" and out == []
