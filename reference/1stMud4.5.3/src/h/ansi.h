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

#ifndef __ANSI_H_
#define __ANSI_H_

#define  COLORCODE   '{'
#define  CCSTR    	 "{"

typedef enum
{
	CL_NONE = 0,
	CL_BRIGHT = 1,
	CL_DIM = 2,
	CL_STANDOUT = 3,
	CL_UNDER = 4,
	CL_BLINK = 5,
	CL_ITALIC = 6,
	CL_REVERSE = 7,
	CL_HIDDEN = 8,
	CL_RANDOM = 9,

	CL_MOD = 10,

	FG_BLACK = 30,
	FG_RED = 31,
	FG_GREEN = 32,
	FG_YELLOW = 33,
	FG_BLUE = 34,
	FG_MAGENTA = 35,
	FG_CYAN = 36,
	FG_WHITE = 37,
	FG_RANDOM = CL_RANDOM,
	FG_NONE = CL_NONE,

	BG_BLACK = 40,
	BG_RED = 41,
	BG_GREEN = 42,
	BG_YELLOW = 43,
	BG_BLUE = 44,
	BG_MAGENTA = 45,
	BG_CYAN = 46,
	BG_WHITE = 47,
	BG_RANDOM = CL_RANDOM,
	BG_NONE = CL_NONE,
}
color_value_t;

#define VALID_BG(bg)     ((bg) >= BG_BLACK && (bg) <= BG_WHITE)

#define VALID_FG(fg)	 ((fg) >= FG_BLACK && (fg) <= FG_WHITE)

#define VALID_CL(cl)     ((cl) >= CL_NONE && (cl) <= CL_HIDDEN)

typedef enum
{ CT_ATTR, CT_FORE, CT_BACK, CT_SAVE, __CT_MAX }
color_attr_t;

#define CT_MAX	CT_SAVE

typedef color_value_t colatt_t[__CT_MAX];

#define ESC    	    	"\033"
#define ESCc    	'\033'

#define CL_DEFAULT    	    	ESC "[0m"

#define copy_color(a, b) \
do { \
	int x; \
	for(x = 0; x < CT_MAX; x++) \
		a[x] = b[x]; \
	a[CT_SAVE] = CL_MOD; \
} while(0)

#define copy_colors(a, b) \
do { \
	int x, y; \
	for(x = 0; x < MAX_CUSTOM_COLOR; x++) { \
		for(y = 0; y < CT_MAX; y++) \
			a[x][y] = b[x][y]; \
		a[x][CT_SAVE] = CL_MOD; \
	} \
} while(0);

#define getcol(col, i)	(*col)[i]

#define _NONE			-1
#define _DEFAULT		0
#define _GOSSIP			1
#define _MUSIC			2
#define _QA				3
#define _QUOTE			4
#define _GRATS			5
#define _SHOUT1			6
#define _SHOUT2			7
#define _IMMTALK		8
#define _TELLS1			9
#define _TELLS2			10
#define _SAY1			11
#define _SAY2			12
#define _SKILL			13
#define _YHIT			14
#define _OHIT			15
#define _VHIT			16
#define _WRACE			17
#define _WCLASS			18
#define _WLEVEL			19
#define _RTITLE			20
#define _SCORE1			21
#define _SCORE2			22
#define _SCORE3			23
#define _SCOREB			24
#define _WIZNET			25
#define _GTELL1			26
#define _GTELL2			27
#define _BTALK			28
#define _WSEX			29
#define _AUTOMAP		30
#define _AUTOEXITS		31
#define _MOBILES		32
#define _OBJECTS		33
#define _SOCIALS		34
#define _OLCBORDER		35
#define _OLCVAR			36
#define _OLCVAL			37
#define _CUSTOM_COLORS	38
#define MAX_CUSTOM_COLOR	top_color

#define VALID_COLOR(c)		(c > _NONE && c < MAX_CUSTOM_COLOR)

#define color_scheme_default_name		"Default"
#define color_scheme_default_descript	"Default Colour Scheme"

#define CUSTOMSTART      '\x11'
#define CUSTOMEND    	    '\x12'
#define CSSTR        	  "\x11"
#define CESTR    	    "\x12"

#define cstr(s) CSSTR #s CESTR
#define CTAG(s) cstr(s)

#define MXP_BEG "\x03"
#define MXP_END "\x04"
#define MXP_ENT "\x06"

#define MXP_BEGc '\x03'
#define MXP_ENDc '\x04'
#define MXP_ENTc '\x06'

#define HTML_LT   "&lt;"
#define HTML_GT   "&gt;"
#define HTML_QUOTE "&quote;"
#define HTML_AMP     "&amp;"

#define HTML_LTc     '<'
#define HTML_GTc     '>'
#define HTML_QUOTEc  '"'
#define HTML_AMPc    '&'

#define MXPMODE(arg) ESC "[" #arg "z"

#define MXPTAG(arg)     MXP_BEG arg MXP_END

#define LF   "\n"
#define CR   "\r"
#define NEWLINE     LF CR

#define CL_SEND_SOUND    	    	"AAA"
#define CL_SEND_IMAGE    	    	"AAB"
#define CL_SEND_REBOOT    	    	"AAC"
#define CL_SEND_MUSIC    	    	"AAD"
#define CL_SEND_UPTIME    	    	"AAF"
#define CL_SEND_AVI    	    	    "AAG"
#define CL_DOWNLOAD_MEDIA    	"AAH"
#define CL_SEND_SPECIAL    	    	"BAA"
#define CL_SEND_SPECIAL2    	"BAC"
#define CL_SEND_TELL    	    	"BAB"
#define CL_SEND_ROOM    	    	"BAD"
#define CL_SEND_MudLAG    	    	"BAE"
#define CL_SEND_EDIT    	    	"BAF"
#define CL_GP1_MASK    	    	    "BBA"
#define CL_GP2_MASK    	    	    "BBB"
#define CL_HP_MASK    	    	    "BBC"
#define CL_SP_MASK    	    	    "BBD"
#define CL_SEND_CAPTION    	    	"CAP"
#define CL_SEND_BEGIN_FILE    	"CDF"
#define CL_SEND_CONT_FILE    	"CCF"
#define CL_SEND_END_FILE    	"CEF"
#define CL_SEND_CHAT    	    	"CAA"
#define CL_SEND_ROOMCODE    "DDD"
#define CL_SEND_COMPOSITE    	"FFF"

#define  CL_SEND_HP    	    	    "A"
#define  CL_SEND_MAXHP    	    	"B"
#define  CL_SEND_SP    	    	    "C"
#define  CL_SEND_MAXSP    	    	"D"
#define  CL_SEND_GP1    	    	"E"
#define  CL_SEND_MAXGP1    	    	"F"
#define  CL_SEND_GP2    	    	"G"
#define  CL_SEND_MAXGP2    	    	"H"
#define  CL_SEND_GLINE1    	    	"I"
#define  CL_SEND_GLINE2    	    	"J"
#define  CL_SEND_ATTACKER    	"K"
#define  CL_SEND_ATTCOND    	"L"
#define  CL_SEND_ATTIMG    	    	"M"

#endif
