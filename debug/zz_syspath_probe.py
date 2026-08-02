"""Coup-de-grace probe for the .mpy track: import machinery anatomy. [PRIMESUD]

zz_mpy_probe got ImportError "no module named" (not ValueError
"incompatible .mpy"), so the importer never stat'ed the .mpy file.
This probe closes the question for good:

  1. sys.path contents (is there a path list to influence at all?)
  2. uos presence + getcwd/listdir (stock VFS or HP custom hook?)
  3. open("mpytoy.mpy", "rb") -- file visible to userland I/O?
  4. control: runtime-write mpytoy3.py, import it. If a .py written
     at runtime imports, the importer scans the filesystem dynamically
     and the .mpy failure is extension-specific, not manifest-based.
  5. retry __import__("mpytoy") after each sys.path tweak ("", ".",
     "/", cwd). Any success = .mpy track alive after all.

Ships with mpytoy.mpy/mpytoy2.mpy already in the appdir. One
self-running .py rule: swap in FOR zz_mpy_probe.py. No primesud.py.
Results printed and written to zz_syspath_probe.log.
"""

LOG = "zz_syspath_probe.log"
_out = []


def log(msg):
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


def try_import(name, note):
    try:
        m = __import__(name)
        log(".. import " + name + " OK (" + note + ") "
            + repr(getattr(m, "MPYTOY_OK", None)))
        return True
    except Exception as exc:
        log(".. import " + name + " FAILED (" + note + ") " + repr(exc))
        return False


def main():
    log("zz_syspath_probe: import machinery anatomy")

    # 1. sys.path
    try:
        import sys
        log("sys.path: " + repr(getattr(sys, "path", "ABSENT")))
    except Exception as exc:
        log("sys import FAILED " + repr(exc))
        sys = None

    # 2. uos / os
    for osname in ("uos", "os"):
        try:
            u = __import__(osname)
            log(osname + ": present, dir: " + repr(dir(u)))
            try:
                log(osname + ".getcwd(): " + repr(u.getcwd()))
            except Exception as exc:
                log(osname + ".getcwd FAILED " + repr(exc))
            try:
                log(osname + ".listdir(): " + repr(u.listdir()))
            except Exception as exc:
                log(osname + ".listdir FAILED " + repr(exc))
            break
        except ImportError:
            log(osname + ": absent")

    # 3. .mpy visible to plain I/O?
    try:
        with open("mpytoy.mpy", "rb") as f:
            head = f.read(4)
        log("open mpytoy.mpy OK, head: " + repr(head))
    except Exception as exc:
        log("open mpytoy.mpy FAILED " + repr(exc))

    # 4. control: runtime-written .py
    try:
        with open("mpytoy3.py", "w") as f:
            f.write("MPYTOY_OK = 777\n")
        log("wrote mpytoy3.py")
    except Exception as exc:
        log("write mpytoy3.py FAILED " + repr(exc))
    py_ok = try_import("mpytoy3", "runtime-written .py")

    # 5. .mpy retries under path tweaks
    mpy_ok = try_import("mpytoy", "baseline")
    if not mpy_ok and sys is not None and hasattr(sys, "path"):
        for p in ("", ".", "/"):
            try:
                sys.path.append(p)
                mpy_ok = try_import("mpytoy", "sys.path + " + repr(p))
                if mpy_ok:
                    break
            except Exception as exc:
                log(".. path tweak " + repr(p) + " FAILED " + repr(exc))

    if mpy_ok:
        log("VERDICT: .mpy ALIVE -- a path tweak reaches the loader")
    elif py_ok:
        log("VERDICT: .mpy DEAD, extension-specific -- importer scans fs"
            + " dynamically but only tries .py. Track closed.")
    else:
        log("VERDICT: .mpy DEAD -- importer opaque (runtime .py also"
            + " invisible). Track closed.")
    log("Done. Results in " + LOG)


main()
