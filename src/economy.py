"""Solo-relevant 1stMud bank and shares economy."""

import world
from game_time import time_info
from handler import chprintln
from urandom import randint
from world import ROOM_DEFS

MAX_SHARES = 10000
MAX_GOLD = 99999999


def do_balance(ch, args):
    """Display bank, carried money, and shares (cf. 1stMud do_balance in economy.c)."""
    chprintln(ch, "Balance : " + str(ch["gold_bank"]) + " gold")
    chprintln(ch, "On Hand : " + str(ch["gold"]) + " gold, " + str(ch["silver"]) + " silver")
    chprintln(ch, "Shares  : " + str(ch["shares"] * world.share_value)
              + " gold in " + str(ch["shares"]) + " shares")


def _syntax(ch):
    chprintln(ch, "Syntax: bank balance")
    chprintln(ch, "        bank deposit <amount|all>")
    chprintln(ch, "        bank withdraw <amount|all>")
    chprintln(ch, "        bank buy <amount|all>")
    chprintln(ch, "        bank sell <amount|all>")
    chprintln(ch, "        bank check")


def _amount(raw, all_value):
    if raw == "all":
        return all_value
    number = 0
    pos = 0
    while pos < len(raw) and raw[pos].isdigit():
        number = number * 10 + int(raw[pos])
        pos += 1
    multiplier = 1
    if pos < len(raw) and raw[pos] in "km":
        multiplier = 1000 if raw[pos] == "k" else 1000000
        number *= multiplier
        pos += 1
    while pos < len(raw) and raw[pos].isdigit() and multiplier > 1:
        multiplier //= 10
        number += int(raw[pos]) * multiplier
        pos += 1
    if pos != len(raw):
        return 0
    return number


def _atoi(raw):
    """Parse a decimal prefix like C atoi (cf. 1stMud do_bank in economy.c)."""
    sign = 1
    pos = 0
    if raw and raw[0] in "+-":
        sign = -1 if raw[0] == "-" else 1
        pos = 1
    number = 0
    found = False
    while pos < len(raw) and raw[pos].isdigit():
        number = number * 10 + int(raw[pos])
        pos += 1
        found = True
    return sign * number if found else 0


def do_bank(ch, args):
    """Use banked gold and shares (cf. 1stMud do_bank in economy.c).

    [PRIMESUD] Clan banking and player transfer are multiplayer-only and
    omitted. Personal deposits accept gold-equivalent silver and enforce
    balance caps; see docs/FIXES.md.
    """
    if not ROOM_DEFS[ch["room"]].get("flags", {}).get("bank"):
        chprintln(ch, "You can't do that here.")
        return
    # [PRIMESUD] Upstream uses >20, leaving the "to 8pm" bank open until 9pm.
    if time_info["hour"] < 4 or time_info["hour"] >= 20:
        chprintln(ch, "The bank is closed, it is open from 4am to 8pm.")
        return
    if not args:
        _syntax(ch)
        return

    raw_op = args[0].lower()
    op = ""
    for name in ("balance", "deposit", "withdraw", "buy", "sell", "check"):
        if name.startswith(raw_op):
            op = name
            break
    if op == "balance":
        do_balance(ch, [])
        return
    if op == "check":
        chprintln(ch, "The current shareprice is " + str(world.share_value) + ".")
        if ch["shares"]:
            chprintln(ch, "You currently have " + str(ch["shares"]) + " shares, ("
                      + str(world.share_value) + " a share) worth a total of "
                      + str(ch["shares"] * world.share_value) + " gold.")
        return
    if len(args) < 2:
        prompts = {"deposit": "Deposit how much?", "withdraw": "Withdraw how much?",
                   "buy": "Buy how many?", "sell": "Sell how many shares?"}
        if op in prompts:
            chprintln(ch, prompts[op])
        else:
            _syntax(ch)
        return

    raw = args[1].lower()
    if op == "deposit":
        # [PRIMESUD] Bank stores whole gold; "all" leaves sub-gold silver.
        amount = _amount(raw, (ch["gold"] * 100 + ch["silver"]) // 100)
        cost = amount * 100
        from shop import check_worth, deduct_cost
        if not check_worth(ch, cost):
            chprintln(ch, "How can you deposit " + str(amount)
                      + " gold when you only have " + str(ch["gold"]) + " gold, "
                      + str(ch["silver"]) + " silver?")
            return
        if amount <= 0:
            chprintln(ch, "Only positive figures are allowed.")
            return
        if ch["gold_bank"] + amount > MAX_GOLD:
            chprintln(ch, "I'm sorry, our accounts can only hold up to "
                      + str(MAX_GOLD) + " gold!")
            return
        deduct_cost(ch, cost)
        ch["gold_bank"] = max(0, ch["gold_bank"] + amount)
        chprintln(ch, "You deposit " + str(amount) + " gold.  Your new balance is "
                  + str(ch["gold_bank"]) + " gold.")
    elif op == "withdraw":
        amount = _amount(raw, ch["gold_bank"])
        if ch["gold_bank"] < amount:
            chprintln(ch, "How can you withdraw " + str(amount)
                      + " gold when your balance is " + str(ch["gold_bank"]) + " gold?")
            return
        if amount <= 0:
            chprintln(ch, "Only positive figures are allowed.")
            return
        if ch["gold"] + amount > MAX_GOLD:
            chprintln(ch, "I'm sorry you can only carry " + str(MAX_GOLD) + " gold!")
            return
        ch["gold_bank"] = max(0, ch["gold_bank"] - amount)
        ch["gold"] = min(MAX_GOLD, ch["gold"] + amount)
        chprintln(ch, "You withdraw " + str(amount) + " gold.  Your new balance is "
                  + str(ch["gold_bank"]) + " gold.")
    elif op == "buy":
        shares = MAX_SHARES - ch["shares"] if raw == "all" else _atoi(raw)
        if ch["shares"] + shares > MAX_SHARES:
            chprintln(ch, "You can't buy more than " + str(MAX_SHARES) + " shares.")
            return
        cost = shares * world.share_value
        if cost > ch["gold_bank"]:
            chprintln(ch, str(shares) + " shares will cost you " + str(cost)
                      + ", deposit more money.")
            return
        if shares <= 0:
            chprintln(ch, "If you want to sell shares you have to say so...")
            return
        ch["gold_bank"] = max(0, ch["gold_bank"] - cost)
        ch["shares"] = min(MAX_SHARES, ch["shares"] + shares)
        chprintln(ch, "You buy " + str(shares) + " shares for " + str(cost)
                  + " gold, you now have " + str(ch["shares"]) + " shares.")
    elif op == "sell":
        shares = ch["shares"] if raw == "all" else _atoi(raw)
        if shares > ch["shares"]:
            chprintln(ch, "You only have " + str(ch["shares"]) + " shares.")
            return
        if shares <= 0:
            chprintln(ch, "If you want to buy shares you have to say so...")
            return
        value = shares * world.share_value
        # [PRIMESUD] Upstream caps the credit but still consumes every share.
        if ch["gold_bank"] + value > MAX_GOLD:
            chprintln(ch, "I'm sorry, your account can't hold that much gold!")
            return
        ch["gold_bank"] = max(0, ch["gold_bank"] + value)
        ch["shares"] = max(0, ch["shares"] - shares)
        chprintln(ch, "You sell " + str(shares) + " shares for " + str(value)
                  + " gold, you now have " + str(ch["shares"]) + " shares.")
    else:
        _syntax(ch)
        return
    world.save_pending = True


def bank_update():
    """Move share price per daytime area pulse (cf. 1stMud bank_update in update.c)."""
    if time_info["hour"] < 6 or time_info["hour"] > 18:
        return
    value = randint(0, 200) - 100
    value = value // 10 if value >= 0 else -((-value) // 10)
    world.share_value = max(10, min(world.share_value + value, 1000))
