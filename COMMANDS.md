# 1stMud 4.5.3 — Command Table Reference

Source: `reference/1stMud4.5.3/data/commands.dat`

## How command lookup works

Commands are stored in a hash table keyed by `tolower(name[0]) % MAX_CMD_HASH`
(MAX_CMD_HASH = 126, defined in `defines.h`).  Each bucket is a linked list in
**load order** (the order entries appear in `commands.dat`).  Lookup walks the
bucket and takes the **first** entry that prefix-matches and passes the level
check — so earlier entries win over later ones sharing a prefix.

Exception: the `noprefix` flag forces **exact-match** comparison (`str_cmp`
instead of `str_prefix`), bypassing prefix collision.

## Flags

| Flag | Meaning |
|------|---------|
| `noprefix` | Exact match only — no abbreviation |
| `no_order` | Cannot be issued via `order <mob> <cmd>` |
| `noalias` | Cannot be triggered through an alias |
| `deleted` | Disabled/removed; still in table but not accessible |

## Position constants (minimum required position)

`dead` < `sleeping` < `resting` < `sitting` < `standing` < `fighting`

`dead` means the command works at any position (even while dead).

## Level thresholds

Mortal max = level 50.  Immortal range: 51 (Hero) … 60 (Implementor).

## Command table

`#` = load order (determines prefix-match priority within the hash bucket).
`pos` = minimum position.  `lvl` = minimum level (0 = all mortals).

| # | name | do_fun | pos | lvl | flags | log | category |
|---|------|--------|-----|-----|-------|-----|----------|
| 1 | north | do_north | standing | 0 | none | never | movement |
| 2 | east | do_east | standing | 0 | none | never | movement |
| 3 | south | do_south | standing | 0 | none | never | movement |
| 4 | west | do_west | standing | 0 | none | never | movement |
| 5 | up | do_up | standing | 0 | none | never | movement |
| 6 | down | do_down | standing | 0 | none | never | movement |
| 7 | at | do_at | dead | 54 | none | normal | immortal |
| 8 | cast | do_cast | fighting | 0 | none | normal | combat |
| 9 | auction | do_auction | sleeping | 0 | none | normal | object |
| 10 | buy | do_buy | resting | 0 | none | normal | object |
| 11 | channels | do_channels | dead | 0 | none | normal | communication |
| 12 | exits | do_exits | resting | 0 | none | normal | information |
| 13 | get | do_get | resting | 0 | none | normal | object |
| 14 | goto | do_goto | dead | 52 | none | normal | immortal |
| 15 | group | do_group | sleeping | 0 | none | normal | combat |
| 16 | guild | do_guild | dead | 56 | none | normal | immortal |
| 17 | hit | do_kill | fighting | 0 | none | normal | hidden |
| 18 | inventory | do_inventory | dead | 0 | none | normal | information |
| 19 | kill | do_kill | fighting | 0 | none | normal | combat |
| 20 | look | do_look | resting | 0 | none | normal | information |
| 21 | clantalk | do_clantalk | sleeping | 0 | none | normal | clan |
| 22 | music | do_music | sleeping | 0 | none | normal | communication |
| 23 | order | do_order | resting | 0 | none | normal | miscellaneous |
| 24 | practice | do_practice | sleeping | 0 | none | normal | miscellaneous |
| 25 | rest | do_rest | sleeping | 0 | none | normal | movement |
| 26 | sit | do_sit | sleeping | 0 | none | normal | movement |
| 27 | sockets | do_sockets | dead | 56 | none | normal | immortal |
| 28 | stand | do_stand | sleeping | 0 | none | normal | movement |
| 29 | tell | do_tell | resting | 0 | none | normal | communication |
| 30 | unlock | do_unlock | resting | 0 | none | normal | object |
| 31 | wield | do_wear | resting | 0 | none | normal | object |
| 32 | wizhelp | do_wizhelp | dead | 51 | none | normal | immortal |
| 33 | affects | do_affects | dead | 0 | none | normal | information |
| 34 | areas | do_areas | dead | 0 | none | normal | information |
| 35 | bug | do_bug | dead | 0 | none | normal | miscellaneous |
| 36 | board | do_board | sleeping | 0 | none | normal | information |
| 37 | commands | do_commands | dead | 0 | none | normal | information |
| 38 | compare | do_compare | resting | 0 | none | normal | information |
| 39 | consider | do_consider | resting | 0 | none | normal | combat |
| 40 | count | do_count | sleeping | 0 | none | normal | information |
| 41 | credits | do_credits | dead | 0 | none | normal | information |
| 42 | equipment | do_equipment | dead | 0 | none | normal | information |
| 43 | examine | do_examine | resting | 0 | none | normal | information |
| 44 | help | do_help | dead | 0 | none | normal | information |
| 45 | motd | do_motd | dead | 0 | none | normal | information |
| 46 | read | do_read | resting | 0 | none | normal | information |
| 47 | report | do_report | resting | 0 | none | normal | information |
| 48 | rules | do_rules | dead | 0 | none | normal | information |
| 49 | score | do_score | dead | 0 | none | normal | information |
| 50 | skills | do_skills | dead | 0 | none | normal | information |
| 51 | socials | do_socials | dead | 0 | none | normal | information |
| 52 | show | do_show | dead | 0 | none | normal | settings |
| 53 | spells | do_spells | dead | 0 | none | normal | information |
| 54 | story | do_story | dead | 0 | none | normal | information |
| 55 | time | do_time | dead | 0 | none | normal | information |
| 56 | typo | do_typo | dead | 0 | none | normal | miscellaneous |
| 57 | weather | do_weather | resting | 0 | none | normal | information |
| 58 | who | do_who | dead | 0 | none | normal | information |
| 59 | whois | do_whois | dead | 0 | none | normal | information |
| 60 | wizlist | do_wizlist | dead | 0 | none | normal | information |
| 61 | worth | do_worth | sleeping | 0 | none | normal | information |
| 62 | alias | do_alias | dead | 0 | noprefix | normal | settings |
| 63 | autolist | do_autolist | dead | 0 | none | normal | information |
| 64 | autoassist | do_autoassist | dead | 0 | none | normal | settings |
| 65 | autoexit | do_autoexit | dead | 0 | none | normal | settings |
| 66 | autogold | do_autogold | dead | 0 | none | normal | settings |
| 67 | autoloot | do_autoloot | dead | 0 | none | normal | settings |
| 68 | autosac | do_autosac | dead | 0 | none | normal | settings |
| 69 | autosplit | do_autosplit | dead | 0 | none | normal | settings |
| 70 | brief | do_brief | dead | 0 | none | normal | settings |
| 71 | colour | do_color | dead | 0 | none | normal | hidden |
| 72 | color | do_color | dead | 0 | none | normal | settings |
| 73 | combine | do_combine | dead | 0 | none | normal | settings |
| 74 | compact | do_compact | dead | 0 | none | normal | settings |
| 75 | description | do_description | dead | 0 | none | normal | settings |
| 76 | delete | do_delete | standing | 0 | noprefix no_order noalias | always | miscellaneous |
| 77 | nofollow | do_nofollow | dead | 0 | none | normal | settings |
| 78 | noloot | do_noloot | dead | 0 | none | normal | settings |
| 79 | nosummon | do_nosummon | dead | 0 | none | normal | settings |
| 80 | outfit | do_outfit | resting | 0 | none | normal | object |
| 81 | password | do_password | dead | 0 | none | never | settings |
| 82 | prompt | do_prompt | dead | 0 | none | normal | settings |
| 83 | screen | do_screen | dead | 0 | none | normal | settings |
| 84 | title | do_title | dead | 0 | none | normal | settings |
| 85 | unalias | do_unalias | dead | 0 | none | normal | settings |
| 86 | wimpy | do_wimpy | dead | 0 | none | normal | combat |
| 87 | info | do_info | dead | 0 | none | normal | information |
| 88 | afk | do_afk | sleeping | 0 | none | normal | settings |
| 89 | answer | do_answer | sleeping | 0 | none | normal | communication |
| 90 | deaf | do_deaf | dead | 0 | none | normal | communication |
| 91 | emote | do_emote | resting | 0 | none | normal | communication |
| 92 | pmote | do_pmote | resting | 0 | none | normal | communication |
| 93 | . | do_gossip | sleeping | 0 | none | normal | hidden |
| 94 | gossip | do_gossip | sleeping | 0 | none | normal | communication |
| 95 | , | do_emote | resting | 0 | none | normal | hidden |
| 96 | grats | do_grats | sleeping | 0 | none | normal | communication |
| 97 | gtell | do_gtell | dead | 0 | none | normal | communication |
| 98 | ; | do_gtell | dead | 0 | none | normal | hidden |
| 99 | quest | do_quest | resting | 0 | none | normal | miscellaneous |
| 100 | qpgive | do_qpgive | resting | 0 | none | normal | miscellaneous |
| 101 | tpgive | do_tpgive | resting | 0 | none | normal | miscellaneous |
| 102 | tpspend | do_tpspend | resting | 0 | none | normal | miscellaneous |
| 103 | question | do_question | sleeping | 0 | none | normal | communication |
| 104 | quote | do_quote | sleeping | 0 | none | normal | communication |
| 105 | quiet | do_quiet | sleeping | 0 | none | normal | communication |
| 106 | reply | do_reply | sleeping | 0 | none | normal | communication |
| 107 | replay | do_replay | sleeping | 0 | none | normal | communication |
| 108 | say | do_say | resting | 0 | none | normal | communication |
| 109 | ' | do_say | resting | 0 | none | normal | hidden |
| 110 | shout | do_shout | resting | 3 | none | normal | communication |
| 111 | yell | do_yell | resting | 0 | none | normal | communication |
| 112 | brandish | do_brandish | resting | 0 | none | normal | object |
| 113 | close | do_close | resting | 0 | none | normal | object |
| 114 | drink | do_drink | resting | 0 | none | normal | object |
| 115 | drop | do_drop | resting | 0 | none | normal | object |
| 116 | eat | do_eat | resting | 0 | none | normal | object |
| 117 | envenom | do_envenom | resting | 0 | none | normal | combat |
| 118 | fill | do_fill | resting | 0 | none | normal | object |
| 119 | give | do_give | resting | 0 | none | normal | object |
| 120 | heal | do_heal | resting | 0 | none | normal | miscellaneous |
| 121 | hold | do_wear | resting | 0 | none | normal | object |
| 122 | list | do_list | resting | 0 | none | normal | object |
| 123 | lock | do_lock | resting | 0 | none | normal | object |
| 124 | open | do_open | resting | 0 | none | normal | object |
| 125 | pick | do_pick | resting | 0 | none | normal | object |
| 126 | pour | do_pour | resting | 0 | none | normal | object |
| 127 | put | do_put | resting | 0 | none | normal | object |
| 128 | second | do_second | resting | 0 | none | normal | object |
| 129 | quaff | do_quaff | resting | 0 | none | normal | object |
| 130 | recite | do_recite | resting | 0 | none | normal | object |
| 131 | remove | do_remove | resting | 0 | none | normal | object |
| 132 | sell | do_sell | resting | 0 | none | normal | object |
| 133 | take | do_get | resting | 0 | none | normal | object |
| 134 | sacrifice | do_sacrifice | resting | 0 | none | normal | object |
| 135 | junk | do_sacrifice | resting | 0 | none | normal | hidden |
| 136 | tap | do_sacrifice | resting | 0 | none | normal | hidden |
| 137 | value | do_value | resting | 0 | none | normal | object |
| 138 | wear | do_wear | resting | 0 | none | normal | object |
| 139 | zap | do_zap | resting | 0 | none | normal | object |
| 140 | war | do_war | dead | 0 | none | normal | miscellaneous |
| 141 | backstab | do_backstab | fighting | 0 | none | normal | combat |
| 142 | bash | do_bash | fighting | 0 | none | normal | combat |
| 143 | bs | do_backstab | fighting | 0 | none | normal | hidden |
| 144 | berserk | do_berserk | fighting | 0 | none | normal | combat |
| 145 | dirt | do_dirt | fighting | 0 | none | normal | combat |
| 146 | disarm | do_disarm | fighting | 0 | none | normal | combat |
| 147 | flee | do_flee | fighting | 0 | none | normal | combat |
| 148 | kick | do_kick | fighting | 0 | none | normal | combat |
| 149 | murder | do_murder | fighting | 5 | noprefix | always | combat |
| 150 | rescue | do_rescue | fighting | 0 | none | normal | combat |
| 151 | surrender | do_surrender | fighting | 0 | none | normal | combat |
| 152 | trip | do_trip | fighting | 0 | none | normal | combat |
| 153 | hunt | do_hunt | standing | 0 | none | normal | combat |
| 154 | automap | do_automap | sleeping | 0 | none | normal | settings |
| 155 | mob | do_mob | dead | 0 | none | never | hidden |
| 156 | enter | do_enter | standing | 0 | none | normal | object |
| 157 | follow | do_follow | resting | 0 | none | normal | combat |
| 158 | gain | do_gain | standing | 0 | none | normal | miscellaneous |
| 159 | go | do_enter | standing | 0 | none | normal | hidden |
| 160 | hide | do_hide | resting | 0 | none | normal | movement |
| 161 | play | do_play | resting | 0 | none | normal | miscellaneous |
| 162 | quit | do_quit | dead | 0 | noprefix | normal | miscellaneous |
| 163 | recall | do_recall | fighting | 0 | none | normal | movement |
| 164 | / | do_recall | fighting | 0 | none | normal | hidden |
| 165 | rent | do_rent | dead | 0 | none | normal | hidden |
| 166 | save | do_save | dead | 0 | none | normal | miscellaneous |
| 167 | sleep | do_sleep | sleeping | 0 | none | normal | movement |
| 168 | sneak | do_sneak | standing | 0 | none | normal | movement |
| 169 | split | do_split | resting | 0 | none | normal | object |
| 170 | steal | do_steal | standing | 0 | none | normal | object |
| 171 | train | do_train | resting | 0 | none | normal | miscellaneous |
| 172 | visible | do_visible | sleeping | 0 | none | normal | combat |
| 173 | wake | do_wake | sleeping | 0 | none | normal | movement |
| 174 | where | do_where | resting | 0 | none | normal | information |
| 175 | showstats | do_showstats | sleeping | 0 | none | normal | information |
| 176 | compress | do_compress | dead | 0 | none | normal | settings |
| 177 | remort | do_remort | standing | 51 | noprefix | normal | miscellaneous |
| 178 | gquest | do_gquest | resting | 0 | none | normal | miscellaneous |
| 179 | explored | do_explored | sleeping | 0 | none | normal | information |
| 180 | advance | do_advance | dead | 60 | none | normal | immortal |
| 181 | announce | do_announce | dead | 53 | none | normal | immortal |
| 182 | trust | do_trust | dead | 60 | none | normal | immortal |
| 183 | violate | do_violate | dead | 60 | none | normal | immortal |
| 184 | copyover | do_copyover | dead | 60 | noprefix no_order noalias | normal | immortal |
| 185 | allow | do_allow | dead | 58 | none | normal | immortal |
| 186 | ban | do_ban | dead | 58 | none | normal | immortal |
| 187 | deny | do_deny | dead | 59 | none | normal | immortal |
| 188 | disconnect | do_disconnect | dead | 57 | none | normal | immortal |
| 189 | flag | do_flag | dead | 56 | none | normal | immortal |
| 190 | freeze | do_freeze | dead | 56 | none | normal | immortal |
| 191 | protect | do_protect | dead | 59 | none | normal | immortal |
| 192 | reboot | do_reboot | dead | 59 | noprefix no_order noalias | normal | immortal |
| 193 | set | do_set | dead | 58 | none | normal | immortal |
| 194 | shutdown | do_shutdown | dead | 59 | noprefix no_order noalias | normal | immortal |
| 195 | wizlock | do_wizlock | dead | 58 | none | normal | immortal |
| 196 | disable | do_disable | dead | 60 | none | normal | immortal |
| 197 | force | do_force | dead | 53 | none | normal | immortal |
| 198 | load | do_load | dead | 56 | none | normal | immortal |
| 199 | newlock | do_newlock | dead | 56 | none | normal | immortal |
| 200 | nochannels | do_nochannels | dead | 55 | none | normal | immortal |
| 201 | noemote | do_noemote | dead | 55 | none | normal | immortal |
| 202 | noshout | do_noshout | dead | 55 | none | normal | immortal |
| 203 | note | do_note | dead | 0 | none | normal | communication |
| 204 | notell | do_notell | dead | 55 | none | normal | immortal |
| 205 | pecho | do_pecho | dead | 56 | none | normal | immortal |
| 206 | pardon | do_pardon | dead | 57 | none | normal | immortal |
| 207 | purge | do_purge | dead | 56 | none | normal | immortal |
| 208 | restore | do_restore | dead | 56 | none | normal | immortal |
| 209 | slay | do_slay | dead | 57 | noprefix | normal | immortal |
| 210 | teleport | do_transfer | dead | 55 | none | normal | immortal |
| 211 | transfer | do_transfer | dead | 55 | none | normal | immortal |
| 212 | sedit | do_sedit | dead | 57 | none | normal | immortal |
| 213 | poofin | do_bamfin | dead | 52 | none | normal | immortal |
| 214 | poofout | do_bamfout | dead | 52 | none | normal | immortal |
| 215 | gecho | do_echo | dead | 56 | none | normal | immortal |
| 216 | holylight | do_holylight | dead | 52 | none | normal | immortal |
| 217 | incognito | do_incognito | dead | 52 | none | normal | immortal |
| 218 | invis | do_invis | dead | 52 | none | normal | hidden |
| 219 | log | do_log | dead | 59 | none | normal | immortal |
| 220 | memory | do_memory | dead | 52 | none | normal | immortal |
| 221 | mwhere | do_mwhere | dead | 52 | none | normal | immortal |
| 222 | owhere | do_owhere | dead | 52 | none | normal | immortal |
| 223 | peace | do_peace | dead | 55 | none | normal | immortal |
| 224 | echo | do_recho | dead | 54 | none | normal | immortal |
| 225 | return | do_return | dead | 54 | none | normal | immortal |
| 226 | snoop | do_snoop | dead | 55 | none | normal | immortal |
| 227 | stat | do_stat | dead | 52 | none | normal | immortal |
| 228 | switch | do_switch | dead | 54 | none | normal | immortal |
| 229 | wizinvis | do_invis | dead | 52 | none | normal | immortal |
| 230 | vnum | do_vnum | dead | 56 | none | normal | immortal |
| 231 | zecho | do_zecho | dead | 56 | none | normal | immortal |
| 232 | avedam | do_avedam | dead | 53 | none | normal | immortal |
| 233 | clone | do_clone | dead | 55 | none | normal | immortal |
| 234 | wiznet | do_wiznet | dead | 52 | none | normal | immortal |
| 235 | immtalk | do_immtalk | dead | 52 | none | normal | immortal |
| 236 | imotd | do_imotd | dead | 52 | none | normal | immortal |
| 237 | : | do_immtalk | dead | 52 | none | normal | hidden |
| 238 | smote | do_smote | dead | 52 | none | normal | immortal |
| 239 | prefix | do_prefix | dead | 52 | noprefix | normal | immortal |
| 240 | edit | do_olc | dead | 55 | none | normal | immortal |
| 241 | asave | do_asave | dead | 55 | none | normal | immortal |
| 242 | alist | do_alist | dead | 55 | none | normal | immortal |
| 243 | resets | do_resets | dead | 54 | none | normal | immortal |
| 244 | redit | do_redit | dead | 55 | none | normal | immortal |
| 245 | medit | do_medit | dead | 55 | none | normal | immortal |
| 246 | aedit | do_aedit | dead | 55 | none | normal | olc |
| 247 | oedit | do_oedit | dead | 55 | none | normal | immortal |
| 248 | mpedit | do_mpedit | dead | 53 | none | normal | immortal |
| 249 | hedit | do_hedit | dead | 55 | none | normal | immortal |
| 250 | cedit | do_cedit | dead | 55 | none | normal | immortal |
| 251 | cmdedit | do_cmdedit | dead | 59 | none | normal | immortal |
| 252 | cmdcheck | do_cmdcheck | dead | 59 | none | normal | immortal |
| 253 | scan | do_scan | resting | 0 | none | normal | information |
| 254 | skedit | do_skedit | dead | 55 | none | normal | immortal |
| 255 | gredit | do_gredit | dead | 55 | none | normal | immortal |
| 256 | raedit | do_raedit | dead | 55 | none | normal | immortal |
| 257 | skcheck | do_skcheck | dead | 57 | none | normal | immortal |
| 258 | cledit | do_cledit | dead | 57 | none | normal | immortal |
| 259 | home | do_home | standing | 0 | none | normal | miscellaneous |
| 260 | bid | do_bid | sleeping | 2 | none | normal | object |
| 261 | autodamage | do_autodamage | sleeping | 0 | none | normal | settings |
| 262 | unread | do_board | sleeping | 0 | none | normal | hidden |
| 263 | clist | do_clist | sleeping | 0 | none | normal | clan |
| 264 | cinfo | do_cinfo | sleeping | 0 | none | normal | clan |
| 265 | promote | do_promote | resting | 0 | none | normal | clan |
| 266 | donate | do_donate | resting | 0 | none | normal | object |
| 267 | whowas | do_whowas | sleeping | 0 | none | normal | information |
| 268 | arena | do_arena | resting | 0 | none | normal | miscellaneous |
| 269 | bank | do_bank | resting | 0 | none | normal | miscellaneous |
| 270 | balance | do_balance | sleeping | 0 | none | normal | information |
| 271 | clanrecall | do_clanrecall | standing | 0 | none | normal | clan |
| 272 | join | do_join | sleeping | 0 | none | normal | clan |
| 273 | clanadmin | do_clanadmin | sleeping | 0 | none | normal | clan |
| 274 | rpedit | do_rpedit | dead | 55 | none | normal | immortal |
| 275 | opedit | do_opedit | dead | 55 | none | normal | immortal |
| 276 | slist | do_slist | dead | 0 | none | normal | information |
| 277 | worship | do_worship | resting | 0 | none | normal | miscellaneous |
| 278 | dedit | do_dedit | dead | 55 | none | normal | immortal |
| 279 | nogocial | do_nogocial | sleeping | 0 | none | normal | settings |
| 280 | ooc | do_ooc | dead | 0 | none | normal | hidden |
| 281 | spellup | do_spellup | dead | 54 | none | normal | immortal |
| 282 | webpass | do_webpass | dead | 54 | none | normal | immortal |
| 283 | strkey | do_strkey | dead | 0 | none | normal | settings |
| 284 | run | do_run | standing | 0 | none | normal | movement |
| 285 | pload | do_pload | dead | 55 | none | normal | immortal |
| 286 | punload | do_punload | dead | 55 | none | normal | immortal |
| 287 | buddy | do_buddy | sleeping | 0 | none | normal | settings |
| 288 | btalk | do_btalk | sleeping | 0 | none | normal | communication |
| 289 | areaset | do_afun | dead | 59 | none | normal | immortal |
| 290 | roster | do_roster | sleeping | 0 | none | normal | clan |
| 291 | map | do_map | resting | 0 | none | normal | information |
| 292 | clanlist | do_clist | sleeping | 0 | none | normal | hidden |
| 293 | claninfo | do_cinfo | sleeping | 0 | none | normal | hidden |
| 294 | timezone | do_timezone | sleeping | 0 | none | normal | miscellaneous |
| 295 | crash | do_crash | dead | 60 | none | always | hidden |
| 296 | songedit | do_songedit | dead | 54 | none | normal | immortal |
| 297 | chanedit | do_chanedit | dead | 55 | none | normal | immortal |
| 298 | mudedit | do_mudedit | dead | 59 | none | normal | immortal |
| 299 | mxp | do_mxp | dead | 0 | none | normal | settings |
| 300 | portal | do_portal | dead | 0 | none | normal | settings |
| 301 | imp | do_imp | dead | 0 | none | normal | settings |
| 302 | pueblo | do_pueblo | dead | 0 | none | normal | settings |
| 303 | msp | do_msp | dead | 0 | none | normal | settings |
| 304 | sskill | do_sskill | sleeping | 0 | none | normal | information |
| 305 | stance | do_stance | standing | 0 | none | normal | combat |
| 306 | autostance | do_autostance | sleeping | 0 | none | normal | combat |
| 307 | ignore | do_ignore | sleeping | 0 | none | normal | hidden |
| 308 | grlist | do_grlist | sleeping | 0 | none | normal | information |
| 309 | programs | do_programs | dead | 58 | none | normal | immortal |
| 310 | subscribe | do_subscribe | dead | 0 | none | normal | settings |
| 311 | barter | do_barter | dead | 0 | none | normal | communication |
| 312 | tax | do_tax | dead | 57 | none | normal | immortal |
| 313 | autoprompt | do_autoprompt | dead | 0 | none | normal | settings |
| 314 | gprompt | do_gprompt | dead | 0 | none | normal | settings |
| 315 | bonus | do_bonus | dead | 56 | none | normal | immortal |
| 316 | sendstats | do_sendstat | dead | 60 | no_order noalias | always | immortal |
| 317 | prime | do_prime | sleeping | 51 | noprefix no_order noalias | always | settings |
| 318 | ring | do_ring | resting | 0 | none | normal | object |
| 319 | genname | do_genname | sleeping | 0 | none | normal | miscellaneous |
| 320 | index | do_index | dead | 0 | none | normal | information |
| 321 | client | do_client | dead | 0 | none | normal | settings |
| 322 | backup | do_backup | sleeping | 0 | noprefix no_order noalias | normal | miscellaneous |
| 323 | system | do_system | dead | 60 | noprefix no_order noalias | normal | immortal |
| 324 | heel | do_heel | resting | 0 | none | normal | miscellaneous |
| 325 | whisper | do_whisper | resting | 0 | none | normal | communication |
| 326 | sooc | do_sooc | resting | 0 | none | normal | communication |
| 327 | helpcheck | do_helpcheck | dead | 54 | none | normal | immortal |
| 328 | think | do_think | resting | 0 | none | normal | communication |
| 329 | ditch | do_ditch | resting | 0 | none | normal | miscellaneous |
| 330 | censor | do_censor | sleeping | 0 | none | normal | communication |
| 331 | clear | do_clear | dead | 0 | none | normal | miscellaneous |
| 332 | cls | do_clear | dead | 0 | none | normal | hidden |
| 333 | nosayverbs | do_nosayverbs | sleeping | 0 | none | normal | settings |
| 334 | mobdeaths | do_mobdeaths | sleeping | 0 | none | normal | information |
| 335 | mobkills | do_mobkills | sleeping | 0 | none | normal | information |
| 336 | areakills | do_areakills | sleeping | 0 | none | normal | information |
| 337 | areadeaths | do_areadeaths | sleeping | 0 | none | normal | information |
| 338 | version | do_version | dead | 0 | none | normal | information |
| 339 | sshow | do_sshow | sleeping | 0 | none | normal | information |
| 340 | appraise | do_appraise | standing | 0 | none | normal | object |
| 341 | rename | do_rename | dead | 59 | noprefix no_order noalias | always | immortal |
| 342 | path | do_path | resting | 0 | none | normal | movement |
| 343 | nopretitles | do_nopretitles | sleeping | 0 | none | normal | settings |
| 344 | suicide | do_suicide | resting | 0 | noprefix no_order noalias | always | combat |
| 345 | changes | do_changes | dead | 59 | none | normal | immortal |
| 346 | pk | do_pk | sleeping | 0 | noprefix no_order noalias | normal | combat |
| 347 | pkshow | do_pkshow | sleeping | 0 | deleted | normal | information |
| 348 | coledit | do_coledit | dead | 55 | none | normal | olc |
