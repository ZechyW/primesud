"""Command dispatcher, command table, and position gates (cf. 1stMud interpret in interp.c)."""

from combat import (do_kill, do_kick, do_backstab, do_murder, do_suicide,
                    do_berserk, do_bash, do_dirt, do_trip, do_flee,
                    do_rescue, do_disarm, do_surrender,
                    do_sskill, do_stance, do_autostance, do_consider)
from comm import (do_say, do_tell, do_reply, do_follow, do_ditch, do_order,
                  do_yell, do_emote)
from config import POS_ORDER
from info import (do_look, do_examine, do_read, do_score, do_skills, do_spells,
                  do_help, do_affects, do_credits, do_areas, do_map, do_automap,
                  do_autolist, do_autoloot, do_autogold, do_autosac,
                  do_autosplit, do_autoassist, do_autoexit, do_autodamage,
                  do_wimpy, do_exits, do_worth, do_where, do_clear,
                  do_time, do_weather)
from inventory import (do_get, do_drop, do_inventory, do_wear, do_remove,
                       do_equipment, do_second, do_quaff, do_recite,
                       do_brandish, do_zap, do_eat, do_outfit, do_put,
                       do_sacrifice, do_compare, do_steal, do_give,
                       do_drink, do_fill, do_pour, do_envenom)
from explored import do_explored, mark_explored
from gquest import do_gquest
from handler import chprintln
from healer import do_heal
from hunt import do_hunt
from macros import do_macro
from magic import do_cast
from quest import do_quest, do_tpspend
from movement import (do_north, do_east, do_south, do_west, do_up, do_down,
                      do_open, do_close, do_recall, do_run,
                      do_stand, do_rest, do_sit, do_sleep, do_wake,
                      do_lock, do_unlock, do_pick,
                      do_hide, do_sneak, do_visible, do_enter)
from scan import do_scan
from shop import do_buy, do_sell, do_list, do_value, do_appraise
from system_cmds import do_save, do_quit
from debug import do_debug
from pager import tpage
from terminal import tprint
from training import do_train, do_practice, do_remort, do_gain
from urandom import randint

_POS_MSG = {
    "dead":     "Lie still; you are DEAD.",
    "mortal":   "You are hurt far too bad for that.",
    "incap":    "You are hurt far too bad for that.",
    "stunned":  "You are too stunned to do that.",
    "sleeping": "In your dreams, or what?",
    "resting":  "Nah... You feel too relaxed...",
    "sitting":  "Better stand up first.",
    "fighting": "No way!  You are still fighting!",
}

CMD_DESC_FILE = "commands.txt"  # [PRIMESUD] name|description per line


def do_commands(player, args):
    """List all available commands with brief descriptions (cf. 1stMud do_commands in interp.c).

    [PRIMESUD] 1stMud prints a bare 4-column name list; here each command
    gets a one-line description, read from commands.txt at display time
    (kept off-heap, cf. help.txt) and shown through the tpage pager.
    Category filter not ported -- no cmd categories.

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments.
    """
    descs = {}
    try:
        f = open(CMD_DESC_FILE)
        while True:
            line = f.readline()
            if not line:
                break
            if "|" in line:
                name, desc = line.split("|", 1)
                descs[name] = desc.rstrip()  # CRLF-safe
        f.close()
    except OSError:
        pass  # missing file: names-only listing
    # cf. cmd_first_sorted -- alphabetical listing
    lines = []
    for name in sorted(e[0] for e in _CMD_TABLE):
        lines.append("{G%-10s{x %s" % (name, descs.get(name, "")))
    tpage(lines)


# -- Command table -------------------------------------------------------------
# All 348 1stMud entries in load order (cf. COMMANDS.md).
# Unported commands commented out as placeholders.
# [PRIMESUD] extensions appended after #348.
# Schema: (name, fn, min_pos, noprefix)

_CMD_TABLE = [
    ("north",      do_north,      "standing", False),  # #1
    ("east",       do_east,       "standing", False),  # #2
    ("south",      do_south,      "standing", False),  # #3
    ("west",       do_west,       "standing", False),  # #4
    ("up",         do_up,         "standing", False),  # #5
    ("down",       do_down,       "standing", False),  # #6
    # ("at",        do_at,         "dead",     False),  # #7 imm lvl 54
    ("cast",       do_cast,       "fighting", False),  # #8
    # ("auction",   do_auction,    "sleeping", False),  # #9
    ("buy",        do_buy,        "resting",  False),  # #10
    # ("channels",  do_channels,   "dead",     False),  # #11
    ("exits",      do_exits,      "resting",  False),  # #12
    ("get",        do_get,        "resting",  False),  # #13
    # ("goto",      do_goto,       "dead",     False),  # #14 imm lvl 52
    # ("group",     do_group,      "sleeping", False),  # #15
    # ("guild",     do_guild,      "dead",     False),  # #16 imm lvl 56
    ("hit",        do_kill,       "fighting", False),  # #17
    ("inventory",  do_inventory,  "dead",     False),  # #18
    ("kill",       do_kill,       "fighting", False),  # #19
    ("look",       do_look,       "resting",  False),  # #20
    # ("clantalk",  do_clantalk,   "sleeping", False),  # #21
    # ("music",     do_music,      "sleeping", False),  # #22
    ("order",      do_order,      "resting",  False),  # #23
    ("practice",   do_practice,   "sleeping", False),  # #24
    ("rest",       do_rest,       "sleeping", False),  # #25
    ("sit",        do_sit,        "sleeping", False),  # #26
    # ("sockets",   do_sockets,    "dead",     False),  # #27 imm lvl 56
    ("stand",      do_stand,      "sleeping", False),  # #28
    ("tell",      do_tell,       "resting",  False),  # #29
    ("unlock",     do_unlock,     "resting",  False),  # #30
    ("wield",      do_wear,       "resting",  False),  # #31
    # ("wizhelp",   do_wizhelp,    "dead",     False),  # #32 imm lvl 51
    ("affects",    do_affects,    "dead",     False),  # #33
    ("areas",      do_areas,      "dead",     False),  # #34
    # ("bug",       do_bug,        "dead",     False),  # #35
    # ("board",     do_board,      "sleeping", False),  # #36
    ("commands",   do_commands,   "dead",     False),  # #37
    ("compare",    do_compare,    "resting",  False),  # #38
    ("consider",   do_consider,   "resting",  False),  # #39
    # ("count",     do_count,      "sleeping", False),  # #40
    ("credits",    do_credits,    "dead",     False),  # #41
    ("equipment",  do_equipment,  "dead",     False),  # #42
    ("examine",    do_examine,    "resting",  False),  # #43
    ("help",       do_help,       "dead",     False),  # #44
    # ("motd",      do_motd,       "dead",     False),  # #45
    ("read",       do_read,       "resting",  False),  # #46
    # ("report",    do_report,     "resting",  False),  # #47
    # ("rules",     do_rules,      "dead",     False),  # #48
    ("score",      do_score,      "dead",     False),  # #49
    ("skills",     do_skills,     "dead",     False),  # #50
    # ("socials",   do_socials,    "dead",     False),  # #51
    # ("show",      do_show,       "dead",     False),  # #52
    ("spells",     do_spells,     "dead",     False),  # #53
    # ("story",     do_story,      "dead",     False),  # #54
    ("time",       do_time,       "dead",     False),  # #55
    # ("typo",      do_typo,       "dead",     False),  # #56
    ("weather",    do_weather,    "resting",  False),  # #57
    # ("who",       do_who,        "dead",     False),  # #58
    # ("whois",     do_whois,      "dead",     False),  # #59
    # ("wizlist",   do_wizlist,    "dead",     False),  # #60
    ("worth",      do_worth,      "sleeping", False),  # #61
    # ("alias",     do_alias,      "dead",     True),   # #62 noprefix
    ("autolist",   do_autolist,   "dead",     False),  # #63
    ("autoassist", do_autoassist, "dead",     False),  # #64
    ("autoexit",   do_autoexit,   "dead",     False),  # #65
    ("autogold",   do_autogold,   "dead",     False),  # #66
    ("autoloot",   do_autoloot,   "dead",     False),  # #67
    ("autosac",    do_autosac,    "dead",     False),  # #68
    ("autosplit",  do_autosplit,  "dead",     False),  # #69
    # ("brief",     do_brief,      "dead",     False),  # #70
    # ("colour",    do_color,      "dead",     False),  # #71
    # ("color",     do_color,      "dead",     False),  # #72
    # ("combine",   do_combine,    "dead",     False),  # #73
    # ("compact",   do_compact,    "dead",     False),  # #74
    # ("description", do_description, "dead",  False),  # #75
    # ("delete",    do_delete,     "standing", True),   # #76 noprefix
    # ("nofollow",  do_nofollow,   "dead",     False),  # #77
    # ("noloot",    do_noloot,     "dead",     False),  # #78
    # ("nosummon",  do_nosummon,   "dead",     False),  # #79
    ("outfit",     do_outfit,     "resting",  False),  # #80
    # ("password",  do_password,   "dead",     False),  # #81
    # ("prompt",    do_prompt,     "dead",     False),  # #82
    # ("screen",    do_screen,     "dead",     False),  # #83
    # ("title",     do_title,      "dead",     False),  # #84
    # ("unalias",   do_unalias,    "dead",     False),  # #85
    ("wimpy",      do_wimpy,      "dead",     False),  # #86
    # ("info",      do_info,       "dead",     False),  # #87
    # ("afk",       do_afk,        "sleeping", False),  # #88
    # ("answer",    do_answer,     "sleeping", False),  # #89
    # ("deaf",      do_deaf,       "dead",     False),  # #90
    ("emote",      do_emote,      "resting",  False),  # #91
    # ("pmote",     do_pmote,      "resting",  False),  # #92
    # (".",         do_gossip,     "sleeping", False),  # #93
    # ("gossip",    do_gossip,     "sleeping", False),  # #94
    (",",          do_emote,      "resting",  False),  # #95
    # ("grats",     do_grats,      "sleeping", False),  # #96
    # ("gtell",     do_gtell,      "dead",     False),  # #97
    # (";",         do_gtell,      "dead",     False),  # #98
    ("quest",     do_quest,      "resting",  False),  # #99
    # qpgive/tpgive: give points to another player -- [PRIMESUD] single-player, skipped
    # ("qpgive",    do_qpgive,     "resting",  False),  # #100
    # ("tpgive",    do_tpgive,     "resting",  False),  # #101
    ("tpspend",   do_tpspend,    "resting",  False),  # #102
    # ("question",  do_question,   "sleeping", False),  # #103
    # ("quote",     do_quote,      "sleeping", False),  # #104
    # ("quiet",     do_quiet,      "sleeping", False),  # #105
    ("reply",     do_reply,      "sleeping", False),  # #106
    # ("replay",    do_replay,     "sleeping", False),  # #107
    ("say",       do_say,        "resting",  False),  # #108
    ("'",         do_say,        "resting",  False),  # #109
    # ("shout",     do_shout,      "resting",  False),  # #110 lvl 3
    ("yell",       do_yell,       "resting",  False),  # #111
    ("brandish",   do_brandish,   "resting",  False),  # #112
    ("close",      do_close,      "resting",  False),  # #113
    ("drink",      do_drink,      "resting",  False),  # #114
    ("drop",       do_drop,       "resting",  False),  # #115
    ("eat",        do_eat,        "resting",  False),  # #116
    ("envenom",    do_envenom,    "resting",  False),  # #117
    ("fill",       do_fill,       "resting",  False),  # #118
    ("give",       do_give,       "resting",  False),  # #119
    ("heal",       do_heal,       "resting",  False),  # #120
    ("hold",       do_wear,       "resting",  False),  # #121
    ("list",       do_list,       "resting",  False),  # #122
    ("lock",       do_lock,       "resting",  False),  # #123
    ("open",       do_open,       "resting",  False),  # #124
    ("pick",       do_pick,       "resting",  False),  # #125
    ("pour",       do_pour,       "resting",  False),  # #126
    ("put",        do_put,        "resting",  False),  # #127
    ("second",     do_second,     "resting",  False),  # #128
    ("quaff",      do_quaff,      "resting",  False),  # #129
    ("recite",     do_recite,     "resting",  False),  # #130
    ("remove",     do_remove,     "resting",  False),  # #131
    ("sell",       do_sell,       "resting",  False),  # #132
    ("take",       do_get,        "resting",  False),  # #133
    ("sacrifice",  do_sacrifice,  "resting",  False),  # #134
    ("junk",       do_sacrifice,  "resting",  False),  # #135
    ("tap",        do_sacrifice,  "resting",  False),  # #136
    ("value",      do_value,      "resting",  False),  # #137
    ("wear",       do_wear,       "resting",  False),  # #138
    ("zap",        do_zap,        "resting",  False),  # #139
    # ("war",       do_war,        "dead",     False),  # #140
    ("backstab",   do_backstab,   "fighting", False),  # #141
    ("bash",       do_bash,       "fighting", False),  # #142
    ("bs",         do_backstab,   "fighting", False),  # #143
    ("berserk",    do_berserk,    "fighting", False),  # #144
    ("dirt",       do_dirt,       "fighting", False),  # #145
    ("disarm",     do_disarm,     "fighting", False),  # #146
    ("flee",       do_flee,       "fighting", False),  # #147
    ("kick",       do_kick,       "fighting", False),  # #148
    ("murder",     do_murder,     "fighting", True),   # #149 noprefix
    ("rescue",     do_rescue,     "fighting", False),  # #150
    ("surrender",  do_surrender,  "fighting", False),  # #151
    ("trip",       do_trip,       "fighting", False),  # #152
    ("hunt",       do_hunt,       "standing", False),  # #153
    ("automap",    do_automap,    "sleeping", False),  # #154
    # ("mob",       do_mob,        "dead",     False),  # #155 mob prog
    ("enter",      do_enter,      "standing", False),  # #156
    ("follow",     do_follow,     "resting",  False),  # #157
    ("gain",       do_gain,       "standing", False),  # #158
    ("go",         do_enter,      "standing", False),  # #159
    ("hide",       do_hide,       "resting",  False),  # #160
    # ("play",      do_play,       "resting",  False),  # #161
    ("quit",       do_quit,       "dead",     True),   # #162 noprefix
    ("recall",     do_recall,     "fighting", False),  # #163
    ("/",          do_recall,     "fighting", False),  # #164
    # ("rent",      do_rent,       "dead",     False),  # #165
    ("save",       do_save,       "dead",     False),  # #166
    ("sleep",      do_sleep,      "sleeping", False),  # #167
    ("sneak",      do_sneak,      "standing", False),  # #168
    # ("split",     do_split,      "resting",  False),  # #169
    ("steal",      do_steal,      "standing", False),  # #170
    ("train",      do_train,      "resting",  False),  # #171
    ("visible",    do_visible,    "sleeping", False),  # #172
    ("wake",       do_wake,       "sleeping", False),  # #173
    ("where",      do_where,      "resting",  False),  # #174
    # ("showstats", do_showstats,  "sleeping", False),  # #175
    # ("compress",  do_compress,   "dead",     False),  # #176
    ("remort",     do_remort,     "standing", True),   # #177 noprefix
    ("gquest",    do_gquest,     "resting",  False),  # #178
    ("explored",   do_explored,   "sleeping", False),  # #179
    # --- Immortal commands #180-#252 ---
    # ("advance",   do_advance,    "dead",     False),  # #180 imm lvl 60
    # ("announce",  do_announce,   "dead",     False),  # #181 imm lvl 53
    # ("trust",     do_trust,      "dead",     False),  # #182 imm lvl 60
    # ("violate",   do_violate,    "dead",     False),  # #183 imm lvl 60
    # ("copyover",  do_copyover,   "dead",     True),   # #184 noprefix, imm lvl 60
    # ("allow",     do_allow,      "dead",     False),  # #185 imm lvl 58
    # ("ban",       do_ban,        "dead",     False),  # #186 imm lvl 58
    # ("deny",      do_deny,       "dead",     False),  # #187 imm lvl 59
    # ("disconnect", do_disconnect, "dead",    False),  # #188 imm lvl 57
    # ("flag",      do_flag,       "dead",     False),  # #189 imm lvl 56
    # ("freeze",    do_freeze,     "dead",     False),  # #190 imm lvl 56
    # ("protect",   do_protect,    "dead",     False),  # #191 imm lvl 59
    # ("reboot",    do_reboot,     "dead",     True),   # #192 noprefix, imm lvl 59
    # ("set",       do_set,        "dead",     False),  # #193 imm lvl 58
    # ("shutdown",  do_shutdown,   "dead",     True),   # #194 noprefix, imm lvl 59
    # ("wizlock",   do_wizlock,    "dead",     False),  # #195 imm lvl 58
    # ("disable",   do_disable,    "dead",     False),  # #196 imm lvl 60
    # ("force",     do_force,      "dead",     False),  # #197 imm lvl 53
    # ("load",      do_load,       "dead",     False),  # #198 imm lvl 56
    # ("newlock",   do_newlock,    "dead",     False),  # #199 imm lvl 56
    # ("nochannels", do_nochannels, "dead",    False),  # #200 imm lvl 55
    # ("noemote",   do_noemote,    "dead",     False),  # #201 imm lvl 55
    # ("noshout",   do_noshout,    "dead",     False),  # #202 imm lvl 55
    # ("note",      do_note,       "dead",     False),  # #203
    # ("notell",    do_notell,     "dead",     False),  # #204 imm lvl 55
    # ("pecho",     do_pecho,      "dead",     False),  # #205 imm lvl 56
    # ("pardon",    do_pardon,     "dead",     False),  # #206 imm lvl 57
    # ("purge",     do_purge,      "dead",     False),  # #207 imm lvl 56
    # ("restore",   do_restore,    "dead",     False),  # #208 imm lvl 56
    # ("slay",     do_slay,       "dead",     True),   # #209 noprefix, imm -- [PRIMESUD] moved to 'debug slay'
    # ("teleport",  do_transfer,   "dead",     False),  # #210 imm lvl 55
    # ("transfer",  do_transfer,   "dead",     False),  # #211 imm lvl 55
    # ("sedit",     do_sedit,      "dead",     False),  # #212 imm lvl 57
    # ("poofin",    do_bamfin,     "dead",     False),  # #213 imm lvl 52
    # ("poofout",   do_bamfout,    "dead",     False),  # #214 imm lvl 52
    # ("gecho",     do_echo,       "dead",     False),  # #215 imm lvl 56
    # ("holylight", do_holylight,  "dead",     False),  # #216 imm lvl 52
    # ("incognito", do_incognito,  "dead",     False),  # #217 imm lvl 52
    # ("invis",     do_invis,      "dead",     False),  # #218 imm lvl 52
    # ("log",       do_log,        "dead",     False),  # #219 imm lvl 59
    # ("memory",    do_memory,     "dead",     False),  # #220 imm lvl 52
    # ("mwhere",    do_mwhere,     "dead",     False),  # #221 imm lvl 52
    # ("owhere",    do_owhere,     "dead",     False),  # #222 imm lvl 52
    # ("peace",     do_peace,      "dead",     False),  # #223 imm lvl 55
    # ("echo",      do_recho,      "dead",     False),  # #224 imm lvl 54
    # ("return",    do_return,     "dead",     False),  # #225 imm lvl 54
    # ("snoop",     do_snoop,      "dead",     False),  # #226 imm lvl 55
    # ("stat",      do_stat,       "dead",     False),  # #227 imm lvl 52
    # ("switch",    do_switch,     "dead",     False),  # #228 imm lvl 54
    # ("wizinvis",  do_invis,      "dead",     False),  # #229 imm lvl 52
    # ("vnum",      do_vnum,       "dead",     False),  # #230 imm lvl 56
    # ("zecho",     do_zecho,      "dead",     False),  # #231 imm lvl 56
    # ("avedam",    do_avedam,     "dead",     False),  # #232 imm lvl 53
    # ("clone",     do_clone,      "dead",     False),  # #233 imm lvl 55
    # ("wiznet",    do_wiznet,     "dead",     False),  # #234 imm lvl 52
    # ("immtalk",   do_immtalk,    "dead",     False),  # #235 imm lvl 52
    # ("imotd",     do_imotd,      "dead",     False),  # #236 imm lvl 52
    # (":",         do_immtalk,    "dead",     False),  # #237 imm lvl 52
    # ("smote",     do_smote,      "dead",     False),  # #238 imm lvl 52
    # ("prefix",    do_prefix,     "dead",     True),   # #239 noprefix, imm lvl 52
    # ("edit",      do_olc,        "dead",     False),  # #240 imm lvl 55
    # ("asave",     do_asave,      "dead",     False),  # #241 imm lvl 55
    # ("alist",     do_alist,      "dead",     False),  # #242 imm lvl 55
    # ("resets",    do_resets,     "dead",     False),  # #243 imm lvl 54
    # ("redit",     do_redit,      "dead",     False),  # #244 imm lvl 55
    # ("medit",     do_medit,      "dead",     False),  # #245 imm lvl 55
    # ("aedit",     do_aedit,      "dead",     False),  # #246 imm lvl 55
    # ("oedit",     do_oedit,      "dead",     False),  # #247 imm lvl 55
    # ("mpedit",    do_mpedit,     "dead",     False),  # #248 imm lvl 53
    # ("hedit",     do_hedit,      "dead",     False),  # #249 imm lvl 55
    # ("cedit",     do_cedit,      "dead",     False),  # #250 imm lvl 55
    # ("cmdedit",   do_cmdedit,    "dead",     False),  # #251 imm lvl 59
    # ("cmdcheck",  do_cmdcheck,   "dead",     False),  # #252 imm lvl 59
    ("scan",       do_scan,       "resting",  False),  # #253
    # ("skedit",    do_skedit,     "dead",     False),  # #254 imm lvl 55
    # ("gredit",    do_gredit,     "dead",     False),  # #255 imm lvl 55
    # ("raedit",    do_raedit,     "dead",     False),  # #256 imm lvl 55
    # ("skcheck",   do_skcheck,    "dead",     False),  # #257 imm lvl 57
    # ("cledit",    do_cledit,     "dead",     False),  # #258 imm lvl 57
    # ("home",      do_home,       "standing", False),  # #259
    # ("bid",       do_bid,        "sleeping", False),  # #260 lvl 2
    ("autodamage", do_autodamage, "sleeping", False),  # #261
    # ("unread",    do_board,      "sleeping", False),  # #262
    # ("clist",     do_clist,      "sleeping", False),  # #263
    # ("cinfo",     do_cinfo,      "sleeping", False),  # #264
    # ("promote",   do_promote,    "resting",  False),  # #265
    # ("donate",    do_donate,     "resting",  False),  # #266
    # ("whowas",    do_whowas,     "sleeping", False),  # #267
    # ("arena",     do_arena,      "resting",  False),  # #268
    # ("bank",      do_bank,       "resting",  False),  # #269
    # ("balance",   do_balance,    "sleeping", False),  # #270
    # ("clanrecall", do_clanrecall, "standing", False), # #271
    # ("join",      do_join,       "sleeping", False),  # #272
    # ("clanadmin", do_clanadmin,  "sleeping", False),  # #273
    # ("rpedit",    do_rpedit,     "dead",     False),  # #274 imm lvl 55
    # ("opedit",    do_opedit,     "dead",     False),  # #275 imm lvl 55
    # ("slist",     do_slist,      "dead",     False),  # #276
    # ("worship",   do_worship,    "resting",  False),  # #277
    # ("dedit",     do_dedit,      "dead",     False),  # #278 imm lvl 55
    # ("nogocial",  do_nogocial,   "sleeping", False),  # #279
    # ("ooc",       do_ooc,        "dead",     False),  # #280
    # ("spellup",   do_spellup,    "dead",     False),  # #281 imm lvl 54
    # ("webpass",   do_webpass,    "dead",     False),  # #282 imm lvl 54
    # ("strkey",    do_strkey,     "dead",     False),  # #283
    ("run",        do_run,        "standing", False),  # #284
    # ("pload",     do_pload,      "dead",     False),  # #285 imm lvl 55
    # ("punload",   do_punload,    "dead",     False),  # #286 imm lvl 55
    # ("buddy",     do_buddy,      "sleeping", False),  # #287
    # ("btalk",     do_btalk,      "sleeping", False),  # #288
    # ("areaset",   do_afun,       "dead",     False),  # #289 imm lvl 59
    # ("roster",    do_roster,     "sleeping", False),  # #290
    ("map",        do_map,        "resting",  False),  # #291
    # ("clanlist",  do_clist,      "sleeping", False),  # #292
    # ("claninfo",  do_cinfo,      "sleeping", False),  # #293
    # ("timezone",  do_timezone,   "sleeping", False),  # #294
    # ("crash",     do_crash,      "dead",     False),  # #295 imm lvl 60
    # ("songedit",  do_songedit,   "dead",     False),  # #296 imm lvl 54
    # ("chanedit",  do_chanedit,   "dead",     False),  # #297 imm lvl 55
    # ("mudedit",   do_mudedit,    "dead",     False),  # #298 imm lvl 59
    # ("mxp",       do_mxp,        "dead",     False),  # #299
    # ("portal",    do_portal,     "dead",     False),  # #300
    # ("imp",       do_imp,        "dead",     False),  # #301
    # ("pueblo",    do_pueblo,     "dead",     False),  # #302
    # ("msp",       do_msp,        "dead",     False),  # #303
    ("sskill",     do_sskill,     "sleeping", False),  # #304
    ("stance",     do_stance,     "standing", False),  # #305
    ("autostance", do_autostance, "sleeping", False),  # #306
    # ("ignore",    do_ignore,     "sleeping", False),  # #307
    # ("grlist",    do_grlist,     "sleeping", False),  # #308
    # ("programs",  do_programs,   "dead",     False),  # #309 imm lvl 58
    # ("subscribe", do_subscribe,  "dead",     False),  # #310
    # ("barter",    do_barter,     "dead",     False),  # #311
    # ("tax",       do_tax,        "dead",     False),  # #312 imm lvl 57
    # ("autoprompt", do_autoprompt, "dead",    False),  # #313
    # ("gprompt",   do_gprompt,    "dead",     False),  # #314
    # ("bonus",     do_bonus,      "dead",     False),  # #315 imm lvl 56
    # ("sendstats", do_sendstat,   "dead",     False),  # #316 imm lvl 60
    # ("prime",     do_prime,      "sleeping", True),   # #317 noprefix, imm lvl 51
    # ("ring",      do_ring,       "resting",  False),  # #318
    # ("genname",   do_genname,    "sleeping", False),  # #319
    # ("index",     do_index,      "dead",     False),  # #320
    # ("client",    do_client,     "dead",     False),  # #321
    # ("backup",    do_backup,     "sleeping", True),   # #322 noprefix
    # ("system",    do_system,     "dead",     True),   # #323 noprefix, imm lvl 60
    # ("heel",      do_heel,       "resting",  False),  # #324
    # ("whisper",   do_whisper,    "resting",  False),  # #325
    # ("sooc",      do_sooc,       "resting",  False),  # #326
    # ("helpcheck", do_helpcheck,  "dead",     False),  # #327 imm lvl 54
    # ("think",     do_think,      "resting",  False),  # #328
    ("ditch",      do_ditch,      "resting",  False),  # #329
    # ("censor",    do_censor,     "sleeping", False),  # #330
    ("clear",      do_clear,      "dead",     False),  # #331
    ("cls",        do_clear,      "dead",     False),  # #332
    # ("nosayverbs", do_nosayverbs, "sleeping", False), # #333
    # ("mobdeaths", do_mobdeaths,  "sleeping", False),  # #334
    # ("mobkills",  do_mobkills,   "sleeping", False),  # #335
    # ("areakills", do_areakills,  "sleeping", False),  # #336
    # ("areadeaths", do_areadeaths, "sleeping", False), # #337
    # ("version",   do_version,    "dead",     False),  # #338
    # ("sshow",     do_sshow,      "sleeping", False),  # #339
    ("appraise",  do_appraise,   "standing", False),  # #340
    # ("rename",    do_rename,     "dead",     True),   # #341 noprefix, imm lvl 59
    # ("path",      do_path,       "resting",  False),  # #342
    # ("nopretitles", do_nopretitles, "sleeping", False), # #343
    ("suicide",    do_suicide,    "resting",  True),   # #344 noprefix
    # ("changes",   do_changes,    "dead",     False),  # #345 imm lvl 59
    # ("pk",        do_pk,         "sleeping", True),   # #346 noprefix
    # ("pkshow",    do_pkshow,     "sleeping", False),  # #347
    # ("coledit",   do_coledit,    "dead",     False),  # #348 imm lvl 55
    # --- [PRIMESUD] extensions (after 1stMud table) ---
    ("macro",      do_macro,      "dead",     False),  # [PRIMESUD] #349
    ("debug",      do_debug,      "dead",     False),  # [PRIMESUD] #350
]


# -- Interpreter ---------------------------------------------------------------

# {? = random colour in 1stMud; we use {R as fallback until random colour ported
_HUH_MESSAGES = [
    "{RHuh?{x",
    "{RPardon?{x",
    "{RWhat is command '%s'?{x",
    "{RInput error.{x",
    "{RTry again.{x",
    "{RI do not understand.{x",
    "{RType commands for a list of commands.{x",
]


def one_argument(argument):
    """Extract one argument from *argument*, returning (word, rest) (cf. 1stMud one_argument in interp.c).

    Handles single/double-quote grouping.  Both the extracted word and the
    remainder are lowercased to match 1stMud's ``tolower`` inside
    ``one_argument``.
    """
    i = 0
    argument = argument.strip().lower()
    length = len(argument)
    while i < length and argument[i].isspace():
        i += 1
    if i >= length:
        return ("", "")
    end = " "
    if argument[i] == "'" or argument[i] == '"':
        end = argument[i]
        i += 1
    start = i
    if end == " ":
        while i < length and not argument[i].isspace():
            i += 1
    else:
        while i < length and argument[i] != end:
            i += 1
    word = argument[start:i]
    if i < length and argument[i] == end:
        i += 1
    rest = argument[i:].strip()
    return (word, rest)


def split_args(argument):
    """Split *argument* into a list via repeated one_argument calls (cf. 1stMud)."""
    args = []
    while argument:
        word, argument = one_argument(argument)
        if word:
            args.append(word)
    return args


def interpret(raw, player):
    """Main command interpreter (cf. 1stMud interpret in interp.c).

    Flow mirrors 1stMud: strip input, remove AFF_HIDE, extract command word
    (handling non-alpha first chars), look up command, check position, execute.
    """
    argument = raw.strip()
    if not argument:
        return None
    tprint("")

    # RemBit(ch->affected_by, AFF_HIDE)
    aff = player.get("affected_by")
    if aff:
        aff.pop("hide", None)

    # -- PLR_FREEZE: not applicable in single-player

    # Non-alpha/digit first char is a single-char command (e.g. '/')
    ch0 = argument[0]
    if not ch0.isalpha() and not ch0.isdigit():
        command = ch0.lower()
        # cf. interp.c: only leading whitespace skipped; remainder kept
        # verbatim (was .strip().lower() -- lowercased say/emote text)
        argument = argument[1:].lstrip()
    else:
        command, argument = one_argument(argument)

    # -- Look up command in table (cf. command_hash scan)
    cmd = None
    for entry in _CMD_TABLE:
        name, fn, min_pos, noprefix = entry
        if noprefix:
            if command != name:
                continue
        else:
            if not name.startswith(command):
                continue
            # cmd_level_ok: not applicable in single-player
        cmd = entry
        break

    # -- No match: check_social fallback, then huh message
    if not cmd:
        # check_social: not yet ported
        msg = _HUH_MESSAGES[randint(0, len(_HUH_MESSAGES) - 1)]
        if "%s" in msg:
            chprintln(player, msg % command)
        else:
            chprintln(player, msg)
        return None

    # -- check_disabled: not yet ported

    name, fn, min_pos, noprefix = cmd

    # -- Position gate (cf. switch on ch->position)
    pos = player.get("pos", "standing")
    if POS_ORDER[pos] < POS_ORDER[min_pos]:
        chprintln(player, _POS_MSG.get(pos, ""))
        return None

    args = split_args(argument)
    result = fn(player, args)
    # [PRIMESUD] mark the room the command left us in as explored. 1stMud does
    # this in char_to_room; PrimeSUD has no such choke point, so mark_explored
    # compares against a cached vnum here (player moves) and in the update tick
    # (mob-initiated drags). See explored.py module docstring.
    mark_explored(player)
    return result
