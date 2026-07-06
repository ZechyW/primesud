"""HP Prime hpprime module stub for PC debugging."""
import builtins
import time


def eval(expr):
    if expr == "GETKEY":
        return -1  # empty firmware key queue (see src/tml_prime.py pump)
    if expr.startswith("WAIT("):
        # Arg may be an expression like "1/1e3", not just a float literal
        # (float() on it raised, silently skipping the sleep -> busy wait).
        try:
            time.sleep(builtins.eval(expr[5:-1]))
        except Exception:
            pass
    return 0


def keyboard(): return 0
def mouse(): return [(-1, 0, 0)]
def dimgrob(*a): pass
def strblit2(*a): pass
def fillrect(*a): pass
def rect(*a): pass
def pixon(*a): pass
def grobw(*a): return 0
def grobh(*a): return 0
def getpix(*a): return 0
