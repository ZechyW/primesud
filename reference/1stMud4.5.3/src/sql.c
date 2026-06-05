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

#ifndef DISABLE_MYSQL

#ifdef HAVE_MYSQL_H
#include <mysql/mysql.h>
#endif

#define DB_SERVER_NAME          "localhost"
#define DB_USER_NAME            "root"
#define DB_USER_PASSWORD        ""
char DB_NAME[MIL];

#define MOB_TABLE_NAME		"mobtype"
#define MOB_TABLE_ROWS          (sizeof(char_index_data_table) / sizeof(char_index_data_table[0]) - 1)

#define OBJ_TABLE_NAME		"objtype"
#define OBJ_TABLE_ROWS         (sizeof(obj_index_data_table) / sizeof(obj_index_data_table[0]) - 1)

#define ROOM_TABLE_NAME		"roomtype"
#define ROOM_TABLE_ROWS         (sizeof(room_index_data_table) / sizeof(room_index_data_table[0]) - 1)

#define AREA_TABLE_NAME         "areatype"
#define AREA_TABLE_ROWS         (sizeof(area_data_table) / sizeof(area_data_table[0]) - 1)

#define HELP_TABLE_NAME         "helptype"
#define HELP_TABLE_ROWS         (sizeof(help_data_table) / sizeof(help_data_table[0]) - 1)

#define COMMAND_TABLE_NAME      "commandtype"
#define COMMAND_TABLE_ROWS      (sizeof(cmd_data_table) / sizeof(cmd_data_table[0]) - 1)

#define SOCIAL_TABLE_NAME       "socialtype"
#define SOCIAL_TABLE_ROWS       (sizeof(social_data_table) / sizeof(social_data_table[0]) - 1)

#define SKILL_TABLE_NAME        "skilltype"
#define SKILL_TABLE_ROWS        (sizeof(skill_data_table) / sizeof(skill_data_table[0]) - 1)

#define MYSQL_INIT_FILE		DATA_DIR ".mysql"

MYSQL mysql;
MYSQL_RES *res, *ares, *bres;
MYSQL_ROW row, arow, brow;
MYSQL_FIELD *field;

int db_state = 1000;
bool db_first_run = false;

char *escape_string(const char *txt)
{
	static char buf[5][MSL];
	static int i;
	char *out;

	++i %= 5;
	out = buf[i];

	if (!NullStr(txt))
		mysql_escape_string(out, txt, strlen(txt));
	else
		out[0] = NUL;

	return out;
}

void exiterr(int exitcode, const char *file, int line)
{
	logf("%d at %s:%d: %s", exitcode, file, line, mysql_error(&mysql));
	if (exitcode > 1)
		db_stop();
	db_state = exitcode;
}

void init_db_first_run(void)
{
	FILE *fp;

	if (run_level != RUNLEVEL_BOOTING)
		return;

	fp = file_open(MYSQL_INIT_FILE, "r+");

	if (!fp)
	{
		/* OK, load data without MySQL. */
		fprintf(fp, "%s mysql database first run on %s.\n", DB_NAME,
				str_time(-1, -1, NULL));
		db_first_run = true;
	}

	file_close(fp);
}

void finish_db_first_run(void)
{
	AreaData *pArea;
	struct stat chk;

	if (run_level != RUNLEVEL_BOOTING)
		return;

	if (stat(MYSQL_INIT_FILE, &chk) != -1)
	{
		FILE *fp;

		for (pArea = area_first; pArea; pArea = pArea->next)
			save_area(pArea);
		rw_cmd_data(act_write);
		rw_skill_data(act_write);
		rw_social_data(act_write);
		rw_help_data(act_write);
		fp = file_open(MYSQL_INIT_FILE, "a");
		fprintf(fp,
				"Inserted %d areas, %d helps, %d commands, %d skills, and %d socials.\n",
				top_area, top_help, top_cmd, top_skill, top_social);
		file_close(fp);
	}
}

void db_start(void)
{
	if (db_state)
		db_state = 0;

	sprintf(DB_NAME, MUD_NAME "%d", mud_info.uniqe_id);

#if 0
	if (!
		(mysql_connect
		 (&mysql, DB_SERVER_NAME, DB_USER_NAME, DB_USER_PASSWORD)))
	{
		exiterr(1, __FILE__, __LINE__);
		return;
	}

	if (mysql_select_db(&mysql, DB_NAME))
	{
		exiterr(2, __FILE__, __LINE__);
		return;
	}
#else
	if (!(mysql_init(&mysql)))
	{
		exiterr(1, __FILE__, __LINE__);
		return;
	}

  again:
	if (!
		(mysql_real_connect
		 (&mysql, DB_SERVER_NAME, DB_USER_NAME, DB_USER_PASSWORD, DB_NAME, 0,
		  NULL, 0)))
	{
		if (!mysql_query("create database " DB_NAME))
			goto again;
		exiterr(2, __FILE__, __LINE__);
		return;
	}
#endif
}

void db_stop(void)
{
	if (db_state <= 1)
		return;

	mysql_close(&mysql);
}

void lock_tables(const char *tablenames)
{
	char buf[MAX_INPUT_LENGTH];

	sprintf(buf, "lock tables %s", tablenames);

	if (mysql_query(&mysql, buf))
	{
		exiterr(3, __FILE__, __LINE__);
		return;
	}
}

void unlock_tables(void)
{
	if (mysql_query(&mysql, "unlock tables"))
	{
		exiterr(3, __FILE__, __LINE__);
		return;
	}
}

int aname_query(const char *table, const char *name, int fields)
{
	char buf[MAX_STRING_LENGTH];

	if (db_state)
		return 0;

	sprintf(buf, "select * from %s where aname='%s'", table,
			escape_string(name));

	if (mysql_query(&mysql, buf))
	{
		exiterr(3, __FILE__, __LINE__);
		return 0;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(4, __FILE__, __LINE__);
		return 0;
	}

	if (mysql_num_fields(res) != fields)
	{
		logf("%s: expected %d fields got %d", table, fields,
			 mysql_num_fields(res));
		return 0;
	}

	return 1;
}

int db_generic_find(const char *sql)
{
	int x;

	if (db_state)
		return 0;

	if (mysql_query(&mysql, sql))
	{
		exiterr(5, __FILE__, __LINE__);
		return 0;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(6, __FILE__, __LINE__);
		return 0;
	}

	x = mysql_num_rows(res);

	mysql_free_result(res);

	return x;
}

int db_generic_insdel(const char *sql, const char *file, int line)
{
	int x;

	if (db_state)
		return 0;

	if (mysql_query(&mysql, sql))
	{
		exiterr(7, file, line);
		return 0;
	}

	x = mysql_affected_rows(&mysql);

	return x;
}

int db_find_vnum(const char *table_name, vnum_t vnum)
{
	char buf[MAX_INPUT_LENGTH];

	sprintf(buf, "SELECT vnum FROM %s where vnum=%ld", table_name, vnum);

	return db_generic_find(buf);
}

int db_del_vnum(const char *table_name, vnum_t vnum)
{
	char buf[MAX_STRING_LENGTH];

	sprintf(buf, "delete from %s where vnum=%ld", table_name, vnum);

	return db_generic_insdel(buf, __FILE__, __LINE__);
}

flag_t parse_flags(const char *str)
{
	flag_t number;
	flag_t flag;
	flag_t temp = 1;
	char c;
	bool negative = false;

	do
	{
		c = *str++;
	}
	while (is_space(c));

	if (c != '+')
	{
		if (c == '-')
		{
			negative = true;
			c = *str++;
		}

		number = 0;

		if (!isdigit(c))
		{
			while (('A' <= c && c <= 'Z') || ('a' <= c && c <= 'z'))
			{
				number += flag_convert(c);
				c = *str++;
			}
		}

		while (isdigit(c))
		{
			number = number * 10 + c - '0';
			c = *str++;
		}

		if (c == '|')
			number += parse_flags(row[i++]);

		else if (c != ' ')
			c = *(--str);

		if (negative)
			return -1 * number;
		return number;
	}
	else
	{
		number = 0;
		flag = 0;
		do
		{
			c = *str++;
			flag += (temp << number) * (c == 'Y');
			number++;
		}
		while (c == 'Y' || c == 'n');

		if (c == '\n' || c == '\r')
			c = *(--str);

		return flag;
	}
}

char *db_print_sound(MspData * snd)
{
	static char buf[MSL];

	if (snd)
		sprintf(buf, ",'%s','%s',%d,%d,%d,%d,'%s','%s'", snd->file,
				escape_string(write_flags(snd->to)), snd->volume, snd->loop,
				snd->priority, !snd->restart,
				escape_string(flag_string(msp_types, snd->type)),
				escape_string(snd->url));
	else
		strcpy(buf, ",'','',0,0,0,0,'',''");

	return buf;
}

MspData *db_read_sound(MYSQL_ROW row)
{
	MspData *snd = new_msp();

	snd->file = str_dup(row[0]);
	snd->to = parse_flags(row[1]);
	snd->volume = atoi(row[2]);
	snd->loop = atoi(row[3]);
	snd->priority = atoi(row[4]);
	snd->restart = (bool) atoi(row[5]);
	snd->type = (msp_t) flag_value(msp_types, row[6]);
	snd->url = str_dup(row[7]);

	return snd;
}

int db_insert_data_table(const char *name, void *typebase, DataTable * table,
						 void *puntero)
{
	DataTable *temp;
	static char buf[MSL * 8];
	const char **pstring, *string, tmp[MSL];
	int *pint, **array;
	long *plong, **larray;
	TableRW_F *function;
	flag_t *pentero;
	bool *pbool;
	FlagTable *flagtable;
	int cnt = 0, i;
	ClanRank *rdata;
	MspData **sound;
	time_t *ptime;
	vnum_t *pvnum;
	NameList **namelst, *nl;
	Spec_F **spdata;
	RaceData **race;
	DeityData **deity;
	AreaData **area;
	ClanData **clan;
	ShopData **shop;
	ExDescrData **exd;
	ResetData **reset;
	ExitData **exit;
	ProgList **prog;
	ProgCode **pcode;
	AffectData **paf;
	colatt_t *col;

	sprintf(buf, "insert into %s values(", name);

	for (temp = table; !NullStr(temp->field); temp++)
	{
		if (temp->function == olced_nosave)
		{
			continue;
		}
		switch (temp->type)
		{
			default:
				bugf("type_field %d invalid, field %s", temp->type,
					 temp->field);
				break;

			case FIELD_STRING:
				rwgetdata(pstring, const char *, temp->argument, typebase,
						  puntero);

				strcatf(buf, ",'%s'",
						NullStr(*pstring) ? "" :
						escape_string(fix_string(*pstring)));
				break;

			case FIELD_INT:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				strcatf(buf, ",%d", *pint);
				break;

			case FIELD_LONG:
				rwgetdata(plong, long, temp->argument, typebase, puntero);

				strcatf(buf, ",%ld", *plong);
				break;

			case FIELD_VNUM:
				rwgetdata(pvnum, vnum_t, temp->argument, typebase, puntero);
				strcatf(buf, ",%ld", *pvnum);
				break;

			case FIELD_TIME:
				rwgetdata(ptime, time_t, temp->argument, typebase, puntero);
				strcatf(buf, "," TIME_T_FMT, *ptime);
				break;

			case FIELD_FUNCTION_INT_TO_STR:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				function = (TableRW_F *) temp->arg1;
				if ((*function) (act_write, (void *) pint, &string) == false)
					bugf("field %s invalid, string %s", temp->field, string);
				strcatf(buf, ",'%s'", escape_string(string));
				break;

			case FIELD_FLAGSTRING:
				rwgetdata(pentero, flag_t, temp->argument, typebase, puntero);
				flagtable = (FlagTable *) temp->arg1;
				strcatf(buf, ",'%s'",
						escape_string(flag_string(flagtable, *pentero)));
				break;

			case FIELD_INT_FLAGSTRING:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				flagtable = (FlagTable *) temp->arg1;
				strcatf(buf, ",'%s'",
						escape_string(flag_string(flagtable, *pint)));
				break;

			case FIELD_FLAGVECTOR:
				rwgetdata(pentero, flag_t, temp->argument, typebase, puntero);
				strcatf(buf, ",'%s'", escape_string(write_flags(*pentero)));
				break;

			case FIELD_BOOL:
				rwgetdata(pbool, bool, temp->argument, typebase, puntero);
				strcatf(buf, ",'%s'", (*pbool == true) ? "true" : "false");
				break;

			case FIELD_DICE:
			case FIELD_INT_ARRAY:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				for (i = 0; i < (int) temp->arg1; i++)
					strcatf(tmp, " %d", pint[i]);
				strcatf(buf, ".'%s'", tmp + 1);
				break;

			case FIELD_INT_ALLOC_ARRAY:
				rwgetdata(array, int *, temp->argument, typebase, puntero);

				for (i = 0; i < *(int *) temp->arg1; i++)
					strcatf(tmp, " %d", (*array)[i]);
				strcatf(buf, ",'%s'", tmp + 1);
				break;

			case FIELD_LONG_ARRAY:
				rwgetdata(plong, long, temp->argument, typebase, puntero);

				for (i = 0; i < (int) temp->arg1; i++)
					strcatf(tmp, " %ld", plong[i]);
				strcatf(buf, ",'%s'", tmp + 1);
				break;

			case FIELD_LONG_ALLOC_ARRAY:
				rwgetdata(larray, long *, temp->argument, typebase, puntero);

				for (i = 0; i < *(int *) temp->arg1; i++)
					strcatf(tmp, " %ld", (*larray)[i]);
				strcatf(buf, ",'%s'", tmp + 1);
				break;

			case FIELD_STRING_ARRAY:
				rwgetdata(pstring, const char *, temp->argument, typebase,
						  puntero);

				for (i = 0; i < (int) temp->arg1; i++)
					strcatf(buf, ",'%s'",
							!NullStr(pstring[i]) ?
							escape_string(fix_string(pstring[i])) : "");
				break;

			case FIELD_STRING_ARRAY_NULL:
				rwgetdata(pstring, const char *, temp->argument, typebase,
						  puntero);

				for (i = 0; i < (int) temp->arg1 && !NullStr(pstring[i]); i++)
					strcatf(buf, ",'%s'",
							!NullStr(pstring[i]) ?
							escape_string(fix_string(pstring[i])) : "");
				break;

			case FIELD_BOOL_ARRAY:
				rwgetdata(pbool, bool, temp->argument, typebase, puntero);

				for (i = 0; i < (int) temp->arg1; i++)
					strcatf(tmp, " %d", pbool[i] == true ? 1 : 0);
				strcatf(buf, ",'%s'", tmp + 1);
				break;

			case FIELD_CLAN_RANK:
				rwgetdata(rdata, ClanRank, temp->argument, typebase, puntero);
				for (i = 0; i < (int) temp->arg1; i++)
				{
					strcatf(buf, ",'%s'",
							escape_string(fix_string(rdata[i].rankname)));
				}
				break;

			case FIELD_MSP:
				rwgetdata(sound, MspData *, temp->argument, typebase,
						  puntero);
				strcat(buf, db_print_sound(*sound));
				break;

			case FIELD_NAMELIST:
				rwgetdata(namelst, NameList *, temp->argument, typebase,
						  puntero);
				for (nl = *namelst; nl != NULL; nl = nl->next)
					strcatf(buf, ",'%s'",
							NullStr(nl->name) ? "" :
							escape_string(fix_string(nl->name)));
				break;

			case FIELD_SPEC_FUN:
				rwgetdata(spdata, Spec_F *, temp->argument, typebase,
						  puntero);
				strcatf(buf, ",'%s'",
						(spdata
						 && *spdata) ? escape_string(spec_name(*spdata)) :
						"");
				break;

			case FIELD_RACE:
				rwgetdata(race, RaceData *, temp->argument, typebase,
						  puntero);
				strcatf(buf, ",'%s'",
						(race && *race) ? escape_string((*race)->name) : "");
				break;

			case FIELD_DEITY:
				rwgetdata(deity, DeityData *, temp->argument, typebase,
						  puntero);
				strcatf(buf, ",'%s'",
						(deity
						 && *deity) ? escape_string((*deity)->name) : "");
				break;

			case FIELD_AREA:
				rwgetdata(area, AreaData *, temp->argument, typebase,
						  puntero);
				strcatf(buf, ",'%s'",
						(area && *area) ? escape_string((*area)->name) : "");
				break;

			case FIELD_CLAN:
				rwgetdata(clan, ClanData *, temp->argument, typebase,
						  puntero);
				strcatf(buf, ",'%s'",
						(clan && *clan) ? escape_string((*clan)->name) : "");
				break;

			case FIELD_SHOP:
				rwgetdata(shop, ShopData *, temp->argument, typebase,
						  puntero);
				if (shop && *shop)
				{
					strcatf(buf, ",%ld", (*shop)->keeper);
					db_insert_data_table(SHOP_TABLE_NAME, &shop_zero,
										 shop_data_table, *shop);
				}
				else
					strcpy(buf, ",0");
				break;

			case FIELD_EXDESC:
				rwgetdata(exd, ExDescrData *, temp->argument, typebase,
						  puntero);
				if (exd && *exd)
					db_insert_data_table(EXDESC_TABLE_NAME, &ed_zero,
										 ed_data_table, *exd);
				break;

			case FIELD_RESET_DATA:
				rwgetdata(reset, ResetData *, temp->argument, typebase,
						  puntero);
				if (reset && *reset)
					db_insert_data_table(RESET_TABLE_NAME, &reset_zero,
										 reset_data_table, *reset);
				break;

			case FIELD_EXIT_DATA:
				rwgetdata(exit, ExitData *, temp->argument, typebase,
						  puntero);
				if (exit && *exit)
					db_insert_data_table(EXIT_TABLE_NAME, &exit_zero,
										 exit_data_table, *exit);
				break;

			case FIELD_PROG_LIST:
				rwgetdata(prog, ProgList *, temp->argument, typebase,
						  puntero);
				if (prog && *prog)
					db_insert_data_table(PROG_TABLE_NAME, &prog_list_zero,
										 prog_list_data_table, *prog);
				break;

			case FIELD_PCODE:
				rwgetdata(pcode, ProgCode *, temp->argument, typebase,
						  puntero);
				strcatf(buf, ",%ld", (pcode && *pcode) ? (*pcode)->vnum : 0);
				break;

			case FIELD_AFFECT:
				rwgetdata(paff, AffectData *, temp->argument, typebase,
						  puntero);
				if (paff && *paff)
					db_insert_data_table(AFFECT_TABLE_NAME, &affect_zero,
										 affect_data_table, *paff);
				break;

			case FIELD_COLOR_ARRAY:
				rwgetdata(col, colatt_t, temp->argument, typebase, puntero);
				for (i = 0; i < MAX_CUSTOM_COLOR; i++)
				{
					sprintf(tmp, "%d %d %d ", col[i][CT_ATTR],
							col[i][CT_FORE], col[i][CT_BACK]);
				}
				strcat(tmp, "-1" LF);
				strcatf(buf, ",'%s'", tmp);
				break;

			case FIELD_COLOR:
				rwgetdata(col, colatt_t, temp->argument, typebase, puntero);
				f_printf(fp, ",%d,%d,%d" LF, getcol(col, CT_ATTR),
						 getcol(col, CT_FORE), getcol(col, CT_BACK));
				break;

			case FIELD_INUTIL:
				break;
		}

		cnt++;
	}
	strcat(buf, ")");
	return db_generic_insdel(buf, __FILE__, __LINE__);
}

int db_load_datatable(MYSQL_ROW row, void *typebase, DataTable * table,
					  void *puntero)
{
	const char *word, arg[MIL];
	DataTable *temp;
	flag_t *pentero, ftemp;
	const char **pstring, *string;
	int *pint, **array;
	long *plong, **larray;
	TableRW_F *function;
	FlagTable *flagtable;
	bool *pbool;
	int cnt = 0, i;
	ClanRank *rdata;
	time_t *ptime;
	vnum_t *pvnum;
	MspData **sound;
	NameList **nl_first, **nl_last, *nl;
	Spec_F **spdata;
	RaceData **race;
	DeityData **deity;
	AreaData **area;
	ClanData **clan;
	ShopData **shop;
	ExDescrData **exd;
	ResetData **reset;
	ExitData **exit;
	ProgList **prog;
	ProgCode **pcode;
	AffectData **paf;
	colatt_t *col;
	color_attr_t j;

	for (temp = table; !NullStr(temp->field); temp++)
	{
		if (temp->function == olced_nosave)
		{
			continue;
		}

		switch (temp->type)
		{
			case FIELD_STRING:
				rwgetdata(pstring, const char *, temp->argument, typebase,
						  puntero);

				*pstring = str_dup(row[cnt++]);

				break;

			case FIELD_INT:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				*pint = atoi(row[cnt++]);

				break;

			case FIELD_LONG:
				rwgetdata(plong, long, temp->argument, typebase, puntero);

				*plong = atol(row[cnt++]);

				break;

			case FIELD_VNUM:
				rwgetdata(pvnum, vnum_t, temp->argument, typebase, puntero);

				*pvnum = atov(row[cnt++]);
				break;

			case FIELD_TIME:
				rwgetdata(ptime, time_t, temp->argument, typebase, puntero);
				*ptime = atol(row[cnt++]);

				break;

			case FIELD_FUNCTION_INT_TO_STR:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				function = (TableRW_F *) temp->arg1;
				string = str_dup(row[cnt++]);
				if ((*function) (act_read, pint, &string) == false)
					bugf("field %s invalid, string %s", temp->field, string);
				free_string(string);

				break;

			case FIELD_FLAGSTRING:
				rwgetdata(pentero, flag_t, temp->argument, typebase, puntero);
				flagtable = (FlagTable *) temp->arg1;
				ftemp = flag_value(flagtable, row[cnt++]);
				*pentero = Max(0, ftemp);

				break;

			case FIELD_INT_FLAGSTRING:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				flagtable = (FlagTable *) temp->arg1;
				ftemp = flag_value(flagtable, row[cnt++]);
				*pint = Max(0, ftemp);

				break;

			case FIELD_FLAGVECTOR:
				rwgetdata(pentero, flag_t, temp->argument, typebase, puntero);
				*pentero = parse_flags(row[cnt++]);

				break;

			case FIELD_BOOL:
				rwgetdata(pbool, bool, temp->argument, typebase, puntero);
				*pbool = str_cmp(row[cnt++], "false") ? true : false;

				break;

			case FIELD_DICE:
			case FIELD_INT_ARRAY:
				rwgetdata(pint, int, temp->argument, typebase, puntero);

				for (i = 0, string = one_argument(row[cnt++], arg);
					 !NullStr(arg) && i < (int) temp->arg1;
					 i++, string = one_argument(string, arg))
				{
					pint[i] = atoi(arg);
				}
				break;

			case FIELD_INT_ALLOC_ARRAY:
				rwgetdata(array, int *, temp->argument, typebase, puntero);

				alloc_mem(*array, int, *(int *) temp->arg1);

				for (i = 0, string = one_argument(row[cnt++], arg);
					 !NullStr(arg) && i < *(int *) temp->arg1;
					 i++, string = one_argument(string, arg))
					(*array)[i] = atoi(arg);

				break;

			case FIELD_LONG_ARRAY:
				rwgetdata(plong, long, temp->argument, typebase, puntero);

				for (i = 0, string = one_argument(row[cnt++], arg);
					 !NullStr(arg) && i < (int) temp->arg1;
					 i++, string = one_argument(string, arg))
					plong[i] = atol(arg);

				break;

			case FIELD_LONG_ALLOC_ARRAY:
				rwgetdata(larray, long *, temp->argument, typebase, puntero);

				alloc_mem(*larray, long, *(int *) temp->arg1);

				for (i = 0, string = one_argument(row[cnt++], arg);
					 !NullStr(arg) && i < *(int *) temp->arg1;
					 i++, string = one_argument(string, arg))
					(*larray)[i] = atol(arg);

				break;

			case FIELD_STRING_ARRAY:
			case FIELD_STRING_ARRAY_NULL:
				rwgetdata(pstring, const char *, temp->argument, typebase,
						  puntero);

				for (i = 0; i < (int) temp->arg1; i++)
					pstring[i++] = str_dup(row[cnt++]);

				break;

			case FIELD_CLAN_RANK:
				rwgetdata(rdata, ClanRank, temp->argument, typebase, puntero);

				for (i = 0; i < (int) temp->arg1; i++)
					rdata[i].rankname = str_dup(row[cnt++]);

				break;

			case FIELD_MSP:
				rwgetdata(sound, MspData *, temp->argument, typebase,
						  puntero);

				break;

			case FIELD_NAMELIST:
				rwgetdata(nl_first, NameList *, temp->argument, typebase,
						  puntero);
				rwgetdata(nl_last, NameList *, temp->arg1, typebase, puntero);
				nl = new_namelist();
				nl->name = str_dup(row[cnt++]);
				Link(nl, *nl, next, prev);

				break;

			case FIELD_INUTIL:

				break;

			case FIELD_BOOL_ARRAY:
				rwgetdata(pbool, bool, temp->argument, typebase, puntero);

				for (i = 0, string = one_argument(row[cnt++], arg);
					 !NullStr(arg) && i < (int) temp->arg1;
					 i++, string = one_argument(string, arg))
					pbool[i] = (bool) atoi(arg);

				break;

			case FIELD_SPEC_FUN:
				rwgetdata(spdata, Spec_F *, temp->argument, typebase,
						  puntero);
				*spdata = spec_lookup(row[cnt++]);
				break;

			case FIELD_RACE:
				rwgetdata(race, RaceData *, temp->argument, typebase,
						  puntero);
				*race = race_lookup(row[cnt++]);
				if (!*race)
					*race = default_race;
				break;

			case FIELD_DEITY:
				rwgetdata(deity, DeityData *, temp->argument, typebase,
						  puntero);
				*deity = deity_lookup(row[cnt++]);
				break;

			case FIELD_AREA:
				rwgetdata(area, AreaData *, temp->argument, typebase,
						  puntero);
				*area = area_lookup(row[cnt++]);
				break;

			case FIELD_CLAN:
				rwgetdata(clan, ClanData *, temp->argument, typebase,
						  puntero);
				*clan = clan_lookup(row[cnt++]);
				break;

			case FIELD_SHOP:
				rwgetdata(shop, ShopData *, temp->argument, typebase,
						  puntero);
				db_fetch_shop(*shop, atov(row[cnt++]));
				break;

			case FIELD_EXDESC:
				rwgetdata(exd, ExDescrData *, temp->argument, typebase,
						  puntero);
				break;

			case FIELD_COLOR_ARRAY:
				rwgetdata(col, colatt_t, temp->argument, typebase, puntero);
				for (i = 0, j = CT_ATTR, string =
					 one_argument(row[cnt++], arg);
					 !NullStr(arg)
					 && (col[i][j] = (color_value_t) atoi(arg)) != -1;
					 j++, string = one_argument(string, arg))
				{
					if (j == CT_BACK)
					{
						i++;
						j = CT_ATTR;
					}
				}
				break;

			case FIELD_COLOR:
				rwgetdata(col, colatt_t, temp->argument, typebase, puntero);

				for (i = CT_ATTR, string = one_argument(row[cnt++], arg);
					 !NullStr(arg) && i < CT_BACK + 1;
					 i++, string = one_argument(string, arg))
					getcol(col, i) = (color_value_t) atoi(arg);
				break;
			default:
				bugf("type_field %d invalid, field %s", temp->type,
					 temp->field);
				break;
		}
	}
	return cnt;
}

int db_insert_mob(bool del, CharIndex * mob)
{
	char buf[MAX_STRING_LENGTH * 8];
	int i;

	if (!mob || !mob->area)
	{
		log_string("db_insert_mob: !mob || !mob->area");
		return 0;
	}

	if (del)
		db_del_vnum(MOB_TABLE_NAME, mob->vnum);
/*
	sprintf(buf, "insert into %s values(", MOB_TABLE_NAME);
	strcatf(buf, "'%s',", escape_string(mob->area->name));
	strcatf(buf, "%ld,", mob->vnum);
	strcatf(buf, "'%s',", escape_string(mob->player_name));
	strcatf(buf, "'%s',", escape_string(mob->short_descr));
	strcatf(buf, "'%s',", escape_string(mob->long_descr));
	strcatf(buf, "'%s',", escape_string(mob->description));
	strcatf(buf, "'%s',", escape_string(mob->mob->race->name));
	strcatf(buf, "'%s',", write_flags(mob->act));
	strcatf(buf, "'%s',", write_flags(mob->affected_by));
	strcatf(buf, "%d,%ld,", mob->alignment, mob->group);
	strcatf(buf, "%d,", mob->level);
	strcatf(buf, "%d,%d,", mob->random, mob->autoset);
	strcatf(buf, "%d,", mob->hitroll);
	for (i = 0; i < DICE_MAX; i++)
		strcatf(buf, "%d,", mob->hit[i]);
	for (i = 0; i < DICE_MAX; i++)
		strcatf(buf, "%d,", mob->mana[i]);
	for (i = 0; i < DICE_MAX; i++)
		strcatf(buf, "%d,", mob->damage[i]);
	strcatf(buf, "'%s',", attack_table[mob->dam_type].name);
	for (i = 0; i < MAX_AC; i++)
		strcatf(buf, "%d,", mob->ac[i] / 10);
	strcatf(buf, "'%s',", write_flags(mob->off_flags));
	strcatf(buf, "'%s',", write_flags(mob->imm_flags));
	strcatf(buf, "'%s',", write_flags(mob->res_flags));
	strcatf(buf, "'%s',", write_flags(mob->vuln_flags));
	strcatf(buf, "'%s','%s','%s',%ld,",
			flag_string(position_flags, mob->start_pos),
			flag_string(position_flags, mob->default_pos),
			flag_string(sex_flags, mob->sex), mob->wealth);
	strcatf(buf, "'%s',", write_flags(mob->form));
	strcatf(buf, "'%s',", write_flags(mob->parts));

	strcatf(buf, "'%s',", flag_string(size_flags, mob->size));
	strcatf(buf, "'%s',", escape_string(GetStr(mob->material, "unknown")));
	strcatf(buf, "%ld,%ld)", mob->kills, mob->deaths);

	return db_generic_insdel(buf, __FILE__, __LINE__); */
	return db_insert_data_table(MOB_TABLE_NAME, &char_index_zero,
								char_index_data_table, mob);
}

/*
void row_to_mob(CharIndex * mob)
{
	int i = 1, j;

	mob->vnum = atov(row[i++]);
	mob->player_name = str_dup(row[i++]);
	mob->short_descr = str_dup(row[i++]);
	mob->long_descr = str_dup(row[i++]);
	mob->description = str_dup(row[i++]);
	mob->race = race_lookup(row[i++]);
	if (mob->race == NULL)
		mob->race = default_race;
	mob->act = parse_flags(row[i++]) | ACT_IS_NPC | mob->race->act;
	mob->affected_by = parse_flags(row[i++]) | mob->race->aff;
	mob->alignment = atoi(row[i++]);
	mob->group = atov(row[i++]);
	mob->level = atoi(row[i++]);
	mob->random = atoi(row[i++]);
	mob->autoset = atoi(row[i++]);
	mob->hitroll = atoi(row[i++]);
	for (j = 0; j < DICE_MAX; j++, i++)
		mob->hit[j] = atoi(row[i]);
	for (j = 0; j < DICE_MAX; j++, i++)
		mob->mana[j] = atoi(row[i]);
	for (j = 0; j < DICE_MAX; j++, i++)
		mob->damage[j] = atoi(row[i]);
	mob->dam_type = attack_lookup(row[i++]);
	for (j = 0; j < MAX_AC; j++, i++)
		mob->ac[j] = atoi(row[i]) * 10;
	mob->off_flags = parse_flags(row[i++]) | mob->race->off;
	mob->imm_flags = parse_flags(row[i++]) | mob->race->imm;
	mob->res_flags = parse_flags(row[i++]) | mob->race->res;
	mob->vuln_flags = parse_flags(row[i++]) | mob->race->vuln;
	mob->start_pos = (position_t) flag_value(position_flags, row[i++]);
	mob->default_pos = (position_t) flag_value(position_flags, row[i++]);
	mob->sex = (sex_t) flag_value(sex_flags, row[i++]);
	mob->wealth = atom(row[i++]);
	mob->form = parse_flags(row[i++]) | mob->race->form;
	mob->parts = parse_flags(row[i++]) | mob->race->parts;
	mob->size = (size_type) flag_value(size_flags, row[i++]);
	mob->material = str_dup(row[i++]);
	mob->kills = atol(row[i++]);
	mob->deaths = atol(row[i++]);
}
*/

int db_fetch_mob(CharIndex * mob, vnum_t vnum)
{
	char buf[MAX_STRING_LENGTH];

	if (!db_find_vnum(MOB_TABLE_NAME, vnum))
		return 0;

	sprintf(buf, "select * from %s where vnum=%ld", MOB_TABLE_NAME, vnum);

	if (mysql_query(&mysql, buf))
	{
		exiterr(8, __FILE__, __LINE__);
		return 0;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(9, __FILE__, __LINE__);
		return 0;
	}

	if (mysql_num_fields(res) != MOB_TABLE_ROWS)
	{
		log_string("db_fetch_mob: wrong number of fields");
		return 0;
	}

	row = mysql_fetch_row(res);
	db_load_datatable(row, &char_index_zero, char_index_data_table, mob);
//  row_to_mob(mob);

	mysql_free_result(res);

	return 1;
}

void db_load_mobiles(AreaData * tarea)
{
	CharIndex *mob;
	char buf[MAX_INPUT_LENGTH];

	if (!tarea)
	{
		bug("db_load_mobiles: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(MOB_TABLE_NAME, tarea->name, MOB_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		bool oldmob = false;
		vnum_t vnum;
		int iHash;

		vnum = atov(row[1]);
		run_level = RUNLEVEL_SAFE_BOOT;
		if (get_char_index(vnum))
		{
			bug("db_load_mobiles: vnum %d duplicated.", vnum);
			shutdown_mud("duplicate vnum");
			exit(1);
		}
		run_level = RUNLEVEL_BOOTING;

		mob = new_char_index();
		pMobIndex->new_format = true;
		newmobs++;
//      row_to_mob(mob);
		db_load_datatable(row, &char_index_zero, char_index_data_table, mob);
		mob->area = tarea;

		iHash = vnum % MAX_KEY_HASH;
		LinkSingle(mob, char_index_hash[iHash], next);
		top_vnum_mob = Max(top_vnum_mob, vnum);
		assign_area_vnum(vnum);
		kill_table[Range(0, mob->level, MAX_LEVEL - 1)].number++;
	}

	mysql_free_result(res);
}

int db_insert_obj(bool del, ObjIndex * obj)
{
	char buf[MAX_STRING_LENGTH * 8];
	int i;

	if (!obj || !obj->area)
	{
		log_string("db_insert_obj: !obj || !obj->area");
		return 0;
	}

	if (del)
		db_del_vnum(OBJ_TABLE_NAME, obj->vnum);
/*
	sprintf(buf, "insert into %s values(", OBJ_TABLE_NAME);
	strcatf(buf, "'%s',", escape_string(obj->area->name));
	strcatf(buf, "%ld,", obj->vnum);
	strcatf(buf, "'%s',", escape_string(obj->name));
	strcatf(buf, "'%s',", escape_string(obj->short_descr));
	strcatf(buf, "'%s',", escape_string(fix_string(obj->description)));
	strcatf(buf, "'%s',", escape_string(obj->material));
	strcatf(buf, "'%s',", flag_string(type_flags, obj->item_type));
	strcatf(buf, "'%s',", write_flags(obj->extra_flags));
	strcatf(buf, "'%s',", write_flags(obj->wear_flags));

	switch (obj->item_type)
	{
	default:
		for (i = 0; i < 5; i++)
			strcatf(buf, "'%s',", write_flags(obj->value[i]));
		break;

	case ITEM_DRINK_CON:
	case ITEM_FOUNTAIN:
		strcatf(buf, "%ld,%ld,'%s',%ld,%ld,", obj->value[0],
				obj->value[1],
				escape_string(liq_table[obj->value[2]].liq_name),
				obj->value[3], obj->value[4]);
		break;

	case ITEM_CONTAINER:
		strcatf(buf, "%ld,'%s',%ld,%ld,%ld,", obj->value[0],
				write_flags(obj->value[1]),
				obj->value[2], obj->value[3], obj->value[4]);
		break;

	case ITEM_WEAPON:
		strcatf(buf, "'%s',%ld,%ld,'%s','%s',",
				escape_string(weapon_name(obj->value[0])),
				obj->value[1], obj->value[2],
				escape_string(attack_table[obj->value[3]].name),
				write_flags(obj->value[4]));
		break;

	case ITEM_PILL:
	case ITEM_POTION:
	case ITEM_SCROLL:
		strcatf(buf, "%ld,", Max(obj->value[0], 0)) for (i = 1; i < 5; i++)
			strcatf(buf, "'%s',",
					ValidSkill(obj->value[i]) ?
					escape_string(skill_table[obj->value[i]].name) : "");
		break;

	case ITEM_STAFF:
	case ITEM_WAND:
		strcatf(buf, "%ld,%ld,%ld,'%s',%ld", obj->value[0],
				obj->value[1], obj->value[2],
				ValidSkill(obj->value[3]) ?
				escape_string(skill_table[obj->value[3]].name) : "",
				obj->value[4]);
		break;
	}

	strcatf(buf, "%d,%d,%ld,%d)", obj->level, obj->weight,
			obj->cost, obj->condition);

	return db_generic_insdel(buf, __FILE__, __LINE__); */
	return db_insert_data_table(OBJ_TABLE_NAME, &obj_index_zero,
								obj_index_data_table, obj);
}
/*
void row_to_obj(ObjIndex * obj)
{
	int i = 1;

	obj->vnum = atov(row[i++]);
	obj->name = str_dup(row[i++]);
	obj->short_descr = str_dup(Upper(row[i++]));
	obj->description = str_dup(Upper(row[i++]));
	obj->material = str_dup(row[i++]);
	obj->item_type = (item_t) flag_value(type_flags, row[i++]);
	obj->extra_flags = parse_flags(row[i++]);
	obj->wear_flags = parse_flags(row[i++]);
	switch (obj->item_type)
	{
	case ITEM_WEAPON:
		obj->value[0] = weapon_class(row[i++]);
		obj->value[1] = atol(row[i++]);
		obj->value[2] = atol(row[i++]);
		obj->value[3] = attack_lookup(row[i++]);
		obj->value[4] = parse_flags(row[i++]);
		break;
	case ITEM_CONTAINER:
		obj->value[0] = atol(row[i++]);
		obj->value[1] = parse_flags(row[i++]);
		obj->value[2] = atol(row[i++]);
		obj->value[3] = atol(row[i++]);
		obj->value[4] = atol(row[i++]);
		break;
	case ITEM_DRINK_CON:
	case ITEM_FOUNTAIN:
		obj->value[0] = atol(row[i++]);
		obj->value[1] = atol(row[i++]);
		CheckPos(obj->value[2], liq_lookup(row[i++]), "liq_lookup");
		obj->value[3] = atol(row[i++]);
		obj->value[4] = atol(row[i++]);
		break;
	case ITEM_WAND:
	case ITEM_STAFF:
		obj->value[0] = atol(row[i++]);
		obj->value[1] = atol(row[i++]);
		obj->value[2] = atol(row[i++]);
		obj->value[3] = skill_lookup(row[i++]);
		obj->value[4] = atol(row[i++]);
		break;
	case ITEM_POTION:
	case ITEM_PILL:
	case ITEM_SCROLL:
		obj->value[0] = atol(row[i++]);
		obj->value[1] = skill_lookup(row[i++]);
		obj->value[2] = skill_lookup(row[i++]);
		obj->value[3] = skill_lookup(row[i++]);
		obj->value[4] = skill_lookup(row[i++]);
		break;
	default:
		obj->value[0] = parse_flags(row[i++]);
		obj->value[1] = parse_flags(row[i++]);
		obj->value[2] = parse_flags(row[i++]);
		obj->value[3] = parse_flags(row[i++]);
		obj->value[4] = parse_flags(row[i++]);
		break;
	}
	obj->level = atoi(row[i++]);
	obj->weight = atoi(row[i++]);
	obj->cost = atoi(row[i++]);
	obj->condition = atoi(row[i++]);
}
*/
int db_fetch_obj(ObjIndex * obj, vnum_t vnum)
{
	char buf[MAX_STRING_LENGTH];

	if (!db_find_vnum(OBJ_TABLE_NAME, vnum))
		return 0;

	sprintf(buf, "select * from %s where vnum=%ld", OBJ_TABLE_NAME, vnum);

	if (mysql_query(&mysql, buf))
	{
		exiterr(10, __FILE__, __LINE__);
		return 0;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(11, __FILE__, __LINE__);
		return 0;
	}

	if (mysql_num_fields(res) != OBJ_TABLE_ROWS)
	{
		log_string("db_fetch_obj: wrong number of fields");
		return 0;
	}

	row = mysql_fetch_row(res);
//  row_to_obj(obj);
	db_load_datatable(row, &obj_index_zero, obj_index_data_table, obj);
	mysql_free_result(res);

	return 1;
}

void db_load_objects(AreaData * tarea)
{
	ObjIndex *obj;
	char buf[MAX_STRING_LENGTH];

	if (!tarea)
	{
		bug("db_load_objects: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(OBJ_TABLE_NAME, tarea->name, OBJ_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		vnum_t vnum;
		int iHash;

		vnum = atov(row[1]);
		run_level = RUNLEVEL_SAFE_BOOT;
		if (get_obj_index(vnum))
		{
			bug("db_load_objects: vnum %d duplicated.", vnum);
			shutdown_mud("duplicate vnum");
			exit(1);
		}
		run_level = RUNLEVEL_BOOTING;

		obj = new_obj_index();
//      row_to_obj(obj);
		db_load_datatable(row, &obj_index_zero, obj_index_data_table, obj);
		obj->area = tarea;
		obj->new_format = true;
		obj->reset_num = 0;
		newobjs++;

		iHash = vnum % MAX_KEY_HASH;
		LinkSingle(obj, obj_index_hash[iHash], next);
		top_vnum_obj = Max(top_vnum_obj, vnum);
		assign_area_vnum(vnum);
	}

	mysql_free_result(res);
}

int db_insert_room(bool del, RoomIndex * room)
{
	char buf[MAX_STRING_LENGTH * 8];

	if (!room || !room->area)
	{
		log_string("db_insert_room: !room || !room->area");
		return 0;
	}

	if (del)
		db_del_vnum(ROOM_TABLE_NAME, room->vnum);
/*
	sprintf(buf, "insert into %s values(", ROOM_TABLE_NAME);
	strcatf(buf, "'%s',", escape_string(room->area->name));
	strcatf(buf, "%ld,", room->vnum);
	strcatf(buf, "'%s',", escape_string(room->name));
	strcatf(buf, "'%s',", escape_string(fix_string(room->description)));
	strcatf(buf, "'%s','%s',",
			write_flags(room->room_flags),
			flag_string(sector_flags, room->sector_type));
	strcatf(buf, "%d,%d,", room->mana_rate, room->heal_rate);
	strcatf(buf, "'%s',", escape_string(room->owner));
	strcatf(buf, "%d)", room->guild);

	return db_generic_insdel(buf, __FILE__, __LINE__); */
	return db_insert_data_table(ROOM_TABLE_NAME, &room_index_zero,
								room_index_data_table, room);
}

/*
void row_to_room(RoomIndex * room)
{
	int i = 1;

	room->vnum = atov(row[i++]);
	room->name = str_dup(row[i++]);
	room->description = str_dup(row[i++]);
	room->room_flags = parse_flags(row[i++]);
	if (3000 <= vnum && vnum < 3400)
		SetBit(room->room_flags, ROOM_LAW);
	room->sector_type = (sector_t) flag_value(sector_flags, row[i++]);
	room->mana_rate = atoi(row[i++]);
	room->heal_rate = atoi(row[i++]);
	room->owner = str_dup(row[i++]);
	if (!NullStr(room->owner))
		SetBit(room->room_flags, ROOM_NOEXPLORE);
	room->guild = atoi(row[i++]);
}
*/

int db_fetch_room(RoomIndex * room, vnum_t vnum)
{
	char buf[MAX_STRING_LENGTH];

	if (!db_find_vnum(ROOM_TABLE_NAME, vnum))
		return 0;

	sprintf(buf, "select * from %s where vnum=%ld", ROOM_TABLE_NAME, vnum);

	if (mysql_query(&mysql, buf))
	{
		exiterr(10, __FILE__, __LINE__);
		return 0;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(11, __FILE__, __LINE__);
		return 0;
	}

	if (mysql_num_fields(res) != ROOM_TABLE_ROWS)
	{
		log_string("db_fetch_room: wrong number of fields");
		return 0;
	}

	row = mysql_fetch_row(res);
//  row_to_room(room);
	db_load_datatable(row, &room_index_zero, room_index_data_table, room);

	mysql_free_result(res);

	return 1;
}

RoomIndex *db_get_room_index(vnum_t vnum)
{
	RoomIndex *room;

	room = new_room_index();

	if (!db_fetch_room(room, vnum))
	{
		free_mem(room);
		return NULL;
	}

	return room;
}

void db_load_rooms(AreaData * tarea)
{
	RoomIndex *room;
	char buf[MAX_STRING_LENGTH];

	if (!tarea)
	{
		bug("db_load_rooms: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(ROOM_TABLE_NAME, tarea->name, ROOM_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		vnum_t vnum;
		int iHash;

		vnum = atov(row[1]);
		run_level = RUNLEVEL_SAFE_BOOT;
		if (get_room_index(vnum))
		{
			bug("db_load_rooms: vnum %d duplicated.", vnum);
			shutdown_mud("duplicate vnum");
			exit(1);
		}
		run_level = RUNLEVEL_BOOTING;

		room = new_room_index();
		db_load_datatable(row, &room_index_zero, room_index_data_table, room);
//      row_to_room(room);
		room->area = tarea;
		iHash = vnum % MAX_KEY_HASH;

		LinkSingle(pRoomIndex, room_index_hash[iHash], next);
		if (!IsSet(pRoomIndex->room_flags, ROOM_NOEXPLORE))
			top_explored++;
		top_vnum_room = Max(top_vnum_room, vnum);
		assign_area_vnum(vnum);
	}

	mysql_free_result(res);
}

int db_insert_shop(bool del, ShopData * shop)
{
	CharIndex *mob;
	char buf[MAX_STRING_LENGTH];
	int iTrade;

	if (!shop || !(mob = get_mob_index(shop->keeper)))
	{
		bug("db_insert_shop: !shop || !shop->keeper");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where keeper=%d", SHOP_TABLE_NAME,
				shop->keeper);
		db_generic_insdel(buf, __FILE__, __LINE__);
	}
/*
	sprintf(buf, "insert into %s values('%s',",
			SHOP_TABLE_NAME, escape_string(mob->area->name));

	strcatf(buf, "%ld,", shop->keeper);
	for (iTrade = 0; iTrade < MAX_TRADE; iTrade++)
		strcatf(buf, "%d,", shop->buy_type[iTrade]);
	strcatf(buf, "%d,%d,%d,%d)", shop->profit_buy,
			shop->profit_sell, shop->open_hour, shop->close_hour);

	return db_generic_insdel(buf, __FILE__, __LINE__);
*/
	return db_insert_data_table(SHOP_TABLE_NAME, &shop_zero, shop_data_table,
								shop);
}

void db_load_shops(AreaData * tarea)
{
	ShopData *pShop;

	if (!tarea)
	{
		bug("db_load_shops: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(SHOP_TABLE_NAME, tarea->name, SHOP_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		CharIndex *pMobIndex;
		int i;

		pShop = new_shop();
/*
		pShop->keeper = atoi(row[i++]);
		if (pShop->keeper == 0)
		{
			free_shop(pShop);
			continue;
		}
		for (iTrade = 0; iTrade < MAX_TRADE; iTrade++)
			pShop->buy_type[iTrade] = atoi(row[i++]);
		pShop->profit_buy = atoi(row[i++]);
		pShop->profit_sell = atoi(row[i++]);
		pShop->open_hour = atoi(row[i++]);
		pShop->close_hour = atoi(row[i++]);
  */
		db_load_datatable(row, &shop_zero, shop_data_table, pShop);

		pMobIndex = get_char_index(pShop->keeper);
		pMobIndex->pShop = pShop;
		Link(pShop, shop, next, prev);
	}

	mysql_free_result(res);
}

int db_insert_special(bool del, AreaData * area, Spec_F * spec, vnum_t vnum)
{
	char buf[MAX_STRING_LENGTH];

	if (!area || !spec)
	{
		bug("db_insert_special: !area || !spec");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where vnum=%ld and type='%s'",
				SPEC_TABLE_NAME, vnum, type);
		db_generic_insdel(buf, __FILE__, __LINE__);
	}

	sprintf(buf, "insert into %s values('%s',%d,'%s')", SPEC_TABLE_NAME,
			escape_string(area->name), vnum, escape_string(spec_name(spec)));

	return db_generic_insdel(buf, __FILE__, __LINE__);
}

void db_load_specials(AreaData * tarea)
{
	CharIndex *pMobIndex;
	ObjIndex *obj;
	RoomIndex *room;

	if (!tarea)
	{
		bug("db_load_specials: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(SPEC_TABLE_NAME, tarea->name, SPEC_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		pMobIndex = get_mob_index(atov(row[1]));
		pMobIndex->spec_fun = spec_lookup(row[4]);
		if (pMobIndex->spec_fun == NULL)
			bug("db_load_specials: 'MOB': vnum %d.", pMobIndex->vnum);
	}

	mysql_free_result(res);
}

int db_insert_descs(bool del, AreaData * area, ExDescrData * eds, vnum_t vnum,
					const char *type)
{
	ExDescrData *ed;
	char buf[MAX_STRING_LENGTH * 8];
	int x = 0;

	if (!area)
	{
		bug("db_insert_descs: !area");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where vnum=%ld and type='%s'",
				DESC_TABLE_NAME, vnum, type);
		db_generic_insdel(buf, __FILE__, __LINE__);
	}

	for (ed = eds; ed; ed = ed->next)
	{
		sprintf(buf, "insert into %s values('%s',%d,'%s','%s','%s')",
				DESC_TABLE_NAME, escape_string(area->name), vnum, type,
				escape_string(ed->keyword), escape_string(ed->description));
		x += db_generic_insdel(buf, __FILE__, __LINE__);
	}

	return x;
}

void db_load_descs(AreaData * tarea)
{
	ObjIndex *obj;
	RoomIndex *room;
	ExDescrData *ed;

	if (!tarea)
	{
		bug("db_load_descs: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(DESC_TABLE_NAME, tarea->name, DESC_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		if (!str_cmp(row[2], "OBJ"))
		{
			obj = get_obj_index(atov(row[1]));
			if (!obj)
			{
				bugf("db_load_descs: obj %d not found", atoi(row[1]));
				continue;
			}

			ed = new_ed();
			ed->keyword = str_dup(row[3]);
			ed->description = str_dup(row[4]);
			Link(ed, obj->ed, next, prev);
		}
		else if (!str_cmp(row[2], "ROOM"))
		{
			room = get_room_index(atov(row[1]));
			if (!room)
			{
				bugf("db_load_descs: room %d not found", atov(row[1]));
				continue;
			}

			ed = new_ed();
			ed->keyword = str_dup(row[3]);
			ed->description = str_dup(row[4]);
			Link(ed, room->ed, next, prev);
		}

	}

	mysql_free_result(res);
}

int db_insert_exit(bool del, AreaData * area, ExitData * ex, int dir,
				   vnum_t vnum)
{
	char buf[MAX_STRING_LENGTH];

	if (!area)
	{
		bug("db_insert_climate: !area");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where vnum=%ld and vdir=%d",
				EXIT_TABLE_NAME, vnum, ex->vdir);
		db_generic_insdel(buf, __FILE__, __LINE__);
	}

	if (dir < 0 || dir > MAX_DIR || !ex->u1.to_room
		|| IsSet(ex->rs_flags, EX_TEMP))
		return 0;

	if (IsSet(pExit->rs_flags, EX_CLOSED) || IsSet(pExit->rs_flags, EX_LOCKED)
		|| IsSet(pExit->rs_flags, EX_PICKPROOF)
		|| IsSet(pExit->rs_flags, EX_NOPASS)
		|| IsSet(pExit->rs_flags, EX_EASY) || IsSet(pExit->rs_flags, EX_HARD)
		|| IsSet(pExit->rs_flags, EX_INFURIATING)
		|| IsSet(pExit->rs_flags, EX_NOCLOSE)
		|| IsSet(pExit->rs_flags, EX_NOLOCK))
		SetBit(pExit->rs_flags, EX_ISDOOR);
	else
		RemBit(pExit->rs_flags, EX_ISDOOR);

	sprintf(buf, "insert into %s values('%s',%ld,%d,'%s','%s','%s',%ld,%ld)",
			EXIT_TABLE_NAME, escape_string(area->name), vnum, dir,
			escape_string(ex->description), escape_string(ex->keyword),
			write_flags(ex->rs_flags), ex->key, ex->u1.to_room->vnum);

	return db_generic_insdel(buf, __FILE__, __LINE__);
}

void db_load_exits(AreaData * tarea)
{
	RoomIndex *room;

	if (!tarea)
	{
		bug("db_load_exits: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(EXIT_TABLE_NAME, tarea->name, EXIT_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		ExitData *pexit;
		int locks, door;

		room = get_room_index(atov(row[1]));
		if (!room)
		{
			bug("db_load_exits: room %d not found", atov(row[1]));
			continue;
		}

		door = atoi(row[2]);
		if (door < 0 || door > MAX_DIR)
		{
			bug("fread_exits: vnum %ld has bad door number %d.", room->vnum,
				door);
			if (run_level == RUNLEVEL_BOOTING)
				exit(1);
		}
		else
		{
			pexit = new_exit();
			pexit->description = str_dup(row[3]);
			pexit->keyword = str_dup(row[4]);
			pexit->rs_flags = parse_flags(row[5]);

			if (IsSet(pexit->rs_flags, EX_TEMP))
				RemBit(pexit->rs_flags, EX_TEMP);

			pexit->exit_info = pexit->rs_flags;
			pexit->key = atov(row[6]);
			pexit->u1.vnum = atov(row[7]);
			pexit->orig_door = door;
			room->exit[door] = pexit;
		}
	}

	mysql_free_result(res);
}

int db_insert_objaffects(bool del, AreaData * area, ObjIndex * obj)
{
	AffectData *aff;
	char buf[MAX_STRING_LENGTH];
	int x = 0;

	if (!area || !obj)
	{
		bug("db_insert_objaffect: !area || !obj");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where aname='%s' and vnum=%ld",
				OBJAFF_TABLE_NAME, aname, obj->vnum);
		db_generic_insdel(buf, __FILE__, __LINE__);
	}

	for (aff = obj->affect_first; aff; aff = aff->next)
	{
		sprintf(buf, "insert into %s values('%s',%ld,%d,%d,%d,'%s')",
				OBJAFF_TABLE_NAME, escape_string(area->name), obj->vnum,
				aff->where, aff->location, aff->modifier,
				write_flags(aff->bitvector));

		x += db_generic_insdel(buf, __FILE__, __LINE__);
	}

	return x;
}

void db_load_objaffects(AreaData * tarea)
{
	ObjIndex *obj;

	if (!tarea)
	{
		bug("db_load_affects: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(OBJAFF_TABLE_NAME, tarea->name, OBJAFF_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		AffectData *paf;

		obj = get_obj_index(atov(row[1]));
		if (!obj)
		{
			bug("db_load_affects: obj %ld not found", atov(row[1]));
			continue;
		}

		paf = new_affect();
		paf->where = (where_t) atoi(row[2]);
		paf->type = -1;
		paf->duration = -1;
		paf->location = (apply_t) atoi(row[3]);
		paf->modifier = atoi(row[4]);
		paf->bitvector = parse_flags(row[5]);
		paf->level = obj->level;
		Link(paf, obj->affect, next, prev);
	}

	mysql_free_result(res);
}

int db_insert_progs(bool del, AreaData * area, ProgList * progs, vnum_t vnum,
					const char *type)
{
	ProgList *prog;
	char buf[MAX_STRING_LENGTH * 8];
	int x = 0;

	if (!area)
	{
		bug("db_insert_progs: !area");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where vnum=%ld and type='%s'",
				PROG_TABLE_NAME, vnum, type);
		db_generic_insdel(buf, __FILE__, __LINE__);
	}

	for (prog = progs; prog; prog = prog->next)
	{

		sprintf(buf, "insert into %s values('%s',%ld,'%s','%s',%ld,'%s')",
				PROG_TABLE_NAME, escape_string(area->name), vnum, type,
				escape_string(prog_type_to_name(prog->type)),
				prog->prog->vnum, escape_string(prog->trig_phrase));
		x += db_generic_insdel(buf, __FILE__, __LINE__);
	}

	return x;
}

void db_load_progs(AreaData * tarea)
{
	ProgList *prg;
	flag_t trigger;

	if (!tarea)
	{
		bug("db_load_progs: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
		{
			return;
		}
	}

	if (!aname_query(PROG_TABLE_NAME, tarea->name, PROG_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		if (!str_cmp(row[2], "MOB"))
		{
			CharIndex *pMobIndex;

			pMobIndex = get_mob_index(atov(row[1]));
			if (!pMobIndex)
				bugf("db_load_progs: 'MOB': vnum %ld.", pMobIndex->vnum);

			prg = new_prog_list();
			if ((trigger = flag_value(mprog_flags, row[2])) == NO_FLAG)
			{
				bug("MOBprogs: invalid trigger.");
				exit(1);
			}
			SetBit(pMobIndex->mprog_flags, trigger);
			prg->trig_type = trigger;
			prg->prog = (ProgCode *) atol(row[3]);
			prg->trig_phrase = str_dup(row[4]);
			Link(prg, pMobIndex->mprog, next, prev);
		}
		else if (!str_cmp(row[2], "OBJ"))
		{
			ObjIndex *obj;

			obj = get_obj_index(atov(row[1]));
			if (!obj)
				bug("db_load_progs: 'OBJ': vnum %ld.", atov(row[1]));

			prg = new_prog_list();
			if ((trigger = flag_value(oprog_flags, row[2])) == NO_FLAG)
			{
				bug("OBJprogs: invalid trigger.");
				exit(1);
			}
			SetBit(obj->oprog_flags, trigger);
			prg->trig_type = trigger;
			prg->prog = (ProgCode *) atol(row[3]);
			prg->trig_phrase = str_dup(row[4]);
			Link(prg, obj->oprog, next, prev);
		}
		else if (!str_cmp(row[2], "ROOM"))
		{
			RoomIndex *room;

			room = get_room_index(atov(row[1]));
			if (!room)
				bug("db_load_progs: 'ROOM': vnum %ld.", atov(row[1]));

			prg = new_prog_list();
			if ((trigger = flag_value(rprog_flags, row[2])) == NO_FLAG)
			{
				bug("ROOMprogs: invalid trigger.");
				exit(1);
			}
			SetBit(room->rprog_flags, trigger);
			prg->trig_type = trigger;
			prg->prog = (ProgCode *) atol(row[3]);
			prg->trig_phrase = str_dup(row[4]);
			Link(prg, room->mprog, next, prev);
		}
	}

	mysql_free_result(res);
}

int db_insert_resets(bool del, RoomIndex * room)
{
	ResetData *treset;
	char buf[MAX_STRING_LENGTH * 8];
	int x = 0;

	if (!room || !room->area)
	{
		bug("db_insert_resets: !area");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where aname='%s'", RESET_TABLE_NAME,
				escape_string(room->area->name));
		db_generic_insdel(buf, __FILE__, __LINE__);
	}

	for (treset = room->reset_first; treset; treset = treset->next)
	{
		sprintf(buf, "insert into %s values('%s','%c',%ld,%ld,%ld,%ld)",
				RESET_TABLE_NAME, escape_string(room->area->name),
				UPPER(treset->command), treset->arg1, treset->arg2,
				treset->arg3, treset->arg4);
		x += db_generic_insdel(buf, __FILE__, __LINE__);
	}

	return x;
}

void db_load_resets(AreaData * tarea)
{
	char buf[MAX_INPUT_LENGTH];
	int count = 0;
	vnum_t rVnum = -1;

	if (!tarea)
	{
		bug("db_load_resets: no #AREA seen yet.");
		if (run_level == RUNLEVEL_BOOTING)
		{
			shutdown_mud("No #AREA");
			exit(1);
		}
		else
			return;
	}

	if (!aname_query(RESET_TABLE_NAME, tarea->name, RESET_TABLE_ROWS))
		return;

	while ((row = mysql_fetch_row(res)))
	{
		RoomIndex *room;
		ResetData *reset;
		ExitData *pexit;
		flag_t arg5;

		reset = new_reset();

		reset->command = row[1][0];

		reset->arg1 = atov(row[2]);
		reset->arg2 = atoi(row[3]);
		reset->arg3 = (letter == 'G') ? 0 : atov(row[4]);
		reset->arg4 = (letter == 'P' || letter == 'M') ? atoi(row[5]) : 0;
		arg5 = (letter == 'F') ? parse_flags(row[cnt++]) : 0;

		++count;

		switch (letter)
		{
			case 'M':
			case 'O':
				rVnum = arg3;
				break;

			case 'P':
			case 'G':
			case 'E':
				break;

			case 'D':
				room = get_room_index((rVnum = reset->arg1));

				if (reset->arg2 < 0 || reset->arg2 >= MAX_DIR || !room
					|| (pexit = room->exit[reset->arg2]) == NULL
					|| !IsSet(pexit->rs_flags, EX_ISDOOR))
				{
					bug("db_load_resets: 'D': exit %d not door on room %ld.",
						reset->arg2, reset->arg1);
					exit(1);
				}
				switch (arg3)
				{
					default:
						bugf("Load_resets: 'D': bad 'locks': %ld.",
							 reset->arg3);
						break;
					case 0:
						break;
					case 1:
						SetBit(pexit->rs_flags, EX_CLOSED);
						SetBit(pexit->exit_info, EX_CLOSED);
						break;
					case 2:
						SetBit(pexit->rs_flags, EX_CLOSED | EX_LOCKED);
						SetBit(pexit->exit_info, EX_CLOSED | EX_LOCKED);
						break;
				}
				break;

			case 'F':
				room = get_room_index((rVnum = reset->arg1));

				if (reset->arg2 < 0 || reset->arg2 >= MAX_DIR || !room
					|| !(pexit = room->exit[reset->arg2]))
				{
					bug("db_load_resets: 'F': bad exit %d on room %ld.",
						reset->arg2, reset->arg1);
					break;
				}
				pexit->rs_flags = arg5;
				pexit->exit_info = arg5;
				break;
			case 'R':
				rVnum = reset->arg1;
				break;
		}

		if (rVnum == -1)
		{
			bugf("load_resets : rVnum == -1");
			exit(1);
		}

		if (reset->command != 'D' && reset->command != 'F')
			add_reset(get_room_index(rVnum), reset, 0);
		else
			free_reset(reset);
	}

	mysql_free_result(res);
}

int db_insert_area(bool del, AreaData * area)
{
	char buf[MAX_STRING_LENGTH * 8];

	if (!area)
	{
		bug("db_insert_area: !area");
		return 0;
	}

	if (del)
	{
		sprintf(buf, "delete from %s where aname='%s'", AREA_TABLE_NAME,
				aname);
		db_generic_insdel(buf, __FILE__, __LINE__);
	}

	RemBit(pArea->area_flags, OLC_CHANGED);
/*
	sprintf(buf, "insert into %s values('%s','%s',",
			AREA_TABLE_NAME,
			escape_string(area->name), escape_string(area->file_name));

	strcatf(buf, "'%s',%ld,%ld,'%s','%s','%s',",
			escape_string(area->builders), area->min_vnum, area->max_vnum,
			escape_string(area->credits), escape_string(area->lvl_comment),
			escape_string(area->resetmsg));
	strcatf(buf, "%d,%d,%d,%d,'%s',", area->min_level, area->max_level,
			AREA_VERSION, area->security,
			area->clan ? escape_string(area->clan->name) : "");
	strcatf(buf, "%d,%d,%d,%ld,'%s',%ld,%ld,", area->weather.climate_temp,
			area->weather.climate_precip, area->weather.climate_wind,
			area->recall, write_flags(area->area_flags), area->kills,
			area->deaths);

	return db_generic_insdel(buf, __FILE__, __LINE__); */
	return db_insert_data_table(AREA_TABLE_NAME, &area_zero, area_data_table,
								area);
}

void db_load_area()
{
	AreaData *tarea;
	int i = 0;

	tarea = new_area();
/*	tarea->name = str_dup(arow[i++]);
	tarea->file_name = str_dup(arow[i++]);
	tarea->builders = str_dup(arow[i++]);
	tarea->min_vnum = atov(arow[i++]);
	tarea->max_vnum = atov(arow[i++]);
	tarea->credits = str_dup(arow[i++]);
	tarea->lvl_comment = str_dup(arow[i++]);
	tarea->resetmsg = str_dup(arow[i++]);
	tarea->min_level = atoi(arow[i++]);
	tarea->max_level = atoi(arow[i++]);
	tarea->version = atoi(arow[i++]);
	tarea->security = atoi(arow[i++]);
	tarea->clan = clan_lookup(arow[i++]);
	tarea->weather.climate_temp = atoi(arow[i++]);
	tarea->weather.climate_precip = atoi(arow[i++]);
	tarea->weather.climate_wind = atoi(arow[i++]);
	tarea->recall = atov(arow[i++]);
	tarea->area_flags = parse_flags(arow[i++]);
	tarea->kills = atol(arow[i++]);
	tarea->deaths = atol(arow[i++]);*/
	db_load_datatable(row, &area_zero, area_data_table, tarea);

	add_area(tarea);
	current_area = tarea;
	convert_area_credits(tarea);

	db_load_objects(tarea);
	db_load_mobiles(tarea);
	db_load_rooms(tarea);
	db_load_exits(tarea);
	db_load_objaffects(tarea);
	db_load_progs(tarea);
	db_load_specials(tarea);
	db_load_shops(tarea);
	db_load_descs(tarea);
	db_load_resets(tarea);
}

void db_load_areas()
{
	char buf[MAX_STRING_LENGTH];

	if (db_first_run)
	{
		load_area_db();
		return;
	}

	sprintf(buf, "select * from %s order by start_range", AREA_TABLE_NAME);

	if (mysql_query(&mysql, buf))
	{
		exiterr(13, __FILE__, __LINE__);
		return;
	}

	if (!(ares = mysql_store_result(&mysql)))
	{
		exiterr(14, __FILE__, __LINE__);
		return;
	}

	if (mysql_num_fields(ares) != AREA_TABLE_ROWS)
	{
		logf("%s: expected %d fields got %d", AREA_TABLE_NAME,
			 AREA_TABLE_ROWS, mysql_num_fields(ares));
		return;
	}

	lock_tables(OBJ_TABLE_NAME " read, " MOB_TABLE_NAME " read, "
				ROOM_TABLE_NAME " read, " \ EXIT_TABLE_NAME " read, "
				OBJAFF_TABLE_NAME " read, " PROG_TABLE_NAME " read, " \
				SPEC_TABLE_NAME " read, " CLIM_TABLE_NAME " read, "
				NEIGH_TABLE_NAME " read, " \ SHOP_TABLE_NAME " read, "
				RSHOP_TABLE_NAME " read, " DESC_TABLE_NAME " read, " \
				RESET_TABLE_NAME " read");

	while ((arow = mysql_fetch_row(ares)))
	{
		db_load_area();
	}

	unlock_tables();

	mysql_free_result(ares);
}

void db_del_area(AreaData * area)
{
	char buf[MAX_INPUT_LENGTH];
	const char *aname;

	lock_tables(OBJ_TABLE_NAME " write, " MOB_TABLE_NAME " write, "
				ROOM_TABLE_NAME " write, " \ EXIT_TABLE_NAME " write, "
				OBJAFF_TABLE_NAME " write, " PROG_TABLE_NAME " write, " \
				SPEC_TABLE_NAME " write, " CLIM_TABLE_NAME " write, "
				NEIGH_TABLE_NAME " write, " \ SHOP_TABLE_NAME " write, "
				RSHOP_TABLE_NAME " write, " DESC_TABLE_NAME " write, " \
				RESET_TABLE_NAME " write, " AREA_TABLE_NAME " write");

	aname = escape_string(area->name);

	sprintf(buf, "delete from %s where aname='%s'", MOB_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", OBJ_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", ROOM_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", SHOP_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", RSHOP_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", SPEC_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", CLIM_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", DESC_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", EXIT_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", NEIGH_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", OBJAFF_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", PROG_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", RESET_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);
	sprintf(buf, "delete from %s where aname='%s'", AREA_TABLE_NAME, aname);
	db_generic_insdel(buf, __FILE__, __LINE__);

	unlock_tables();

}

int db_insert_helps()
{
	HelpData *help;
	char buf[MAX_STRING_LENGTH * 8];
	int x = 0;

	sprintf(buf, "delete from %s", HELP_TABLE_NAME);
	db_generic_insdel(buf, __FILE__, __LINE__);

	for (help = first_help; help; help = help->next)
	{
		/*
		   sprintf(buf, "insert into %s values(%d,'%s','%s',%d)",
		   HELP_TABLE_NAME,
		   help->level, escape_string(help->keywords),
		   escape_string(help->text) help->category);

		   x += db_generic_insdel(buf, __FILE__, __LINE__); */
		x +=
			db_insert_data_table(HELP_TABLE_NAME, &help_zero, help_data_table,
								 help);
	}

	return x;
}

void db_load_helps()
{
	HelpData *pHelp;
	char buf[MAX_STRING_LENGTH];

	log_string("Loading helps...");
	sprintf(buf, "select * from %s", HELP_TABLE_NAME);

	if (mysql_query(&mysql, buf))
	{
		exiterr(15, __FILE__, __LINE__);
		return;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(16, __FILE__, __LINE__);
		return;
	}

	if (mysql_num_fields(res) != HELP_TABLE_ROWS)
	{
		logf("%s: expected %d fields got %d", HELP_TABLE_NAME,
			 HELP_TABLE_ROWS, mysql_num_fields(res));
		return;
	}

	while ((row = mysql_fetch_row(res)))
	{
		pHelp = new_help();
/*		pHelp->level = atoi(row[0]);
		pHelp->keyword = str_dup(row[1]);
		pHelp->text = str_dup(row[2]);
		pHelp->category = (help_t) atoi(row[3]);
*/
		db_load_table(row, &help_zero, help_data_table, pHelp);
		add_help(pHelp);
	}

	mysql_free_result(res);
}

int db_insert_commands()
{
	CmdData *command;
	char buf[MAX_STRING_LENGTH];
	int x, y = 0;

	sprintf(buf, "delete from %s", COMMAND_TABLE_NAME);
	db_generic_insdel(buf, __FILE__, __LINE__);

	for (x = 0; x < MAX_CMD_HASH; x++)
	{
		for (command = command_hash[x]; command; command = command->next)
		{
			if (NullStr(command->name))
			{
				bug("db_insert_commands: blank command in hash bucket %d", x);
				continue;
			}
/*
			sprintf(buf, "insert into %s values('%s','%s',%d,%d,%d,%d,'%s')",
					COMMAND_TABLE_NAME, escape_string(command->name),
					escape_string(cmd_name(command->do_fun)),
					command->position, command->level, command->log,
					command->category, flag_string(cmd_flags,
												   command->flags));

			y += db_generic_insdel(buf, __FILE__, __LINE__); */
			y +=
				db_load_table(COMMAND_TABLE_NAME, &cmd_zero, cmd_data_table,
							  command);
		}
	}

	return y;
}

void db_load_commands()
{
	CmdData *command;
	char buf[MAX_STRING_LENGTH];

	log_string("Loading commands...");
	sprintf(buf, "select * from %s", COMMAND_TABLE_NAME);

	if (mysql_query(&mysql, buf))
	{
		exiterr(17, __FILE__, __LINE__);
		return;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(18, __FILE__, __LINE__);
		return;
	}

	if (mysql_num_fields(res) != COMMAND_TABLE_ROWS)
	{
		logf("%s: expected %d fields got %d", COMMAND_TABLE_NAME,
			 COMMAND_TABLE_ROWS, mysql_num_fields(res));
		return;
	}

	while ((row = mysql_fetch_row(res)))
	{
		command = new_cmd();
/*		command->name = str_dup(row[0]);
		command->do_fun =
			(Do_F *) index_lookup(row[1], dofun_index, (void *) do_null);
		command->position = (position_t) atoi(row[2]);
		command->level = atoi(row[3]);
		command->log = (log_t) atoi(row[4]);
		command->category = (cmd_cat) atoi(row[5]);
		command->flags = flag_value(cmd_flags, row[6]);
*/
		if (NullStr(command->name))
		{
			bug("db_load_commands: Name not found");
			free_command(command);
			continue;
		}
		if (!command->do_fun)
		{
			bug("db_load_commands: Function not found");
			free_command(command);
			continue;
		}
		if (command->do_fun == do_null)
			command->level = MAX_LEVEL;
		db_load_datatable(row, &cmd_zero, cmd_data_table, command);
		add_command(command);
	}

	mysql_free_result(res);
}

int db_insert_socials()
{
	SocialData *social;
	char buf[MAX_STRING_LENGTH];
	int x, y = 0;

	sprintf(buf, "delete from %s", SOCIAL_TABLE_NAME);
	db_generic_insdel(buf, __FILE__, __LINE__);

	for (x = 0; x < MAX_SOCIAL_HASH; x++)
	{
		for (social = social_index[x]; social; social = social->next)
		{
			if (NullStr(social->name))
			{
				bugf("db_insert_socials: blank social in hash bucket %d", x);
				continue;
			}
			/*
			   sprintf(buf,
			   "insert into %s values('%s','%s','%s','%s','%s','%s','%s','%s')",
			   SOCIAL_TABLE_NAME, escape_string(social->name),
			   escape_string(social->char_no_arg),
			   escape_string(social->others_no_arg),
			   escape_string(social->char_found),
			   escape_string(social->others_found),
			   escape_string(social->victim_found),
			   escape_string(social->char_auto),
			   escape_string(social->others_auto));

			   y += db_generic_insdel(buf, __FILE__, __LINE__); */
			y +=
				db_insert_data_table(SOCIAL_TABLE_NAME, &social_zero,
									 social_data_table, social);
		}
	}

	return y;
}

void db_load_socials()
{
	SocialData *social;
	char buf[MAX_STRING_LENGTH];

	log_string("Loading socials...");
	sprintf(buf, "select * from %s", SOCIAL_TABLE_NAME);

	if (mysql_query(&mysql, buf))
	{
		exiterr(19, __FILE__, __LINE__);
		return;
	}

	if (!(res = mysql_store_result(&mysql)))
	{
		exiterr(20, __FILE__, __LINE__);
		return;
	}

	if (mysql_num_fields(res) != SOCIAL_TABLE_ROWS)
	{
		logf("%s: expected %d fields got %d", SOCIAL_TABLE_NAME,
			 SOCIAL_TABLE_ROWS, mysql_num_fields(res));
		return;
	}

	while ((row = mysql_fetch_row(res)))
	{
		social = new_social();
/*
		social->name = str_dup(row[0]);
		social->char_no_arg = str_dup(row[1]);
		social->others_no_arg = str_dup(row[2]);
		social->char_found = str_dup(row[3]);
		social->others_found = str_dup(row[4]);
		social->vict_found = str_dup(row[5]);
		social->char_auto = str_dup(row[6]);
		social->others_auto = str_dup(row[7]);
*/
		db_load_datatable(row, &social_zero, social_data_table, social);
		add_social(social);
	}

	mysql_free_result(res);
}

int db_insert_skills()
{
	char buf[MAX_INPUT_LENGTH];
	int x, y = 0, i;

	sprintf(buf, "delete from %s", SKILL_TABLE_NAME);
	db_generic_insdel(buf, __FILE__, __LINE__);

	for (x = 0; x < top_skill; x++)
	{
/*		SkillData *skill = &skill_table[x];

		sprintf(buf, "insert into %s values('%s',%d", SKILL_TABLE_NAME,
				skill->name, top_class);
		for (i = 0; i < top_class; i++)
			strcatf(buf, ",%d,%d", skill->skill_level[i], skill->rating[i]);
		strcatf(buf, ",'%s'",
				index_name((void *) skill->spell_fun, spell_index,
						   "spell_null"));
		strcatf(buf, ",'%s','%s'",
				escape_string(flag_string(target_flags, skill->target)),
				escape_string(flag_string(position_flags, skill->position)));
		strcatf(buf, ",'%s'", index_name(skill->pgsn, gsn_index, "gsn_null"));
		strcatf(buf, ",%d,%d,'%s'", skill->min_mana, skill->beats,
				escape_string(skill->noun_damage));
		strcatf(buf, ",'%s','%s'", escape_string(skill->msg_off),
				escape_string(skill->msg_obj));
		strcat(buf, db_print_sound(skill->sound));
		strcat(buf, ")");

		y += db_generic_insdel(buf, __FILE__, __LINE__); */
		y +=
			db_insert_data_table(SKILL_TABLE_NAME, &skill_zero,
								 skill_data_table, &skill_table[x]);
	}
	return y;
}

void db_load_skill_table()
{
	char buf[MAX_STRING_LENGTH];

	log_string("Loading skills...");
	sprintf(buf, "select * from %s", SKILL_TABLE_NAME);

	if (mysql_query(&mysql, buf))
	{
		exiterr(23, __FILE__, __LINE__);
		return;
	}

	if (!(ares = mysql_store_result(&mysql)))
	{
		exiterr(24, __FILE__, __LINE__);
		return;
	}

	if (mysql_num_fields(ares) != SKILL_TABLE_ROWS)
	{
		logf("%s: expected %d fields got %d", SKILL_TABLE_NAME,
			 SKILL_TABLE_ROWS, mysql_num_fields(ares));
		return;
	}

	while ((arow = mysql_fetch_row(ares)))
	{
		SkillData *skill;
		int i = 0, j, t;

		top_skill++;
		skill_table = realloc_mem(skill_table, SkillData, top_skill + 1);
		skill = &skill_table[top_skill];
/*		skill->name = str_dup(arow[i++]);
		alloc_mem(skill->skill_level, int, top_class);
		alloc_mem(skill->ratings, int, top_class);

		t = atoi(row[i++]);
		for (j = 0; j < Min(t, top_class); j++)
		{
			skill->skill_level[j] = atoi(arow[i++]);
			skill->ratings[j] = atoi(arow[i++]);
		}
		while (j < top_class)
		{
			skill->skill_level[j] = LEVEL_IMMORTAL + 3;
			skill->ratings[j] = 0;
			i++, j++;
		}
		skill->spell_fun =
			(Spell_F *) index_lookup(arow[i++], spell_index,
									 (void *) spell_null);
		skill->target = (tar_t) flag_value(target_flags, arow[i++]);
		skill->position = (position_t) flag_value(position_flags, arow[i++]);
		skill->pgsn =
			(int *) index_lookup(arow[i++], gsn_index, (void *) &gsn_null);
		skill->min_mana = atoi(arow[i++]);
		skill->beats = atoi(arow[i++]);
		skill->noun_damage = str_dup(arow[i++]);
		skill->msg_off = str_dup(arow[i++]);
		skill->msg_obj = str_dup(arow[i++]);
		skill->sound = db_read_sound(&arow[i]);
*/
		db_load_datatable(arow, &skill_zero, skill_data_table,
						  &skill_table[top_skill]);
	}

	mysql_free_result(ares);
}

#endif
