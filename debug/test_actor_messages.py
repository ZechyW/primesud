import os
import sys


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "primesud.hpappdir"))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import actor
import world


def main():
    seen = []
    old_print = actor.tprint
    old_chars = world.chars
    try:
        actor.tprint = lambda msg: seen.append(msg)
        player = {"id": 1, "room": 100, "name": "Player", "pos": "standing"}
        mob = {"id": 2, "room": 100, "name": "a goblin", "is_npc": True, "sex": "male", "pos": "standing"}
        other = {"id": 3, "room": 100, "name": "Victim", "pos": "standing"}
        world.chars = {1: player, 2: mob, 3: other}

        actor.act("you hit it", ch=player, arg2=mob, type=actor.TO_CHAR)
        assert seen == ["You hit it"]

        seen[:] = []
        actor.act("$n hits you", mob, None, player, actor.TO_VICT)
        assert seen == ["A goblin hits you"]

        seen[:] = []
        actor.act("$n snarls", mob, None, other, actor.TO_ROOM)
        assert seen == ["A goblin snarls"]

        seen[:] = []
        actor.act("$n bites $N", mob, None, player, actor.TO_NOTVICT)
        assert seen == []

        seen[:] = []
        actor.act("You rescue $N.", player, None, other, actor.TO_CHAR)
        assert seen == ["You rescue Victim."]

        seen[:] = []
        actor.act("$n kicks dirt in your eyes!", other, None, player, actor.TO_VICT)
        assert seen == ["Victim kicks dirt in your eyes!"]

        seen[:] = []
        assert actor.chprint(player, "direct-noformat") == 1
        assert actor.chprint(mob, "skip-noformat") == 0
        assert seen == ["direct-noformat"]

        seen[:] = []
        actor.chprintln(player, "direct")
        actor.chprintln(mob, "skip")
        assert seen == ["direct"]

        seen[:] = []
        assert actor.chprintf(player, "hp: %d", 7) == 1
        assert actor.chprintf(mob, "hp: %d", 9) == 0
        assert seen == ["hp: 7"]

        seen[:] = []
        assert actor.chprintlnf(player, "%s %d", "lvl", 3) == 1
        assert actor.chprintlnf(player, None) == 1
        assert seen == ["lvl 3", ""]
    finally:
        actor.tprint = old_print
        world.chars = old_chars


if __name__ == "__main__":
    main()
