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

#ifndef __CHARACTER_H_
#define __CHARACTER_H_

int chprint(CharData * ch, const char *txt)
{
	if (!NullStr(txt) && ch && ch->desc != NULL)
		return d_print(ch->desc, txt);

	return 0;
}

int chprintln(CharData * ch, const char *txt)
{
	if (ch && ch->desc != NULL)
		return d_println(ch->desc, txt);
	return 0;
}

int chprintf(CharData * ch, const char *fmt, ...)
{
	char buf[MPL];
	va_list args;

	if (NullStr(fmt) || !ch->desc)
		return 0;

	va_start(args, fmt);
	vsnprintf(buf, sizeof(buf), fmt, args);
	va_end(args);

	return d_print(ch->desc, buf);
}

int chprintlnf(CharData * ch, const char *fmt, ...)
{
	char buf[MPL];

	if (!ch || !ch->desc)
		return 0;

	buf[0] = NUL;
	if (!NullStr(fmt))
	{
		va_list args;

		va_start(args, fmt);
		vsnprintf(buf, sizeof(buf), fmt, args);
		va_end(args);
	}
	return d_println(ch->desc, buf);
}

int chwrap(CharData * ch, const char *txt)
{
	if (!NullStr(txt) && ch && ch->desc)
		return dwrap(ch->desc, txt);
	return 0;
}

int chwrapln(CharData * ch, const char *txt)
{
	if (ch && ch->desc)
		return dwrapln(ch->desc, txt);
	return 0;
}

int chwrapf(CharData * ch, const char *fmt, ...)
{
	if (!NullStr(fmt) && ch && ch->desc)
	{
		char buf[MPL];
		va_list args;

		va_start(args, fmt);
		vsnprintf(buf, sizeof(buf), fmt, args);
		va_end(args);
		return dwrap(ch->desc, buf);
	}
	return 0;
}

int chwraplnf(CharData * ch, const char *fmt, ...)
{
	char buf[MPL];

	if (!ch || !ch->desc)
		return 0;

	buf[0] = NUL;
	if (!NullStr(fmt))
	{
		va_list args;

		va_start(args, fmt);
		vsnprintf(buf, sizeof(buf), fmt, args);
		va_end(args);
	}
	return dwrapln(ch->desc, buf);
}

#endif
