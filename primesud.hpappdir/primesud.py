import math

from tml import tml
from hpprime import dimgrob, eval as ppleval, keyboard


class Game:
    """Holds game state and drives the main loop."""

    def __init__(self):
        # Text terminal: dark bg (0x3000), 8-space tabs
        self.tr = tml(dark_mode=True, tab_size=8, bg_color=0x3000)
        self.last_keys = set()  # keys held down in the previous frame
        self.config = {"tick_interval": 5000}

    def print(self, *args, **kwargs):
        self.tr.print(*args, **kwargs)

    @staticmethod
    def pressed_keys():
        """
        Return the set of currently pressed key bit-indices.

        Reads the calculator's keyboard bitmask via hpprime.keyboard() and
        converts each set bit into its zero-based index (0–63), which corresponds
        to a physical key on the HP Prime keyboard.

        Returns:
            set[int]: Bit indices of all keys currently held down.
        """
        state = keyboard()
        keys = set()
        while state:
            n = state & (-state)  # isolate lowest set bit
            keys.add(round(math.log2(n)))  # convert to bit index
            state &= state - 1  # clear lowest set bit
        return keys

    def game_loop(self):
        """
        Poll keyboard and advance game state on each tick.

        Runs indefinitely; exit via KeyboardInterrupt (On key).
        """
        t = int(ppleval("Ticks"))
        next_tick = t + self.config["tick_interval"]

        while True:
            # Diff against last frame to find new presses
            next_keys = self.pressed_keys()
            additions = list(next_keys - self.last_keys)
            deletions = list(self.last_keys - next_keys)
            if additions:
                self.print("New: {}, ({})".format(additions, list(next_keys)))
            self.last_keys = next_keys

            # Tick handling
            t = int(ppleval("Ticks"))
            if t >= next_tick:
                self.print("* TICK *")
                next_tick += self.config["tick_interval"]

            # Yield CPU for ~1 ms
            ppleval("WAIT(1/1e3)")


class PrimeSud:
    """
    Manages environment setup/teardown and top-level game flow.

    Environment pattern adapted from JezzBall 1.23 by Piotr Kowalewski (komame).
    """

    def __enter__(self):
        """
        Save calculator settings (AAngle, AFormat, AComplex, Bits, HSeparator),
        apply game-optimal values, and initialize the Game instance.
        """
        sep = ppleval("HSeparator")
        ppleval("HSeparator:=0")
        self.vars = tuple(ppleval("{AAngle,AFormat,AComplex,Bits}")) + (sep,)
        ppleval("AAngle:=1;AFormat:=1;AComplex:=0;Bits:=32")
        self.game = Game()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Clear graphic buffers and restore saved calculator settings.
        Suppresses KeyboardInterrupt so the On key exits cleanly.
        """
        for n in range(1, 9):
            dimgrob(n, 0, 0, 0)
        ppleval(
            "AAngle:=%d;AFormat:=%d;AComplex:=%d;Bits:=%d;HSeparator:=%d;TOff:=TOff"
            % self.vars
        )
        return exc_type is KeyboardInterrupt

    def run(self):
        """Entry point: run the game inside the environment context manager."""
        with self:
            game = self.game
            mode = 1

            game.print("Hello!")

            while mode != 0:
                game.game_loop()


PrimeSud().run()
