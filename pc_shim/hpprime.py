"""HP Prime hpprime module stub for PC debugging."""
import time


def eval(expr):
    if expr.startswith("WAIT("):
        try:
            time.sleep(float(expr[5:-1]))
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
