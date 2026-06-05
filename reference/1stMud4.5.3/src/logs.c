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
* The Dawn of Time v1.69q (c)1997-2002 Michael Garratt                    *
* >> A number of people have contributed to the Dawn codebase, with the   *
*    majority of code written by Michael Garratt - www.dawnoftime.org     *
* >> To use this source code, you must fully comply with the dawn license *
*    in licenses.txt... In particular, you may not remove this copyright  *
*    notice.                                                              *
***************************************************************************
*          1stMud ROM Derivative (c) 2001-2004 by Markanth                *
*            http://www.firstmud.com/  <markanth@firstmud.com>            *
*         By using this code you have agreed to follow the term of        *
*             the 1stMud license in ../doc/1stMud/LICENSE                 *
***************************************************************************/

#include "merc.h"

#define LOG_TIME_MAGIC_NUM    	666
#define LOG_TIME_FMT    "%b %e %H:%M:%S"

time_t last_current_time;
time_t cycle_log_after;
bool log_hold_log_string_core_stdout_restore_value;
bool log_string_core_stdout_enabled = true;
char initial_startup_log_buffer[7 * MSL + 1];
bool initial_startup_log_buffer_full = false;
FILE *current_logfile_descriptor = NULL;
char current_logfile_name[MSL];

time_t get_tomorrow_start(void)
{
	struct tm now;
	time_t tommorrow_start;

	now = *localtime(&current_time);

	now.tm_sec = 0;
	now.tm_min = 0;
	now.tm_hour = 0;
	now.tm_mday++;

	tommorrow_start = mktime(&now);

	return tommorrow_start;
}

FILE *get_new_logfile(int portprefix, char *logfilename)
{
	sprintf(logfilename, "%s%d-%s.log", LOG_DIR, portprefix,
			str_time(-1, -1, "%m-%d"));

	return fopen(logfilename, "w");
}

static void log_str_fmt(FILE * file, const char *str)
{
	if (!file)
		return;

	if (last_current_time == LOG_TIME_MAGIC_NUM)
		fprintf(file, "%s\n", str);
	else if (!NullStr(str))
	{
		if (last_current_time == current_time)
			fprintf(file, "%15s :: %s\n", " ", str);
		else
			fprintf(file, "%15s :: %s\n", str_time(-1, -1, LOG_TIME_FMT),
					str);
	}
}

static void log_string_core_stdout(const char *str)
{
	if (log_string_core_stdout_enabled)
	{
		log_str_fmt(stdout, str);
	}
}

void log_hold_till_commandline_options_parsed(void)
{
	log_hold_log_string_core_stdout_restore_value =
		log_string_core_stdout_enabled;
	log_string_core_stdout_enabled = false;

}

void log_release_held_logs(void)
{
	log_string_core_stdout_enabled =
		log_hold_log_string_core_stdout_restore_value;
	if (!NullStr(initial_startup_log_buffer))
		log_string_core_stdout(initial_startup_log_buffer);
}

void write_log_index(char *str)
{
	append_file(LOG_INDEX_FILE,
				FORMATF("[%d] %s :: %s", getpid(),
						str_time(-1, -1, LOG_TIME_FMT), str), true);
}

void log_string_flush()
{
	fflush(stdout);
	if (current_logfile_descriptor)
	{
		fflush(current_logfile_descriptor);
	}
}

void log_string_core(const char *str)
{
	if (!mainport)
	{
		int pos;

		log_string_core_stdout(str);

		if (!initial_startup_log_buffer_full
			&& (pos =
				strlen(initial_startup_log_buffer)) + strlen(str) <
			sizeof(initial_startup_log_buffer) - 100)
		{
			sprintf(&initial_startup_log_buffer[pos], "%15s :: %s\n",
					"startup buffer", str);
		}
		else
		{
			initial_startup_log_buffer_full = true;
			logf
				("initial_startup_log_buffer exceeded, some logging information will be lost.");
		}
		return;
	}

	if (IsSet(mud_info.cmdline_options, CMDLINE_NO_LOGFILE))
	{
		log_string_core_stdout(str);
		return;
	}

	if (current_logfile_descriptor && cycle_log_after < current_time)
	{
		char new_logfile_name[MSL];
		FILE *new_logfile_descriptor;

		cycle_log_after = get_tomorrow_start();

		new_logfile_descriptor = get_new_logfile(mainport, new_logfile_name);

		logf("transfering logging from %s to %s", current_logfile_name,
			 new_logfile_name);

		log_string_flush();
		fclose(current_logfile_descriptor);
		current_logfile_descriptor = new_logfile_descriptor;
		new_logfile_descriptor = NULL;

		logf("logging continuation of %s", current_logfile_name);

		strcpy(current_logfile_name, new_logfile_name);
		new_logfile_name[0] = '\0';
	}
	if (!current_logfile_descriptor)
	{
		int portprefix = mainport;

		mainport = 0;

		current_logfile_descriptor =
			get_new_logfile(portprefix, current_logfile_name);

		cycle_log_after = get_tomorrow_start();

		mainport = portprefix;
		if (current_logfile_descriptor)
		{
			log_string_core(initial_startup_log_buffer);
			initial_startup_log_buffer[0] = '\0';
			if (initial_startup_log_buffer_full)
			{
				logf
					("initial_startup_log_buffer exceeded, some logging information will be lost.");
				initial_startup_log_buffer_full = false;
			}
			logf("Logging to %s", current_logfile_name);

			write_log_index("============================================");
			write_log_index(FORMATF
							("%s logging to %s", EXE_FILE,
							 current_logfile_name));

#ifdef HAVE_WORKING_FORK
			if (IsSet
				(mud_info.cmdline_options, CMDLINE_NO_BACKGROUND_PROCESS))
			{
				logf("Mud remaining in foreground, process id = %d.",
					 getpid());
			}
			else
			{
				pid_t fork_result;

				logf("switching to daemon mode (background running process)");

				fork_result = fork();

				if (fork_result < 0)
				{
					bugf
						("switching to background daemon failed! errno=%d (%s)",
						 errno, strerror(errno));
				}
				else if (fork_result)
				{

					sleep_seconds(1);
					exit(1);
				}
				if (setsid() < 0)
				{

					bugf("failed to set new session id.");
				}
				logf
					("The mud is now running in the background, process id = %d.",
					 getpid());
			}
#endif
			if (!IsSet(mud_info.cmdline_options, CMDLINE_LOG_CONSOLE))
			{
				log_string_core_stdout_enabled = false;
			}
		}
	}

	log_string_core_stdout(str);

	if (current_logfile_descriptor)
	{
		log_str_fmt(current_logfile_descriptor, str);
	}
}

void log_string(const char *str)
{
	if (IsSet(run_level, RUNLEVEL_INIT))
	{
		return;
	}

	log_string_core(str);
	last_current_time = current_time;
	log_string_flush();
	return;
}

void fulltime_log_string(const char *str)
{
	if (IsSet(run_level, RUNLEVEL_INIT))
	{
		return;
	}
	last_current_time = 0;
	log_string_core(str);
	log_string_flush();
	return;
}

void log_bar(void)
{
	last_current_time = LOG_TIME_MAGIC_NUM;
	log_string(draw_line(NULL, "*", 0));
}

void log_note(const char *text)
{
	const char *msg;

	log_bar();
	msg = str_dup(text);
	msg = format_string(msg);
	msg = string_replace_all(msg, "{}", "\n");
	log_string(msg);
	free_string(msg);

	log_bar();
}

void log_notef(const char *fmt, ...)
{
	char buf[MPL];
	va_list args;

	va_start(args, fmt);
	vsnprintf(buf, sizeof(buf) - 100, fmt, args);
	va_end(args);

	log_note(buf);
}

void log_error(const char *str)
{
#ifdef HAVE_STRERROR
	log_str_fmt(stderr, FORMATF("%s - %s", strerror(errno), str));
	logf("%s - %s", strerror(errno), str);
#else
	perror(str);
	log_string(str);
#endif
	last_current_time = current_time;
	return;
}

void logf_error(const char *fmt, ...)
{
	char buf[MPL];

	if (!NullStr(fmt))
	{
		va_list args;

		va_start(args, fmt);
		vsnprintf(buf, sizeof(buf), fmt, args);
		va_end(args);
	}
	else
		buf[0] = NUL;
	log_error(buf);
}
