"""MWE: HP Prime list-comprehension + nested dict + .format() string corruption.

Hypothesis: .format() inside a list comprehension with nested dict lookups
corrupts the first byte of some result strings to \x00 on physical HP Prime
hardware. Standalone .format() with identical args is clean.

Observed: entry 5 ("parry") produced '\x00arry (35%)' -- first byte zeroed,
rest of string intact. Consistent with heap write-before-allocation or buffer
underwrite triggered by memory pressure during comprehension evaluation.

Run standalone on physical HP Prime (not via game). Raw print() goes to Python
terminal, bypassing colour parsing. Expected clean output: all [0]= match the
ord of the first character of each skill name. Bug: [0]=0 on some entries.
"""

# Mimics SKILLS and player["learned"] shapes from PrimeSUD
_skills = {
    101: {"name": "recall"},
    102: {"name": "wands"},
    103: {"name": "bash"},
    104: {"name": "dodge"},
    105: {"name": "parry"},
    106: {"name": "shield block"},
    107: {"name": "second attack"},
    108: {"name": "third attack"},
    109: {"name": "hand to hand"},
    110: {"name": "kick"},
}

_learned = {101: 50, 102: 1, 103: 25, 104: 40, 105: 35,
            106: 20, 107: 15, 108: 10, 109: 75, 110: 60}


def run_mwe():
    # Control: standalone .format() -- expected clean
    ctrl = "{} ({}%)".format("recall", 50)
    print("ctrl[0]=" + str(ord(ctrl[0])) + " (expect 114)")

    # Test 1: comprehension with nested dict lookup + .format()
    # Bug observed: some entries get first byte zeroed to \x00
    names_fmt = ["{} ({}%)".format(_skills[k]["name"], v)
                 for k, v in _learned.items()]
    print("--- fmt comprehension ---")
    for i, (k, n) in enumerate(zip(_learned.keys(), names_fmt)):
        o = ord(n[0])
        expected = ord(_skills[k]["name"][0])
        flag = " BUG(got=" + str(o) + " want=" + str(expected) + ")" if o != expected else ""
        print(str(i) + ": " + repr(n[:8]) + flag)

    # Test 2: str() concat comprehension -- expected clean
    names_cat = [str(_skills[k]["name"]) + " (" + str(v) + "%)"
                 for k, v in _learned.items()]
    print("--- cat comprehension ---")
    for i, (k, n) in enumerate(zip(_learned.keys(), names_cat)):
        o = ord(n[0])
        expected = ord(_skills[k]["name"][0])
        flag = " BUG(got=" + str(o) + " want=" + str(expected) + ")" if o != expected else ""
        print(str(i) + ": " + repr(n[:8]) + flag)


run_mwe()
