import math

from tml import tml
from hpprime import dimgrob, eval as ppleval, keyboard


class Game:
    """
    Main game class
    """

    def __init__(self):
        # Terminal setup
        self.tr = tml(dark_mode=True, tab_size=8, bg_color=0x3000)
        # Keyboard handling
        self.last_keys = set()
        # Config
        self.config = {"tick_interval": 5000}

    def print(self, *args, **kwargs):
        self.tr.print(*args, **kwargs)

    @staticmethod
    def pressed_keys():
        state = keyboard()
        keys = set()
        while state:
            n = state & (-state)  # isolate lowest set bit
            keys.add(round(math.log2(n)))  # convert to bit index
            state &= state - 1  # clear lowest set bit
        return keys

    def game_loop(self):
        # Handles main gameplay loop using internal millisecond clock as timer
        t = int(ppleval("Ticks"))
        next_tick = t + self.config["tick_interval"]

        while True:
            # Check for keyboard presses
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

            # General wait
            ppleval("WAIT(1/1e3)")


class PrimeSud:
    """
    Main entry point class that manages game execution, handles environment
    setup/teardown, and controls the game flow between title screen and gameplay.

    Copied from JezzBall 1.23, Piotr Kowalewski (komame)
    """

    def __enter__(self):
        """
        Set up the game environment, save current calculator settings,
        configure optimal settings for the game, and initialize the Game instance.

        Returns:
            self: The overall app instance for context manager usage.
        """
        sep = ppleval("HSeparator")
        ppleval("HSeparator:=0")
        self.vars = tuple(ppleval("{AAngle,AFormat,AComplex,Bits}")) + (sep,)
        ppleval("AAngle:=1;AFormat:=1;AComplex:=0;Bits:=32")
        self.game = Game()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        This method is automatically called when exiting the game.

        It saves the high scores, clears graphic buffers, and restores
        previously saved calculator settings.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.

        Returns:
            bool | None: True if KeyboardInterrupt should be suppressed, otherwise None.
        """
        # self.game.save_highscore()
        for n in range(1, 9):
            dimgrob(n, 0, 0, 0)
        ppleval(
            "AAngle:=%d;AFormat:=%d;AComplex:=%d;Bits:=%d;HSeparator:=%d;TOff:=TOff"
            % self.vars
        )
        return exc_type is KeyboardInterrupt

    def run(self):
        """
        Main game execution method that creates the context manager,
        initializes title assets, and manages the game flow between
        title screen and gameplay until the player exits the game.
        """
        with self:
            game = self.game
            mode = 1

            game.print("Hello!")

            while mode != 0:
                game.game_loop()


PrimeSud().run()
