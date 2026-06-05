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
#include "globals.h"
#include "interp.h"
#include "recycle.h"
#include "data_table.h"

/*
 * Local Functions
 */

TableSave_Fun(rw_change_data)
{
	rw_table(type, CHANGES_FILE, ChangeData, change);
}

void delete_change(int iChange)
{
	int i, j;
	ChangeData *new_table;

	alloc_mem(new_table, ChangeData, top_change);

	if (!new_table)
	{
		return;
	}

	for (i = 0, j = 0; i < top_change; i++)
	{
		if (i != iChange)
		{
			new_table[j] = change_table[i];
			j++;
		}
	}

	free_mem(change_table);
	change_table = new_table;

	top_change--;

	return;
}

void add_change(const char *argument, const char *name)
{
	ChangeData *new_table;
	int j, i = top_change;

	top_change++;
	alloc_mem(new_table, ChangeData, top_change);

	if (!new_table)
	{
		bug("Memory allocation failed. Brace for impact.");
		return;
	}

	for (j = 0; j < i; j++)
		new_table[j] = change_table[j];

	free_mem(change_table);
	change_table = new_table;

	change_table[i].change = str_dup(argument);
	change_table[i].coder = str_dup(name);
	change_table[i].time = current_time;
	rw_change_data(act_write);
}

void post_changes(CharData * ch, int begin, int end)
{
	char buf[MSL], note[MSL * 2], date[MIL];
	int i;

	if (end >= top_change || begin < 0 || begin > end)
		return;

	note[0] = NUL;
	for (i = begin; i <= end; i++)
	{
		sprintf(buf, "{G%3d) {C%-45s{x\n\r", i, change_table[i].change);
		strcat(note, buf);
	}
	strcat(note, NEWLINE);
	sprintf(date, "Changes (%s)", str_time(-1, -1, "%D"));
	append_to_note(ch, "Announce", ch->name, "All", date, 60, note);
}

void archive_changes(CharData * ch, int begin, int end)
{
	FileData *fp;
	int i;
	int j = 0;
	int old = top_change;
	ChangeData *new_table;
	bool fAuto = (begin == -1 && end == -1);
	char file[MIL];

#define ARCHIVE_TIME ((WEEK * 4) * 3)

	if (!fAuto && (end >= top_change || begin < 0 || begin > end))
	{
		chprintln(ch, "Invalid range.");
		return;
	}

	sprintf(file, "%soldchanges/changes.%s", DATA_DIR,
			str_time(-1, -1, "%H-%M-%S"));
	fp = f_open(file, "w");

	if (!fp)
	{
		bug("NULL fp");
		chprintln(ch, "Error opening archive file.");
		return;
	}

	if (!fAuto)
		f_printf(fp, "%d\n", end - begin);
	else
	{
		begin = 0;
		end = top_change - 1;
		for (i = 0; i < top_change; i++)
			if (current_time - change_table[i].time >= ARCHIVE_TIME)
				j++;

		f_printf(fp, "%d\n", j);
	}
	for (i = begin; i <= end; i++)
	{
		if (!fAuto || current_time - change_table[i].time >= ARCHIVE_TIME)
		{
			f_printf(fp, "#CHANGE\n");
			save_struct(fp, &change_zero, change_data_table,
						&change_table[i]);
			f_printf(fp, "#end\n\n");
		}
	}
	f_printf(fp, "#!\n");

	if (!fAuto)
		top_change = Max(0, top_change - (end - begin) - 1);
	else
		top_change = Max(0, top_change - j);

	alloc_mem(new_table, ChangeData, top_change);

	if (!new_table)
	{
		chprintln(ch, "Unable to remove changes.");
		return;
	}

	for (i = 0, j = 0; i < old; i++)
	{
		if (!fAuto ? (i < begin || i > end) : current_time -
			change_table[i].time < ARCHIVE_TIME)
		{
			new_table[j] = change_table[i];
			j++;
		}
	}

	free_mem(change_table);
	change_table = new_table;

	if (!fAuto)
	{
		add_change(FORMATF
				   ("Changes %d through %d archived.", begin + 1, end + 1),
				   GetName(ch));
		chprintlnf(ch, "Changes %d through %d archived to %s.", begin + 1,
				   end + 1, file);
	}
	else
	{
		add_change(FORMATF("%d changes auto archived.", old - j),
				   GetName(ch));
		chprintlnf(ch, "%d changes auto archived to %s.", old - j, file);
	}
	f_close(fp);

	rw_change_data(act_write);
}

int num_changes(void)
{
	struct tm a, *b;
	int today;
	int i;

	b = localtime(&current_time);
	a = *b;
	today = 0;

	for (i = 0; i < top_change; i++)
	{
		if (change_table[i].time <= 0)
			continue;

		b = localtime(&change_table[i].time);

		if (a.tm_year != b->tm_year)
			continue;

		if (a.tm_mon != b->tm_mon)
			continue;

		if (a.tm_yday != b->tm_yday)
			continue;

		today++;
	}

	return today;
}

Do_Fun(do_changes)
{
	char arg1[MAX_INPUT_LENGTH];
	char arg2[MAX_INPUT_LENGTH];
	Buffer *buf;
	struct tm a, *b;
	int today;
	int i, c = 0, d = top_change;
	bool fToDay;

	argument = one_argument(argument, arg1);
	argument = one_argument(argument, arg2);

	if (IsImmortal(ch))
	{
		if (NullStr(arg1))
		{
			cmd_syntax(ch, NULL, n_fun, "save", "view",
					   "delete <change number>", "add <change>",
					   "edit <change number> <string>",
					   "post <start #> [end #]",
					   "archive auto | <start #> <end #>", NULL);
			return;
		}

		if (!str_cmp(arg1, "add"))
		{
			if (NullStr(arg2))
			{
				chprintln(ch, "Add what change?");
				return;
			}

			if (!NullStr(argument))
			{
				strcat(arg2, " ");
				strcat(arg2, argument);
			}
			add_change(arg2, GetName(ch));
			chprintln(ch, "Change Created.");
			chprintln(ch, "Type 'changes' to see the changes.");
			return;
		}
		if (!str_cmp(arg1, "save"))
		{
			rw_change_data(act_write);
			chprintln(ch, "Changes Saved.");
			return;
		}
		if (!str_cmp(arg1, "post"))
		{
			int begin = 1;
			int end = top_change;

			if (NullStr(arg2) || !is_number(arg2))
			{
				cmd_syntax(ch, NULL, n_fun, "post <start #> [end #]", NULL);
				return;
			}

			begin = atoi(arg2);

			if (!NullStr(argument) && is_number(argument))
				end = atoi(argument);

			if (begin < 1 || begin > top_change || end > top_change
				|| end < 1)
			{
				chprintln(ch, "Are you purposly trying to crash the mud?");
				return;
			}
			post_changes(ch, begin - 1, end - 1);
			return;
		}

		if (!str_cmp(arg1, "archive"))
		{
			int begin = 1;
			int end = top_change;

			if (NullStr(arg2)
				|| (str_cmp(arg2, "auto")
					&& (!is_number(arg2) || NullStr(argument)
						|| !is_number(argument))))
			{
				cmd_syntax(ch, NULL, n_fun, "archive <start #> <end #>",
						   NULL);
				return;
			}

			if (!str_cmp(arg2, "auto"))
			{
				archive_changes(ch, -1, -1);
				return;
			}

			begin = atoi(arg2);
			end = atoi(argument);

			if (begin < 1 || begin > top_change || end > top_change
				|| end < 1)
			{
				chprintln(ch, "Are you purposly trying to crash the mud?");
				return;
			}
			archive_changes(ch, begin - 1, end - 1);
			return;
		}

		if (!str_cmp(arg1, "edit"))
		{
			int num;

			if (NullStr(arg2) || !is_number(arg2))
			{
				chprintln(ch,
						  "You must provide the number of the change you want to edit.");
				return;
			}

			num = atoi(arg2);

			if (num < 1 || num > top_change)
			{
				chprintlnf(ch, "Valid changes are from 1 to %d.", top_change);
				return;
			}

			if (NullStr(argument))
			{
				chprintln(ch, "Want to you want the change to say?");
				return;
			}

			replace_str(&change_table[num - 1].change, argument);
			chprintln(ch, "Change edited.");
			rw_change_data(act_write);
			return;
		}

		if (!str_cmp(arg1, "delete"))
		{
			int num;

			if (NullStr(arg2) || !is_number(arg2))
			{
				chprintlnf(ch,
						   "{wFor %s delete, you must provide a change number.{x",
						   n_fun);
				cmd_syntax(ch, NULL, n_fun, "delete (change number)", NULL);
				return;
			}

			num = atoi(arg2);
			if (num < 1 || num > top_change)
			{
				chprintlnf(ch, "Valid changes are from 1 to %d.", top_change);
				return;
			}
			delete_change(num - 1);
			chprintln(ch, "Change deleted.");
			return;
		}
		if (str_cmp(arg1, "view"))
		{
			do_changes(n_fun, ch, "");
			return;
		}
		else
		{
			strcpy(arg1, arg2);
			strcpy(arg2, argument);
		}
	}

	if (top_change < 1)
	{
		chprintln(ch, "No changes found.");
		return;
	}

	if (NullStr(arg1))
		c = top_change - 16;
	else if (is_number(arg1))
	{
		c = Max(c, atoi(arg1) - 1);
		if (!NullStr(arg2) && is_number(arg2))
		{
			d = Min(atoi(arg2), d);
		}
		if (d <= c)
		{
			chprintln(ch, "First number must be lower than the second.");
			return;
		}
	}
	else
	{
		chprintln(ch, "Invalid argument.");
		return;
	}

	b = localtime(&current_time);
	a = *b;
	fToDay = false;
	buf = new_buf();
	bprintln(buf, "{wNo.  Coder        Date        Change{R");
	bprintln(buf, draw_line(ch, NULL, 0));
	for (i = c; i < d; i++)
	{
		if (change_table[i].time > 0)
		{
			b = localtime(&change_table[i].time);

			if (a.tm_year == b->tm_year && a.tm_mon == b->tm_mon
				&& a.tm_yday == b->tm_yday)
			{
				fToDay = true;
			}
		}
		bprintf(buf, "{g[{R%3d{g]{w %-9.9s %s%-8.8s {w", (i + 1),
				change_table[i].coder, fToDay ? "{C" : "{c",
				str_time(change_table[i].time, GetTzone(ch), "%D"));

		bprintln(buf, change_table[i].change);
		fToDay = false;
	}
	bprintlnf(buf, "{R%s", draw_line(ch, NULL, 0));
	bprintlnf(buf,
			  "{wThere is a total of {g[ {Y%3d {g] {wchanges in the database.{x",
			  top_change);
	bprintln(buf,
			 "{wAlso see: '{Cchanges <number> [number]{w' to display specific changes.{x");
	bprintlnf(buf, "{R%s", draw_line(ch, NULL, 0));
	if ((today = num_changes()) > 0)
	{
		bprintlnf(buf,
				  "{wThere is a total of {g[ {Y%2d {g] {wnew changes that have been added today.{x",
				  today);
		bprint(buf, "{R");
		bprintln(buf, draw_line(ch, NULL, 0));
	}
	sendpage(ch, buf_string(buf));
	free_buf(buf);
	return;
}
