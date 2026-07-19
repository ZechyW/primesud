"""Random fantasy name generation (cf. 1stMud namegen.c).

[PRIMESUD] Ported for the chargen name picker and the rename command;
upstream exposes this as the imm `genname` list command and nanny.c
suggestions. Only the one stock profile ("mixed fantasy names",
init_name_profiles in namegen.c) exists upstream, so the profile layer
is dropped.
"""

from urandom import randint

# Syllable pools from init_name_profiles (namegen.c:56-70). Duplicate
# entries are intentional weighting; "_" in the suffix pool means "no
# suffix" (genname skips words starting with '_').
_PREFIX = ("A Ab Ac Ad Af Agr Ast As Al Adw Adr Ar B Br C C C Cr Ch Cad "
           "D Dr Dw Ed Eth Et Er El Eow F Fr G Gr Gw Gw Gal Gl H Ha Ib "
           "Jer K Ka Ked L Loth Lar Leg M Mir N Nyd Ol Oc On P Pr R Rh S "
           "Sev T Tr Th Th V Y Yb Z W W Wic")
_MIDDLE = ("a ae ae au ao are ale ali ay ardo e ei ea ea eri era ela eli "
           "enda erra i ia ie ire ira ila ili ira igo o oa oi oe ore u y")
_SUFFIX = ("_ _ _ _ _ _ a and b bwyn baen bard c ctred cred ch can d dan "
           "don der dric dfrid dus f g gord gan l li lgrin lin lith lath "
           "loth ld ldric ldan m mas mos mar mond n nydd nidd nnon nwan "
           "nyth nad nn nnor nd p r ron rd s sh seth sean t th th tha "
           "tlan trem tram v vudd w wan win win wyn wyn wyr wyr wyth")

_PARTS = [s.split() for s in (_PREFIX, _MIDDLE, _SUFFIX)]


def random_name():
    """Return one random capitalized name (cf. 1stMud genname in namegen.c).

    [PRIMESUD] upstream rolls number_range(0, part_count), which can index
    one past the pool (logged as a bugf and the syllable dropped); rolled
    in-range here. Result capped at 12 characters, the chargen name limit
    (every prefix syllable is already capitalized, so no capitalize call).
    """
    out = ""
    for pool in _PARTS:
        syl = pool[randint(0, len(pool) - 1)]
        if syl != "_":
            out = out + syl
    return out[:12]
