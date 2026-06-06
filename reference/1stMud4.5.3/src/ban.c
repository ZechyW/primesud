/**************************************************************************
*  Original Diku Mud copyright (C) 1990, 1991 by Sebastian Hammer,        *
*  Michael Seifert, Hans Henrik St{rfeldt, Tom Madsen, and Katja Nyboe.   *
*                                                                         *
*  Merc Diku Mud improvements copyright (C) 1992, 1993 by Michael         *
*  Chastain, Michael Quan, and Mitchell Tse.                              *
*                                                                         *
*  In order to use any part of this Merc Diku Mud, you must comply with   *
*  both the original Diku license in 'license.doc' as well the Merc       *
*  license in 'license.txt'.  In particular, you may not remove either of *
*  these copyright notices.                                               *
*                                                                         *
*  Much time and thought has gone into this software and you are          *
*  benefiting.  We hope that you share your changes too.  What goes       *
*  around, comes around.                                                  *
***************************************************************************
*       ROM 2.4 is copyright 1993-1998 Russ Taylor                        *
*       ROM has been brought to you by the ROM consortium                 *
*           Russ Taylor (rtaylor@hypercube.org)                           *
*           Gabrielle Taylor (gtaylor@hypercube.org)                      *
*           Brian Moore (zump@rom.org)                                    *
*       By using this code, you have agreed to follow the terms of the    *
*       ROM license, in the file Rom24/doc/rom.license                    *
***************************************************************************
*          1stMud ROM Derivative (c) 2001-2004 by Markanth                *
*            http://www.firstmud.com/  <markanth@firstmud.com>            *
*         By using this code you have agreed to follow the term of        *
*             the 1stMud license in ../doc/1stMud/LICENSE                 *
***************************************************************************/

#include "merc.h"
#include "recycle.h"
#include "interp.h"
#include "data_table.h"

DataTable ban_data_table[] = {
	{"name", FIELD_STRING, (void *) &ban_zero.name, NULL, NULL},
	{"level", FIELD_INT, (void *) &ban_zero.level, NULL, NULL},
	{"flags", FIELD_FLAGVECTOR, (void *) &ban_zero.ban_flags, NULL, NULL},
	{NULL, (field_t) - 1, NULL, NULL, NULL}
};

TableSave_Fun(rw_ban_data)
{
	rw_list(type, BAN_FILE, BanData, ban);
}

bool check_ban(const char *site, int type)
{
	BanData *pban;
	char host[MAX_STRING_LENGTH];

	strcpy(host, capitalize(site));
	host[0] = tolower(host[0]);

	for (pban = ban_first; pban != NULL; pban = pban->next)
	{
		if (!IsSet(pban->ban_flags, type))
			continue;

		if (wild_match(pban->name, host))
			return true;
	}

	return false;
}

void ban_site(CharData * ch, const char *argument)
{
	char arg1[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH];
	Buffer *buffer;
	BanData *pban, *prev;
	int type;

	argument = one_argument(argument, arg1);
	argument = one_argument(argument, arg2);

	if (NullStr(arg1))
	{
		if (ban_first == NULL)
		{
			chprintln(ch, "No sites banned at this time.");
			return;
		}
		buffer = new_buf();

		bprintln(buffer, "Banned sites  level  type");
		for (pban = ban_first; pban != NULL; pban = pban->next)
		{
			bprintlnf(buffer, "%-12s    %-3d  %s", pban->name, pban->level,
					  IsSet(pban->ban_flags,
							BAN_NEWBIES) ? "newbies" : IsSet(pban->ban_flags,
															 BAN_PERMIT) ?
					  "permit" : IsSet(pban->ban_flags,
									   BAN_ALL) ? "all" : "");
		}

		sendpage(ch, buf_string(buffer));
		free_buf(buffer);
		return;
	}

	if (NullStr(arg2) || !str_prefix(arg2, "all"))
		type = BAN_ALL;
	else if (!str_prefix(arg2, "newbies"))
		type = BAN_NEWBIES;
	else if (!str_prefix(arg2, "permit"))
		type = BAN_PERMIT;
	else
	{
		chprintln(ch, "Acceptable ban types are all, newbies, and permit.");
		return;
	}

	if (strlen(arg1) == 0)
	{
		chprintln(ch, "You have to ban SOMETHING.");
		return;
	}

	prev = NULL;
	for (pban = ban_first; pban != NULL; pban = prev)
	{
		prev = pban->next;

		if (!str_cmp(arg1, pban->name))
		{
			if (pban->level > get_trust(ch))
			{
				chprintln(ch, "That ban was set by a higher power.");
				return;
			}
			else
			{
				UnLink(pban, ban, next, prev);
				free_ban(pban);
			}
		}
	}

	pban = new_ban();
	pban->name = str_dup(arg1);
	pban->level = get_trust(ch);

	pban->ban_flags = type;

	Link(pban, ban, next, prev);
	rw_ban_data(act_write);
	chprintlnf(ch, "%s has been banned.", pban->name);
	return;
}

Do_Fun(do_ban)
{
	ban_site(ch, argument);
}

Do_Fun(do_allow)
{
	char arg[MAX_INPUT_LENGTH];
	BanData *prev;
	BanData *curr;

	one_argument(argument, arg);

	if (NullStr(arg))
	{
		chprintln(ch, "Remove which site from the ban list?");
		return;
	}

	prev = NULL;
	for (curr = ban_first; curr != NULL; curr = prev)
	{
		prev = curr->next;

		if (!str_cmp(arg, curr->name))
		{
			if (curr->level > get_trust(ch))
			{
				chprintln(ch,
						  "You are not powerful enough to lift that ban.");
				return;
			}
			UnLink(curr, ban, next, prev);

			free_ban(curr);
			chprintlnf(ch, "Ban on %s lifted.", arg);
			rw_ban_data(act_write);
			return;
		}
	}

	chprintln(ch, "Site is not banned.");
	return;
}
