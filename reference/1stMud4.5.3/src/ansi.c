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
#include "tables.h"
#include "interp.h"
#include "recycle.h"
#include "data_table.h"
#include "olc.h"

bool is_ansi_printed_char(char c)
{
	switch (c)
	{
		case ' ':
		case '-':
		case COLORCODE:
			return true;
		default:
			return false;
	}
}

int ansi_skip(const char *pstr)
{
	int i = 0;
	const char *str = pstr;

	if (*str != COLORCODE)
		return i;

	str++;
	i++;

	if (isdigit(*str))
	{
		str++;
		i++;
		if (*str == '+')
		{
			str++;
			i++;
		}
		else
			return i;
	}

	if (*str == '=')
	{
		str++;
		i++;
	}

	switch (*str)
	{
		case 'T':
		case 't':
			str += 3;
			i += 3;
			do
			{
				str++;
				i++;
			}
			while (*str && *str != '"');
			break;
		default:
			break;
	}

	return i;
}

char *make_custom_color(int slot)
{
	return FORMATF("%s%d%s", CSSTR, slot, CESTR);
}

color_value_t random_color(color_attr_t att)
{
	switch (att)
	{
		case CT_ATTR:
			return (color_value_t) number_range(CL_NONE, CL_BRIGHT);
		case CT_FORE:
			return (color_value_t) number_range(FG_RED, FG_WHITE);
		case CT_BACK:
			return (color_value_t) number_range(BG_RED, BG_WHITE);
		default:
			return CL_NONE;
	}
}

void convert_random(colatt_t * col)
{
	int i;

	for (i = 0; i < CT_MAX; i++)
		if (getcol(col, i) == CL_RANDOM)
			getcol(col, i) = random_color((color_attr_t) i);

	if (VALID_FG(getcol(col, CT_SAVE)))
	{
		if (VALID_FG(getcol(col, CT_FORE)))
			getcol(col, CT_BACK) =
				(color_value_t) (getcol(col, CT_FORE) + CL_MOD);

		getcol(col, CT_FORE) = (color_value_t) (getcol(col, CT_SAVE));
	}

	if (VALID_CL(getcol(col, CT_SAVE)))
		getcol(col, CT_ATTR) = getcol(col, CT_SAVE);

	getcol(col, CT_SAVE) = CL_MOD;
}

char *make_color(CharData * ch, colatt_t * col)
{
	int len = 0;
	char code[100];

	convert_random(col);

	if (ch)
	{
		if (getcol(col, CT_ATTR) == CL_BLINK)
		{
			if (VT100_SET(ch, NO_BLINKING))
				getcol(col, CT_ATTR) = CL_NONE;
		}
		if (getcol(col, CT_FORE) == FG_BLACK)
		{
			if (VT100_SET(ch, DARK_MOD))
				getcol(col, CT_ATTR) = CL_BRIGHT;
		}
		if (getcol(col, CT_ATTR) == CL_BRIGHT)
		{
			if (VT100_SET(ch, DARK_COLORS))
				getcol(col, CT_ATTR) = CL_NONE;
		}
	}

	if (!VT100_SET(ch, BROKEN_ANSI))
	{
		if (VALID_CL(getcol(col, CT_ATTR)))
			len = sprintf(code + len, ";%d", getcol(col, CT_ATTR));
		if (VALID_FG(getcol(col, CT_FORE)))
			len = sprintf(code + len, ";%d", getcol(col, CT_FORE));
		if (VALID_BG(getcol(col, CT_BACK)))
			len = sprintf(code + len, ";%d", getcol(col, CT_BACK));

		if (len > 0)
			return FORMATF(ESC "[%sm", code + 1);
		else
		{
			bug("make_color(): invalid color value(s)");
			return "";
		}
	}
	else
	{
		if (!VALID_CL(getcol(col, CT_ATTR)))
			getcol(col, CT_ATTR) = CL_NONE;
		if (!VALID_FG(getcol(col, CT_FORE)))
			getcol(col, CT_FORE) = FG_WHITE;
		if (!VALID_BG(getcol(col, CT_BACK)))
			getcol(col, CT_BACK) = BG_BLACK;
		return FORMATF(ESC "[%d;%d;%dm", getcol(col, CT_ATTR),
					   getcol(col, CT_FORE), getcol(col, CT_BACK));
	}
}

void set_col_attr(char c, colatt_t * col, CharData * ch)
{
	int z;

	switch (c)
	{
		case '?':
		case '`':
			getcol(col, CT_ATTR) = CL_RANDOM;
			getcol(col, CT_FORE) = FG_RANDOM;
			break;
		case 'z':
			getcol(col, CT_ATTR) = CL_RANDOM;
			getcol(col, CT_BACK) = BG_RANDOM;
			break;
		case 'Z':
			for (z = 0; z < CT_MAX; z++)
				getcol(col, z) = CL_RANDOM;
			break;
		case 'b':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_BLUE;
			break;
		case 'c':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_CYAN;
			break;
		case 'g':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_GREEN;
			break;
		case 'm':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_MAGENTA;
			break;
		case 'd':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_BLACK;
			break;
		case 'r':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_RED;
			break;
		case 'y':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_YELLOW;
			break;
		case 'w':
			getcol(col, CT_ATTR) = CL_NONE;
			getcol(col, CT_FORE) = FG_WHITE;
			break;
		case 'B':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_BLUE;
			break;
		case 'C':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_CYAN;
			break;
		case 'G':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_GREEN;
			break;
		case 'M':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_MAGENTA;
			break;
		case 'D':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_BLACK;
			break;
		case 'R':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_RED;
			break;
		case 'W':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_WHITE;
			break;
		case 'Y':
			getcol(col, CT_ATTR) = CL_BRIGHT;
			getcol(col, CT_FORE) = FG_YELLOW;
			break;
		default:
			break;
	}
}

char *colorize(const char *str)
{
	static int c;
	static char out[4][MSL];
	char *result;
	size_t a, b = 0;

	if (NullStr(str))
		return "{?";

	++c, c %= 4;
	result = out[c];

	for (a = 0; str[a] != NUL; a++)
	{
		if (str[a] == COLORCODE)
		{
			a += ansi_skip(&str[a]);
			continue;
		}
		else if (str[a] == CUSTOMSTART)
		{
			do
			{
				a++;
			}
			while (str[a] != CUSTOMEND);
			a++;
			continue;
		}
		else if (str[a] == MXP_BEGc)
		{
			do
			{
				a++;
			}
			while (str[a] != MXP_ENDc);
			a++;
			continue;
		}
		result[b++] = COLORCODE;
		result[b++] = '?';
		result[b++] = str[a];
	}
	result[b++] = COLORCODE;
	result[b++] = 'x';
	result[b++] = NUL;
	return (result);
}

void goto_xy(CharData * ch, int col, int row)
{
	chprintf(ch, ESC "[%u;%uH", row, col);
}

void clear_window(CharData * ch)
{
	chprint(ch, ESC "[r");
}

void clear_screen(CharData * ch)
{
	chprint(ch, ESC "[2J");
}

void set_default_color(colatt_t * color, int slot, ColorTemplate * scheme)
{
	int i = 0;
	ColorTemplate *v = !scheme ? default_color_scheme : scheme;

	if (slot == _NONE)
	{
		copy_colors(color, v->colors);
	}
	else
	{
		for (i = 0; i < MAX_CUSTOM_COLOR; i++)
		{
			if (color_table[i].slot == slot)
			{
				copy_color(color[slot], v->colors[slot]);
				break;
			}
		}
	}

	return;
}

void default_color(CharData * ch, int slot)
{
	if (!ch || IsNPC(ch))
		return;

	if (!ch->pcdata->color_scheme)
	{
		if (!default_color_scheme)
			create_default_color_scheme();

		ch->pcdata->color_scheme = default_color_scheme;
	}

	if (!ch->pcdata->colors)
	{
		alloc_mem(ch->pcdata->colors, colatt_t, MAX_CUSTOM_COLOR);

		copy_colors(ch->pcdata->colors, ch->pcdata->color_scheme->colors);
	}

	set_default_color(ch->pcdata->colors, slot, ch->pcdata->color_scheme);
}

Lookup_Fun(color_lookup)
{
	int i;

	if (NullStr(name))
		return -1;

	for (i = 0; i < MAX_CUSTOM_COLOR; i++)
		if (!str_prefix(name, color_table[i].name))
			return i;

	return -1;
}

void color_convert_prefix(char colcode, char *text)
{
	char buf[MIL * 2];
	bool moved = false;
	char *src = text;
	char *dest = text;

	assert(colcode != COLORCODE);

	for (; *src;)
	{
		if (*src == COLORCODE)
		{
			if (!moved)
			{
				strcpy(buf, src);
				src = buf;
				moved = true;
			}
			*dest++ = *src;
			*dest++ = *src++;
			continue;
		}

		if (*src == colcode)
		{
			src++;

			if (*src == NUL)
			{
				*dest++ = COLORCODE;
				*dest = NUL;
				return;
			};

			if (*src == colcode)
			{
				*dest++ = *src++;
				continue;
			}

			*dest++ = COLORCODE;
			*dest++ = *src++;
			continue;
		}
		*dest++ = *src++;
	}

	*dest = NUL;
}

void create_default_color_scheme(void)
{
	int i;

	if (!default_color_scheme)
		default_color_scheme = new_color_template();

	for (i = 0; i < MAX_CUSTOM_COLOR; i++)
	{
		copy_color(default_color_scheme->colors[color_table[i].slot],
				   color_table[i].col_attr);
	}

	default_color_scheme->name = str_dup(color_scheme_default_name);
	default_color_scheme->description =
		str_dup(color_scheme_default_descript);
	Link(default_color_scheme, color_template, next, prev);
}

ColorTemplate *find_color_template(const char *template_name)
{
	ColorTemplate *result;

	// first do an exact search
	for (result = color_template_first; result; result = result->next)
	{
		if (!str_cmp(result->name, template_name))
		{
			return result;
		}
	}

	// do a count search
	if (is_number(template_name))
	{
		int count = atoi(template_name);
		for (result = color_template_first; result; result = result->next)
		{
			if (--count < 1)
			{
				return result;
			}
		}
		return NULL;
	}

	// try a prefix match next
	for (result = color_template_first; result; result = result->next)
	{
		if (!str_prefix(result->name, template_name))
		{
			return result;
		}
	}
	return NULL;
}

Do_Fun(custom_color_list)
{
	ColorTemplate *pct;
	int count = 0;

	chprintln(ch, stringf(ch, 0, Center, "-=", " COLOR SCHEMES "));

	for (pct = color_template_first; pct; pct = pct->next)
	{

		chprintlnf(ch, "[%2d] %-15s: %s", ++count, pct->name,
				   pct->description);
	}

	chprintln(ch, draw_line(ch, "-=", 0));
}

Do_Fun(custom_color_use)
{
	ColorTemplate *new_scheme;

	if (NullStr(argument))
	{
		chprintln(ch,
				  "Syntax: color use <scheme/template name>   (as per color list)");
		chprintln(ch,
				  "Syntax: color use <scheme/template number> (as per color list)");
		return;
	}
	new_scheme = find_color_template(argument);

	if (!new_scheme)
	{
		chprintlnf(ch, "Could not find scheme/template '%s'", argument);
		return;
	}
	ch->pcdata->color_scheme = new_scheme;
	copy_colors(ch->pcdata->colors, new_scheme->colors);
	chprintlnf(ch, "Base color scheme changed to '%s'", new_scheme->name);
}

Do_Fun(custom_color_savescheme)
{
	ColorTemplate *new_scheme;

	if (NullStr(argument))
	{
		chprintln(ch, "Syntax: color savescheme <name of new scheme>");
		return;
	}
	new_scheme = find_color_template(argument);
	if (new_scheme)
	{
		chprintlnf(ch,
				   "There already exists a scheme '%s', you need something more unique.",
				   new_scheme->name);
		return;
	}

	new_scheme = new_color_template();

	alloc_mem(new_scheme->colors, colatt_t, MAX_CUSTOM_COLOR);

	copy_colors(new_scheme->colors, ch->pcdata->colors);

	new_scheme->name = str_dup(argument);

	new_scheme->description = str_dupf("A scheme by %s", ch->name);

	Link(new_scheme, color_template, next, prev);

	chprintln(ch,
			  "Scheme created, use 'color description' to set a description for the scheme.");
	rw_color_template_data(act_write);
	chprintln(ch, "Colour schemes/templates saved");
}

Do_Fun(custom_color_replacescheme)
{
	ColorTemplate *new_scheme;

	if (NullStr(argument))
	{
		chprintln(ch,
				  "Syntax: color replacescheme <scheme/template number>  (as per color list)");
		return;
	}
	new_scheme = find_color_template(argument);
	if (!new_scheme)
	{
		chprintlnf(ch, "Could not find scheme/template '%s' to replace",
				   argument);
		return;
	}

	copy_colors(new_scheme->colors, ch->pcdata->colors);
	rw_color_template_data(act_write);
	chprintlnf(ch, "Replaced scheme '%s'.", new_scheme->name);
	chprintln(ch, "Colour schemes/templates resaved");
}

Do_Fun(custom_color_description)
{
	ColorTemplate *new_scheme;
	char arg[MIL];

	argument = one_argument(argument, arg);

	if (NullStr(argument))
	{
		chprintln(ch,
				  "Syntax: color descript <scheme/template number> new description");
		return;
	}
	if (!is_number(arg))
	{
		chprintln(ch, "You must specify a scheme by its number.");
		return;
	}
	new_scheme = find_color_template(arg);
	if (!new_scheme)
	{
		chprintlnf(ch,
				   "Could not find scheme/template '%s' to change the description of.",
				   argument);
		return;
	}

	chprintlnf(ch, "Colour schemes '%s' description '%s' replaced with '%s'",
			   new_scheme->name, new_scheme->description,
			   capitalize(argument));

	replace_str(&new_scheme->description, capitalize(argument));

	rw_color_template_data(act_write);
	chprintln(ch, "Colour schemes/templates resaved");
}

Do_Fun(custom_color_rename)
{
	ColorTemplate *new_scheme, *dup;
	char arg[MIL];

	argument = one_argument(argument, arg);

	if (NullStr(argument))
	{
		chprintln(ch,
				  "Syntax: color rename <scheme/template number> new name");
		return;
	}
	if (!is_number(arg))
	{
		chprintln(ch, "You must specify a scheme by its number.");
		return;
	}
	new_scheme = find_color_template(arg);
	if (!new_scheme)
	{
		chprintlnf(ch, "Could not find scheme/template '%s' to rename.",
				   argument);
		return;
	}

	dup = find_color_template(argument);
	if (dup)
	{
		chprintlnf(ch,
				   "There already exists a scheme '%s', you need something more unique.",
				   dup->name);
		return;
	}

	chprintlnf(ch, "Colour schemes '%s' description '%s' renamed to '%s'",
			   new_scheme->name, new_scheme->description, argument);
	replace_str(&new_scheme->name, argument);

	rw_color_template_data(act_write);
	chprintln(ch, "Colour schemes/templates resaved");
}

Do_Fun(custom_color_prefix)
{
	if (argument[0] == COLORCODE && argument[1] == COLORCODE)
	{
		((char *) argument)[1] = '\0';
	}

	if (strlen(argument) > 1 || NullStr(argument))
	{
		chprintln(ch, "syntax: color prefix <color prefix character>");
		chprintln(ch, "This command is used to specify which character you ");
		chprintln(ch, "want to prefix color codes with.");
		if (ch->color_prefix != COLORCODE)
		{
			chprintlnf(ch, "Your current color code prefix is set to %c%c",
					   ch->color_prefix, ch->color_prefix);
		}
		else
		{
			chprintln(ch, "Your current color code prefix is unset,");
			chprintlnf(ch,
					   " therefore you should prefix colors with the default %c%c",
					   COLORCODE, COLORCODE);
		}
		return;
	}

	chprintlnf(ch, "Colour code prefix changed from %c%c to %s",
			   ch->color_prefix, ch->color_prefix, argument);

	ch->color_prefix = *argument;
}

Do_Fun(custom_color_on)
{
	if (!ch || IsNPC(ch) || !ch->desc)
		return;

	SetBit(ch->desc->desc_flags, DESC_COLOR);
	RemBit(ch->comm, COMM_NOCOLOR);
	chprintln(ch, colorize("Color is now ON!"));
}

Do_Fun(custom_color_off)
{
	if (!ch || IsNPC(ch) || !ch->desc)
		return;

	chprintln(ch, casemix("Color is now OFF, <sigh>"));
	RemBit(ch->desc->desc_flags, DESC_COLOR);
	SetBit(ch->comm, COMM_NOCOLOR);
}

Do_Fun(custom_color_options)
{
	flag_t vf;
	const char *name;

	if (NullStr(argument))
	{
		print_all_on_off(ch, vt100_flags, ch->pcdata->vt100);
		return;
	}

	if ((vf = flag_value(vt100_flags, argument)) == NO_FLAG)
	{
		chprintln(ch, "Invalid option.");
		return;
	}

	name = capitalize(flag_string(vt100_flags, vf));
	set_on_off(ch, &ch->pcdata->vt100, vf, FORMATF("%s ON.", name),
			   FORMATF("%s OFF.", name));
	return;
}

Do_Fun(custom_color_colors)
{
	int i, j = 0, k = 0;

	chprintln(ch, "Attributes       Foregrounds      Backgrounds");
	chprintln(ch, draw_line(ch, NULL, 58));
	for (i = 0; color_attributes[i].name != NULL; i++)
	{
		chprintf(ch, "%-15s  ", Upper(color_attributes[i].name));
		if (color_foregrounds[j].name != NULL)
			chprintf(ch, "%-15s  ", Upper(color_foregrounds[j++].name));
		else
			chprintf(ch, "%-15s  ", " ");
		if (color_backgrounds[k].name != NULL)
			chprintlnf(ch, "%s", Upper(color_backgrounds[k++].name));
		else
			chprintln(ch, NULL);
	}
	while (color_foregrounds[j].name != NULL)
	{
		chprintf(ch, "%-15s  %-15s  ", " ",
				 Upper(color_foregrounds[j++].name));
		if (color_backgrounds[k].name != NULL)
			chprintlnf(ch, "%s", Upper(color_backgrounds[k++].name));
		else
			chprintln(ch, NULL);
	}
	while (color_backgrounds[k].name != NULL)
		chprintlnf(ch, "%-15s  %-15s  %s", " ", " ",
				   Upper(color_backgrounds[k++].name));
	chprintln(ch, draw_line(ch, NULL, 58));
}

char *format_color(colatt_t col)
{
	static char buf[3][MSL];
	static int i;
	char *r;

	++i, i %= 3;
	r = buf[i];

	if (VALID_BG(col[CT_BACK]))
	{
		strcpy(r, flag_string(color_backgrounds, col[CT_BACK]));
		strcat(r, " background");
	}
	else
	{
		strcpy(r, flag_string(color_attributes, col[CT_ATTR]));
		if (VALID_FG(col[CT_FORE]))
		{
			strcat(r, " ");
			strcat(r, flag_string(color_foregrounds, col[CT_FORE]));
		}
	}
	return r;
}

bool compare_colors(colatt_t * a, colatt_t * b)
{
	int i;

	for (i = 0; i < CT_MAX; i++)
		if (getcol(a, i) != getcol(b, i))
			return false;

	return true;
}

void show_colors_to_char(CharData * ch, CharData * v)
{
	Column Cd;
	Buffer *output;
	int i;

	output = new_buf();
	set_cols(&Cd, ch, 2, COLS_BUF, output);

	bprintln(output, stringf(ch, 0, Center, "-=", "[ CUSTOM COLORS ]"));

	for (i = 0; i < MAX_CUSTOM_COLOR; i++)
	{
		if (IsSet(color_table[i].flags, COLOR_IMMORTAL) && !IsImmortal(ch))
			continue;

		print_cols(&Cd, "%2d) %s%-10s{x: %s%s", i + 1, make_custom_color(i),
				   color_table[i].name, !compare_colors(&v->pcdata->colors[i],
														&v->
														pcdata->color_scheme->colors
														[i]) ? "{G*{x" : " ",
				   color_table[i].description);
	}
	cols_nl(&Cd);

	bprintln(output, draw_line(ch, NULL, 0));
	if (v == ch)
		bprintlnf(output, "\tCurrent color scheme in use: {W%s{x.",
				  v->pcdata->color_scheme->name);
	else
		bprintlnf(output, "\t%s's current color scheme: {W%s{x.", Pers(v, ch),
				  v->pcdata->color_scheme->name);
	bprintln(output,
			 "A {G*{x symbol means the custom color is different than the current scheme.");
	sendpage(ch, buf_string(output));
	free_buf(output);
}

Do_Fun(custom_color_show)
{
	CharData *v;

	if (NullStr(argument) || (v = get_char_world(ch, argument)) == NULL
		|| IsNPC(v))
	{
		v = ch;
	}

	show_colors_to_char(ch, v);
}

void show_scheme_to_char(CharData * ch, CharData * v, ColorTemplate * scheme)
{
	Column Cd;
	Buffer *output;
	int i;
	colatt_t *col = scheme->colors;

	output = new_buf();
	set_cols(&Cd, ch, 2, COLS_BUF, output);

	bprintln(output,
			 stringf(ch, 0, Center, "-=", "[ %s Color Scheme ]",
					 scheme->name));

	for (i = 0; i < MAX_CUSTOM_COLOR; i++)
	{
		if (IsSet(color_table[i].flags, COLOR_IMMORTAL) && !IsImmortal(ch))
			continue;

		print_cols(&Cd, "%2d) %s%-10s{x: %s%s", i + 1,
				   make_color(NULL, &col[i]), color_table[i].name,
				   !compare_colors(&col[i],
								   &v->pcdata->colors[i]) ? "{G*{x" : " ",
				   color_table[i].description);
	}
	cols_nl(&Cd);

	bprintln(output, draw_line(ch, NULL, 0));
	if (scheme != v->pcdata->color_scheme)
		bprintlnf(output, "%s is using the %s color scheme.", v->name,
				  scheme->name);
	bprintln(output,
			 "A {G*{x symbol means the custom color is different than the current scheme.");
	sendpage(ch, buf_string(output));
	free_buf(output);
}

Do_Fun(custom_scheme_show)
{
	CharData *v;
	ColorTemplate *sch;
	char name[MIL];

	argument = one_argument(argument, name);

	if (NullStr(name))
	{
		cmd_syntax(ch, NULL, n_fun, "[player] and/or [scheme]", NULL);
		return;
	}

	if ((v = get_char_world(ch, name)) == NULL || IsNPC(v))
	{
		if ((sch = find_color_template(name)) == NULL)
		{
			chprintln(ch, "No such player or color scheme.");
			return;
		}
		v = ch;
	}
	else
	{
		sch = v->pcdata->color_scheme;
	}
	show_scheme_to_char(ch, v, sch);
}

Do_Fun(custom_color_reset)
{
	copy_colors(ch->pcdata->colors, ch->pcdata->color_scheme->colors);

	chprintlnf(ch, "Custom colors reset to %s scheme.",
			   ch->pcdata->color_scheme->name);
}

bool set_custom_color(const char *n_fun, CharData * ch, colatt_t * col,
					  const char *argument)
{
	int i, val;
	FlagTable *ctable = color_attributes;
	const char *cname = "";
	char temp[MIL];

	argument = one_argument(argument, temp);

	if (NullStr(temp))
	{
		chprintln(ch, "You must specify an attribute to set.");
		return false;
	}
	for (i = 0; i < CT_MAX; i++)
	{
		if (NullStr(temp))
		{
			break;
		}

		switch (i)
		{
			case CT_ATTR:
				ctable = color_attributes;
				cname = "attribute";
				break;
			case CT_FORE:
				ctable = color_foregrounds;
				cname = "foreground";
				break;
			case CT_BACK:
				ctable = color_backgrounds;
				cname = "background";
				break;
			default:
				chprintln(ch, "error");
				return false;
		}

		if ((val = flag_value(ctable, temp)) == NO_FLAG)
		{
			chprintlnf(ch, "Invalid %s color.", cname);
			break;
		}

		getcol(col, i) = (color_value_t) val;

		chprintlnf(ch, "%s %s set to %s.", n_fun, cname,
				   flag_string(ctable, getcol(col, i)));

		argument = one_argument(argument, temp);
	}

	while (i < CT_MAX)
	{
		getcol(col, i) = CL_NONE;
		i++;
	}

	getcol(col, CT_SAVE) = CL_MOD;

	return true;
}

Do_Fun(custom_color_set)
{
	char arg[MIL];
	int pos;

	argument = one_argument(argument, arg);

	if (NullStr(arg) || (pos = color_lookup(arg)) == -1)
	{
		chprintln(ch, "Invalid custom color to set.");
		return;
	}

	set_custom_color(color_table[pos].name, ch,
					 &ch->pcdata->colors[color_table[pos].slot], argument);
}

struct custom_color_cmd_type
{
	const char *name;
	Do_F *do_fun;
	int level;
	const char *syntax;
};

const struct custom_color_cmd_type custom_color_cmd_table[] = {
	{"show", custom_color_show, 0, "Shows your current color scheme."},
	{"showscheme", custom_scheme_show, 0,
	 "Shows another persons color scheme."},
	{"set", custom_color_set, 0,
	 "Sets a particular color in your color scheme."},
	{"prefix", custom_color_prefix, 0,
	 "Sets a particular character to be used to prefix color codes."},
	{"reset", custom_color_reset, 0, "Resets all color customizations."},
	{"list", custom_color_list, 0, "Lists all the mud color templates."},
	{"use", custom_color_use, 0, "Use a particular color scheme/template."},
	{"on", custom_color_on, 0, "Turn on your color."},
	{"off", custom_color_off, 0, "Turn off your color."},
	{"options", custom_color_options, 0, "Sets various display options."},
	{"colors", custom_color_colors, 0,
	 "List colors (attributes, foregrounds, backgrounds)"},
	{"savescheme", custom_color_savescheme, LEVEL_IMMORTAL,
	 "Save your current color settings as a scheme."},
	{"replacescheme", custom_color_replacescheme, LEVEL_IMMORTAL,
	 "Replace a current scheme with your scheme."},
	{"description", custom_color_description, LEVEL_IMMORTAL,
	 "Replace the description of a current scheme."},
	{"rename", custom_color_rename, LEVEL_IMMORTAL, "Rename a scheme."},
	{NULL, NULL, 0, ""}
};

Do_Fun(do_color)
{
	char arg[MIL];
	int i;

	if (!ch->desc)
	{
		chprintln(ch,
				  "You must have an active connection to use this command.");
		return;
	}

	argument = one_argument(argument, arg);
	if (NullStr(arg))
	{
		chprintlnf(ch, "%s Customing Colour System", mud_info.name);
		chprintln(ch, "Syntax:");
		for (i = 0; !NullStr(custom_color_cmd_table[i].name); i++)
		{
			if (custom_color_cmd_table[i].level > get_trust(ch))
			{
				continue;
			}
			chprintlnf(ch, "  color %-15s - %s",
					   custom_color_cmd_table[i].name,
					   custom_color_cmd_table[i].syntax);
		}
		return;
	}

	// find the command
	for (i = 0; !NullStr(custom_color_cmd_table[i].name); i++)
	{
		if (custom_color_cmd_table[i].level > get_trust(ch))
		{
			continue;
		}

		if (!str_prefix(arg, custom_color_cmd_table[i].name))
		{
			// found the command
			break;
		}
	}
	if (NullStr(custom_color_cmd_table[i].name))
	{
		chprintlnf(ch, "Unrecognised Custom Colour command '%s'", arg);
		do_color(n_fun, ch, "");
		return;
	}

	(*custom_color_cmd_table[i].do_fun) (custom_color_cmd_table[i].name, ch,
										 argument);
}
