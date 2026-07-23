"""Unit tests for tools/are_to_primesud.py (ROM 2.4 .are converter).

Feeds synthetic .are text through convert() and execs the emitted Python
to check the data, plus fail-loud coverage for the constructs QuickMUD's
loader bug()+exit(1)s on. [PRIMESUD]
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import are_to_primesud as conv


AREA_HEADER = """#AREA
test.are~
Test Area~
{ 1 10} Test  Test Area~
8000 8099

"""

# Minimal valid new-format mob (layout cribbed from areas/school.are #3700).
MOB_8000 = """#8000
guard test~
the test guard~
A test guard stands here.
~
He looks bored.
~
human~
AB 0 1000 0
10 5 1d1+99 1d1+49 2d4+3 beating
-5 -5 -5 -5
0 0 0 0
stand stand male 100
0 0 medium 0
"""


def convert_str(tmp_path, body):
    """Wrap body in an #AREA header + #$, convert, exec, return namespace."""
    are = tmp_path / "test.are"
    are.write_text(AREA_HEADER + body + "#$\n")
    code = conv.convert(str(are), str(tmp_path / "out.txt"))
    ns = {}
    exec(code, ns)
    return ns


class TestHappyPath:
    def test_shipped_midgaard_object_and_room_programs(self, tmp_path):
        root = Path(__file__).resolve().parents[1]
        code = conv.convert(
            str(root / "areas" / "midgaard.are"),
            str(tmp_path / "area_midgaard.txt"),
        )
        ns = {}
        exec(code, ns)

        assert ns["OBJECTS"][3005]["obj_triggers"] == (("drop", 3005, "100"),)
        assert ns["ROOMS"][3054]["room_triggers"] == (("grall", 3054, "100"),)
        assert ns["OBJPROGS"][3005] == "obj echo Don't drop me!"
        assert ns["ROOMPROGS"][3054] == (
            "room echo {`You enter a room of sanctuary and peace.{x"
        )

    def test_two_line_f_trailer_and_a_trailer(self, tmp_path):
        # The shipped One Ring bug: F alone on one line, payload on the
        # next (areas/shire.are #1105); A-trailer payload on its own line.
        ns = convert_str(tmp_path, """#OBJECTS
#8012
ring test~
a test ring~
A test ring is here.~
gold~
jewelry G AB
0 0 0 0 0
20 30 1660 P
F
A 0 0 B
A
1 -1
#0
""")
        obj = ns["OBJECTS"][8012]
        assert obj["stat_bonuses"] == {"str": -1}
        assert obj["flag_affects"] == (("affects", "0", 0, {"invisible": True}),)

    def test_values_fallback_for_undecoded_item_type(self, tmp_path):
        # db2.c default: branch reads all 5 values via fread_flag; letter
        # forms legal (AH = bits 0+7 = 129).
        ns = convert_str(tmp_path, """#OBJECTS
#8011
bed test~
a test bed~
A test bed is here.~
wood~
furniture 0 0
9 0 AH 0 0
1 100 0 P
#0
""")
        assert ns["OBJECTS"][8011]["values"] == (9, 0, 129, 0, 0)

    def test_all_zero_values_omitted(self, tmp_path):
        ns = convert_str(tmp_path, """#OBJECTS
#8013
rock test~
a test rock~
A test rock is here.~
stone~
trash 0 A
0 0 0 0 0
1 10 0 P
#0
""")
        assert "values" not in ns["OBJECTS"][8013]

    def test_spec_and_shop_baked_case_insensitive(self, tmp_path):
        # spec_lookup matches case-insensitively; canonical spelling baked.
        ns = convert_str(tmp_path, MOB_HEADER_WRAP + """#SHOPS
8000 0 0 0 0 0 	 150 50 	 0 23
0
#SPECIALS
M 8000 SPEC_CAST_MAGE
S
""")
        mob = ns["MOBILES"][8000]
        assert mob["spec_fun"] == "spec_cast_mage"
        assert mob["shop"]["profit_buy"] == 150

    def test_mob_f_trailer_two_line(self, tmp_path):
        ns = convert_str(tmp_path, "#MOBILES\n" + MOB_8000 + """F
res S
#0
""")
        assert ns["MOBILES"][8000].get("flag_removes")

    def test_mob_trigger_multi_line_phrase(self, tmp_path):
        # db2.c reads the trig phrase via fread_string: full multi-line
        # tilde string.
        ns = convert_str(tmp_path, "#MOBILES\n" + MOB_8000 + """M speech 8050 hello
there~
#0
""")
        trig = ns["MOBILES"][8000]["mob_triggers"][0]
        assert tuple(trig) == ("speech", 8050, "hello\nthere")

    def test_optional_pet_evolution_trailer(self, tmp_path):
        ns = convert_str(tmp_path, "#MOBILES\n" + MOB_8000 + "E 8001\n#0\n")
        assert ns["MOBILES"][8000]["evolves_to"] == 8001

    def test_object_and_room_program_data(self, tmp_path):
        ns = convert_str(tmp_path, """#OBJECTS
#8010
bell test~
a test bell~
A test bell is here.~
brass~
treasure 0 A
0 0 0 0 0
1 10 0 P
O DROP 8050 100~
#0

#ROOMS
#8020
Test Room~
A bare test room.
~
0 0 0
R GRALL 8060 100~
S
#0

#OBJPROGS
#8050
obj echo Don't drop me!
~
#0

#ROOMPROGS
#8060
room echo Peace and quiet.
~
#0
""")
        assert ns["OBJECTS"][8010]["obj_triggers"] == (("drop", 8050, "100"),)
        assert ns["ROOMS"][8020]["room_triggers"] == (("grall", 8060, "100"),)
        assert ns["OBJPROGS"][8050] == "obj echo Don't drop me!"
        assert ns["ROOMPROGS"][8060] == "room echo Peace and quiet."


MOB_HEADER_WRAP = "#MOBILES\n" + MOB_8000 + "#0\n"


class TestFailLoud:
    def check_raises(self, tmp_path, body, match=None):
        with pytest.raises(ValueError, match=match):
            convert_str(tmp_path, body)

    def test_unknown_section(self, tmp_path):
        self.check_raises(tmp_path, "#FROBNICATE\njunk\n", "unknown section")

    def test_areadata_rejected(self, tmp_path):
        self.check_raises(tmp_path, "#AREADATA\nName Test~\nEnd\n",
                          "AREADATA")

    def test_mobold_rejected(self, tmp_path):
        self.check_raises(tmp_path, "#MOBOLD\n#0\n", "MOBOLD")

    def test_unknown_spec_fun(self, tmp_path):
        self.check_raises(
            tmp_path,
            MOB_HEADER_WRAP + "#SPECIALS\nM 8000 spec_bogus\nS\n",
            "not an implemented spec_fun")

    def test_specials_bad_letter(self, tmp_path):
        self.check_raises(
            tmp_path,
            MOB_HEADER_WRAP + "#SPECIALS\nX 1 2\nS\n",
            "unrecognized command letter")

    def test_room_bad_trailer_letter(self, tmp_path):
        self.check_raises(tmp_path, """#ROOMS
#8020
Test Room~
A bare test room.
~
0 0 0
Z 5
S
#0
""", "trailer letter")

    def test_reset_bad_letter(self, tmp_path):
        self.check_raises(tmp_path, "#RESETS\nQ 0 1 2\nS\n",
                          "unrecognized command letter")

    @pytest.mark.parametrize("reset", (
        "M 0 9000 1 9000 1",
        "O 0 9000 1 9000",
        "R 0 9000 4",
        "D 0 9000 0 1",
    ))
    def test_reset_cannot_target_foreign_room(self, tmp_path, reset):
        self.check_raises(tmp_path, """#ROOMS
#8020
Test Room~
A bare test room.
~
0 0 0
S
#0
#RESETS
""" + reset + "\nS\n", "outside this file's ROOMS section")

    def test_reset_can_pull_foreign_template_into_local_room(self, tmp_path):
        ns = convert_str(tmp_path, """#ROOMS
#8020
Test Room~
A bare test room.
~
0 0 0
S
#0
#RESETS
M 0 9000 1 8020 1
O 0 9001 1 8020
S
""")
        assert ns["RESETS"] == (("M", 9000, 1, 8020, 1),
                                ("O", 9001, 8020))

    def test_object_f_bad_where_letter(self, tmp_path):
        self.check_raises(tmp_path, """#OBJECTS
#8014
amulet test~
a test amulet~
A test amulet is here.~
gold~
jewelry 0 A
0 0 0 0 0
1 10 0 P
F
X 0 0 B
#0
""", "where-letter")

    def test_object_a_trailer_truncated(self, tmp_path):
        # Bare A with no payload before end of entry: must raise, never
        # silently swallow + desync (any ValueError acceptable).
        self.check_raises(tmp_path, """#OBJECTS
#8015
amulet test~
a test amulet~
A test amulet is here.~
gold~
jewelry 0 A
0 0 0 0 0
1 10 0 P
A
#0
""")

    def test_mob_invalid_trigger_type(self, tmp_path):
        self.check_raises(
            tmp_path,
            "#MOBILES\n" + MOB_8000 + "M bogus 1 x~\n#0\n",
            "invalid trigger type")

    def test_object_invalid_trigger_type(self, tmp_path):
        self.check_raises(tmp_path, """#OBJECTS
#8010
bell test~
a test bell~
A test bell is here.~
brass~
treasure 0 A
0 0 0 0 0
1 10 0 P
O BOGUS 8050 100~
#0
""", "invalid trigger type")

    def test_room_invalid_trigger_type(self, tmp_path):
        self.check_raises(tmp_path, """#ROOMS
#8020
Test Room~
A bare test room.
~
0 0 0
R BOGUS 8060 100~
S
#0
""", "invalid trigger type")
