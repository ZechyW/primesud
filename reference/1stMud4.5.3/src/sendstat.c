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

// About: The code within this module sends to firstmud.com statistical
// information.  Using this information we are able to
// get an idea of the number of 1stmud based muds running and
// hopefully the number of players.
//
// The statistical information submitted to firstmud.com is a
// summary of mudstats, combined with a few other things specific to 
// your mud environment (such as the name of the mud).  Only the info
// relavent to possible players is posted publicly, the rest is for
// the developers of 1stmud.  The SENDSTAT_SECURE_LEVEL define can be
// used to limit some of the info as you see fit, but please leave the 
// unique_id, name, and version if possible.
//
// By default the mud after about 10 minutes of running will
// send the stats to http://firstmud.com/scripts/post/post.php
// This does not lag the mud in anyway, (unless your dns resolver
// is broken - use sockets to determine this), if the dns resolver
// is broken there may be a one off small delay (ordinarily less
// than 5 seconds) while the mud resolves the ip address of
// firstmud.com in order to know where to send the
// stats to.
//

#include "merc.h"
#include "recycle.h"
#include "tables.h"
#include "olc.h"

#ifndef DISABLE_SENDSTAT

//#define SENDSTAT_LOG_PROGRESS
#define SENDSTAT_SUBMIT_DOMAIN  "1stmud.dlmud.com"
#define SENDSTAT_SUBMIT_URL     "/scripts/post.php"

/* Determines the level of information sent to create
   a mud listing.
   1 - minimal
   2 - average
   3 - all
*/
#define SENDSTAT_SECURE_LEVEL    	2

void sendstat_logf(const char *fmt, ...)
{
	char buf[MSL];
	va_list args;

#ifndef SENDSTAT_LOG_PROGRESS

	return;
#endif

	if (NullStr(fmt))
		return;

	va_start(args, fmt);
	vsnprintf(buf, MSL, fmt, args);
	va_end(args);

	logf("sendstat: %s", buf);
}

const char *url_encode_table[] = {
	"%00", "%01", "%02", "%03", "%04", "%05", "%06", "%07",
	"%08", "%09", "%0A", "%0B", "%0C", "%0D", "%0E", "%0F",
	"%10", "%11", "%12", "%13", "%14", "%15", "%16", "%17",
	"%18", "%19", "%1A", "%1B", "%1C", "%1D", "%1E", "%1F",
	"+", "!", "%22", "%23", "$", "%25", "%26", "%27",
	"(", ")", "*", "%2B", ",", "-", ".", "%2F",
	"0", "1", "2", "3", "4", "5", "6", "7",
	"8", "9", "%3A", "%3B", "%3C", "%3D", "%3E", "%3F",
	"%40", "A", "B", "C", "D", "E", "F", "G",
	"H", "I", "J", "K", "L", "M", "N", "O",
	"P", "Q", "R", "S", "T", "U", "V", "W",
	"X", "Y", "Z", "%5B", "%5C", "%5D", "%5E", "_",
	"%60", "a", "b", "c", "d", "e", "f", "g",
	"h", "i", "j", "k", "l", "m", "n", "o",
	"p", "q", "r", "s", "t", "u", "v", "w",
	"x", "y", "z", "%7B", "%7C", "%7D", "%7E", "%7F",
	"%80", "%81", "%82", "%83", "%84", "%85", "%86", "%87",
	"%88", "%89", "%8A", "%8B", "%8C", "%8D", "%8E", "%8F",
	"%90", "%91", "%92", "%93", "%94", "%95", "%96", "%97",
	"%98", "%99", "%9A", "%9B", "%9C", "%9D", "%9E", "%9F",
	"%A0", "%A1", "%A2", "%A3", "%A4", "%A5", "%A6", "%A7",
	"%A8", "%A9", "%AA", "%AB", "%AC", "%AD", "%AE", "%AF",
	"%B0", "%B1", "%B2", "%B3", "%B4", "%B5", "%B6", "%B7",
	"%B8", "%B9", "%BA", "%BB", "%BC", "%BD", "%BE", "%BF",
	"%C0", "%C1", "%C2", "%C3", "%C4", "%C5", "%C6", "%C7",
	"%C8", "%C9", "%CA", "%CB", "%CC", "%CD", "%CE", "%CF",
	"%D0", "%D1", "%D2", "%D3", "%D4", "%D5", "%D6", "%D7",
	"%D8", "%D9", "%DA", "%DB", "%DC", "%DD", "%DE", "%DF",
	"%E0", "%E1", "%E2", "%E3", "%E4", "%E5", "%E6", "%E7",
	"%E8", "%E9", "%EA", "%EB", "%EC", "%ED", "%EE", "%EF",
	"%F0", "%F1", "%F2", "%F3", "%F4", "%F5", "%F6", "%F7",
	"%F8", "%F9", "%FA", "%FB", "%FC", "%FD", "%FE", "%FF"
};

char *url_encode_post_data(const char *postdata)
{
	static char *result;
	unsigned char *s;
	const char *t;
	char *d;

	if (result)
	{
		free_mem(result);
	}
	alloc_mem(result, char, strlen(postdata) * 3 + 1);

	d = result;

	for (s = (unsigned char *) postdata; *s; s++)
	{
		t = url_encode_table[*s];
		while (*t)
		{
			*d++ = *t++;
		}
	}
	*d = '\0';
	return result;
}

char *sendstat_generate_statistics_text()
{
	static char result[45000];
	char stats[45000];
	char *encoded;
	int len;

	stats[0] = NUL;

	/* required to post data on site */
	strcatf(stats, "&unique_id=%d", mud_info.unique_id);
	/* required to post data on site */
	strcatf(stats, "&name=%s", url_encode_post_data(mud_info.name));

/* level 1 security: minimal */
#if SENDSTAT_SECURE_LEVEL >= 1
	strcatf(stats, "&hostname=%s", url_encode_post_data(HOSTNAME));
	strcatf(stats, "&version=%s", url_encode_post_data(MUDVERSION));
	strcatf(stats, "&mainport=%d", mainport);
#ifndef DISABLE_WEBSRV
	strcatf(stats, "&webport=%d", webport);
#endif
	strcatf(stats, "&areas=%d", top_area);
	strcatf(stats, "&rooms=%d", top_room_index);
	strcatf(stats, "&shops=%d", top_shop);
	strcatf(stats, "&explorable_rooms=%d", top_explored);
	strcatf(stats, "&resets=%d", top_reset);
	strcatf(stats, "&exits=%d", top_exit);
	strcatf(stats, "&extra_descriptions=%d", top_ed);
	strcatf(stats, "&affects=%d", top_affect);
	strcatf(stats, "&mobiles=%d", top_char_index);
	strcatf(stats, "&mobile_count=%d", mobile_count);
	strcatf(stats, "&objects=%d", top_obj_index);
	strcatf(stats, "&object_count=%d", top_obj);
	strcatf(stats, "&mob_programs=%d", top_mprog);
	strcatf(stats, "&obj_programs=%d", top_oprog);
	strcatf(stats, "&room_programs=%d", top_rprog);
	strcatf(stats, "&helps=%d", top_help);
	strcatf(stats, "&max_online=%d", mud_info.stats.online);
	strcatf(stats, "&logins=%d", mud_info.stats.logins);
	strcatf(stats, "&quests=%d", mud_info.stats.quests);
	strcatf(stats, "&qcomplete=%d", mud_info.stats.qcomplete);
	strcatf(stats, "&levels=%d", mud_info.stats.levels);
	strcatf(stats, "&newbies=%d", mud_info.stats.newbies);
	strcatf(stats, "&deletions=%d", mud_info.stats.deletions);
	strcatf(stats, "&mobdeaths=%d", mud_info.stats.mobdeaths);
	strcatf(stats, "&auctions=%d", mud_info.stats.auctions);
	strcatf(stats, "&aucsold=%d", mud_info.stats.aucsold);
	strcatf(stats, "&pdied=%d", mud_info.stats.pdied);
	strcatf(stats, "&pkill=%d", mud_info.stats.pkill);
	strcatf(stats, "&notes=%d", mud_info.stats.notes);
	strcatf(stats, "&remorts=%d", mud_info.stats.remorts);
	strcatf(stats, "&wars=%d", mud_info.stats.wars);
	strcatf(stats, "&gquests=%d", mud_info.stats.gquests);
	strcatf(stats, "&connections=%d", mud_info.stats.connections);
	strcatf(stats, "&longest_uptime=%s",
			timestr(mud_info.longest_uptime, false));
	strcatf(stats, "&web_requests=%d", mud_info.stats.web_requests);
	strcatf(stats, "&chan_msgs=%d", mud_info.stats.chan_msgs);
	strcatf(stats, "&hero_level=%d", LEVEL_HERO);
	strcatf(stats, "&immortal_level=%d", LEVEL_IMMORTAL);
	strcatf(stats, "&max_level=%d", MAX_LEVEL);
	strcatf(stats, "&current_time=%s",
			url_encode_post_data(str_time(-1, -1, NULL)));
	strcatf(stats, "&timezone=%s",
			url_encode_post_data(str_time(-1, -1, "%z %Z")));
	strcatf(stats, "&races=%d", top_race);
	strcatf(stats, "&classes=%d", top_class);
	strcatf(stats, "&skills=%d", top_skill);
	strcatf(stats, "&groups=%d", top_group);
	strcatf(stats, "&socials=%d", top_social);
	strcatf(stats, "&clans=%d", top_clan);
	strcatf(stats, "&commands=%d", top_cmd);
	strcatf(stats, "&deities=%d", top_deity);
	strcatf(stats, "&songs=%d", top_song);
	strcatf(stats, "&channels=%d", top_channel);
	strcatf(stats, "&pfiles=%d", pfiles.count);
	strcatf(stats, "&mudflags=%s",
			url_encode_post_data(flag_string(mud_flags, mud_info.mud_flags)));
	strcatf(stats, "&boot_time=%s",
			url_encode_post_data(str_time(boot_time, -1, NULL)));
	strcatf(stats, "&current_time=%s",
			url_encode_post_data(str_time(-1, -1, NULL)));
#ifndef DISABLE_MCCP
	strcatf(stats, "&MCCP=%s", url_encode_post_data("yes"));
#endif
	strcatf(stats, "&bans=%d", top_ban);
	strcatf(stats, "&disabled_cmds=%d", top_disabled);
	strcatf(stats, "&clan_members=%d", top_mbr);
	strcatf(stats, "&msp_sounds=%d", top_msp);

/* level 2 security: average */
#elif SENDSTAT_SECURE_LEVEL >= 2
#ifdef __cplusplus
	strcatf(stats, "&Cplus=%s", url_encode_post_data("yes"));
#endif
	strcatf(stats, "&default_port=%d", mud_info.default_port);
	strcatf(stats, "&min_save_lvl=%d", mud_info.min_save_lvl);
	strcatf(stats, "&group_lvl_range=%d", mud_info.group_lvl_limit);
	strcatf(stats, "&pcdam_mod=%d", mud_info.pcdam);
	strcatf(stats, "&mobdam_mod=%d", mud_info.mobdam);
	strcatf(stats, "&creation_point_mod=%d", mud_info.max_points);
	strcatf(stats, "&str_count=%d", nAllocString);
	strcatf(stats, "&str_size=%d", sAllocString);
	strcatf(stats, "&share_value=%d", mud_info.share_value);
#ifdef __DATE__
	strcatf(stats, "&compiled_date=%s", url_encode_post_data(__DATE__));
#endif
#ifdef __TIME__
	strcatf(stats, "&compiled_time=%s", url_encode_post_data(__TIME__));
#endif
#ifdef __CYGWIN__
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("cygwin"));
#elif defined WIN32
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("Win32"));
#elif defined unix
#ifdef linux
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("linux"));
#elif defined __OpenBSD__
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("OpenBSD"));
#elif defined __FreeBSD__
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("FreeBSD"));
#elif defined __NetBSD__
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("NetBSD"));
#elif defined BSD
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("BSD"));
#else
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("unix"));
#endif
#else
	strcatf(stats, "&compiled_platform=%s", url_encode_post_data("unknown"));
#endif
#ifdef __VERSION__
	strcatf(stats, "&compiler_version=%s", url_encode_post_data(__VERSION__));
#endif

/* level 3 security: all */
#elif SENDSTAT_SECURE_LEVEL >= 3
	strcatf(stats, "&bind_ip=%s",
			url_encode_post_data(mud_info.bind_ip_address));
	strcatf(stats, "&max_stats=%d", MAX_STATS);
	strcatf(stats, "&pulsepersec=%d", mud_info.pulsepersec);
	strcatf(stats, "&top_vnum_room=%ld", top_vnum_room);
	strcatf(stats, "&top_vnum_obj=%ld", top_vnum_obj);
	strcatf(stats, "&top_vnum_mob=%ld", top_vnum_mob);
	strcatf(stats, "&max_key_hash=%d", MAX_KEY_HASH);
	strcatf(stats, "&max_string_length=%d", MAX_STRING_LENGTH);
	strcatf(stats, "&max_input_length=%d", MAX_INPUT_LENGTH);
	/* up to you! */
	strcatf(stats, "&uname=%s", url_encode_post_data(UNAME));
	strcatf(stats, "&curr_directory=%s", url_encode_post_data(CWDIR));
	strcatf(stats, "&exe_file=%s", url_encode_post_data(EXE_FILE));
	strcatf(stats, "&platform_info=%s",
			url_encode_post_data(get_platform_info()));
#endif

	encoded = &stats[1];
	len = strlen(encoded);

	sprintf(result,
			"POST " SENDSTAT_SUBMIT_URL "  HTTP/1.1\r\n"
			"Content-Type: application/x-www-form-urlencoded\r\n" "Host: "
			SENDSTAT_SUBMIT_DOMAIN "\r\n"
			"User-Agent: Mozilla/4.0 (compatible; " MUDNAME
			"SendStat/1.0;)\r\n" "Content-Length: %d\r\n"
			"Cache-Control: no-cache\r\n" "\r\n%s", len, encoded);

	return result;
}

char *sendstat_stattext_to_post;

typedef enum
{
	SENDSTATSTAGE_WAIT,
	SENDSTATSTAGE_DOMAIN_RESOLVED,
	SENDSTATSTAGE_CONNECT_IN_PROGRESS,
	SENDSTATSTAGE_GENERATE_STATS,
	SENDSTATSTAGE_POSTING,
	SENDSTATSTAGE_CLOSE_CONNECT,
	SENDSTATSTAGE_COMPLETED,
	SENDSTATSTAGE_ABORTED
}
sendstat_stages;

sendstat_stages sendstat_stage = SENDSTATSTAGE_WAIT;
time_t sendstat_connect_timeout = 0;

struct in_addr sendstat_address;
static SOCKET sendstat_socket;

void sendstat_resolve_domain()
{

	if (!inet_aton(SENDSTAT_SUBMIT_DOMAIN, &sendstat_address))
	{
		if (sendstat_address.s_addr == 0)
		{
			struct hostent *hostp = gethostbyname(SENDSTAT_SUBMIT_DOMAIN);

			if (!hostp)
			{

				sendstat_logf("failed to resolve '%s.'",
							  SENDSTAT_SUBMIT_DOMAIN);
				sendstat_stage = SENDSTATSTAGE_ABORTED;
				return;
			}
			memcpy(&sendstat_address, hostp->h_addr, hostp->h_length);
		}
	}
	sendstat_logf("resolved '%s' as %s", SENDSTAT_SUBMIT_DOMAIN,
				  inet_ntoa(sendstat_address));
	sendstat_stage = SENDSTATSTAGE_DOMAIN_RESOLVED;
}

struct sockaddr_in sockaddress;

void sendstat_initiate_connection()
{
	SOCKET nRet;

	sendstat_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
	if (sendstat_socket == INVALID_SOCKET)
	{
		sendstat_logf("Error creating connection socket");
		return;
	}

	sockaddress.sin_family = AF_INET;
	sockaddress.sin_addr.s_addr = sendstat_address.s_addr;
	sockaddress.sin_port = htons(80);

	if (!socket_cntl(sendstat_socket))
	{
		sendstat_logf("error setting new socket to nonblocking");
		sendstat_stage = SENDSTATSTAGE_ABORTED;
		return;
	}

	nRet =
		connect(sendstat_socket, (SOCKADDR *) & sockaddress,
				sizeof(sockaddress));

	if (nRet == 0)
	{					// successful connection, jump straight to generating the stats to post
		sendstat_stage = SENDSTATSTAGE_GENERATE_STATS;
		return;
	}

#ifdef WIN32
	if (WSAGetLastError() != WSAEWOULDBLOCK)
	{
		sendstat_logf("sendstat_initiate_connection(): connect() error %d",
					  WSAGetLastError());
		sendstat_stage = SENDSTATSTAGE_ABORTED;
		return;
	}
#else
	if (nRet < 0)
	{
		if (errno != EINPROGRESS && errno != EALREADY)
		{
			sendstat_logf
				("sendstat_initiate_connection(): connect() error %d", errno);
			sendstat_stage = SENDSTATSTAGE_ABORTED;
			return;
		}
	}
#endif

	sendstat_connect_timeout = current_time + 200;

	sendstat_logf("connection initiation successful");
	sendstat_stage = SENDSTATSTAGE_CONNECT_IN_PROGRESS;
	return;
}

void sendstat_process_connect()
{
	SOCKET nRet;

	if (sendstat_connect_timeout < current_time)
	{
		sendstat_logf
			("sendstat_process_connect(): pending connection timed out.");
		sendstat_stage = SENDSTATSTAGE_ABORTED;
		return;
	}

	sendstat_logf("processing connection %s:80", inet_ntoa(sendstat_address));
#ifdef WIN32
	{

		struct timeval select_timeout;
		fd_set fdWrite;
		fd_set fdExcept;

		select_timeout.tv_sec = 0;
		select_timeout.tv_usec = 0;

		FD_ZERO(&fdWrite);
		FD_SET(sendstat_socket, &fdWrite);
		FD_ZERO(&fdExcept);
		FD_SET(sendstat_socket, &fdExcept);

		nRet =
			select(sendstat_socket + 1, NULL, &fdWrite, &fdExcept,
				   &select_timeout);

		if (nRet < 1)
		{
			if (nRet)
			{
				sendstat_logf
					("sendstat_process_connect(): select() returned error");
				sendstat_stage = SENDSTATSTAGE_ABORTED;
			}
			return;
		}

		if (FD_ISSET(sendstat_socket, &fdWrite))
		{

			sendstat_logf
				("sendstat_process_connect(): connection established.");
			sendstat_stage = SENDSTATSTAGE_GENERATE_STATS;
			return;
		}

		if (FD_ISSET(sendstat_socket, &fdExcept))
		{

			sendstat_logf("sendstat_process_connect(): connection failed.");
		}
		else
		{
			sendstat_logf
				("sendstat_process_connect(): don't know how we got here!");
		}
		sendstat_stage = SENDSTATSTAGE_ABORTED;
		return;
	}
#else

	nRet =
		connect(sendstat_socket, (SOCKADDR *) & sockaddress,
				sizeof(sockaddress));

	if (nRet == 0)
	{

		sendstat_stage = SENDSTATSTAGE_GENERATE_STATS;
		return;
	}
	if (nRet < 0)
	{
		if (errno != EINPROGRESS && errno != EALREADY)
		{
			sendstat_logf("sendstat_process_connect(): connect() error %d",
						  errno);
			sendstat_stage = SENDSTATSTAGE_ABORTED;
			return;
		}
	}
#endif
	return;
}

void sendstat_generate_stats()
{
	sendstat_stattext_to_post = sendstat_generate_statistics_text();
	if (NullStr(sendstat_stattext_to_post))
	{
		sendstat_logf
			("sendstat_generate_stats(): An error occured generating statistics.");
		sendstat_stage = SENDSTATSTAGE_ABORTED;
	}
	else
		sendstat_stage = SENDSTATSTAGE_POSTING;
}

void sendstat_post()
{
	char *msg = sendstat_stattext_to_post;

	int written;
	int msglen = strlen(msg);

	written = write_to_socket(sendstat_socket, msg, msglen);

	if (written < 0)
	{
		sendstat_logf
			("sendstat_post(): An error occured posting statistics.");
		sendstat_stage = SENDSTATSTAGE_ABORTED;
		return;
	}

	if (written < msglen)
	{
		sendstat_logf
			("Incomplete write, sent %d bytes of %d, write rest later",
			 written, msglen);
		sendstat_stattext_to_post += written;
		return;
	}

	sendstat_logf("Submitted %d bytes", written);

	sendstat_stage = SENDSTATSTAGE_CLOSE_CONNECT;
}
#endif

time_t last_sendstat_post;

Do_Fun(do_sendstat)
{
#ifdef DISABLE_SENDSTAT
	chprintlnf(ch,
			   "Posting {n statistics to http://" SENDSTAT_SUBMIT_DOMAIN
			   "/muds/%s%d.php is disabled.", mud_info.name,
			   mud_info.unique_id);
#else
	while (sendstat_stage != SENDSTATSTAGE_ABORTED
		   && sendstat_stage != SENDSTATSTAGE_COMPLETED)
	{
		sendstat_resolve_domain();
		sendstat_initiate_connection();
		sendstat_process_connect();
		sendstat_generate_stats();
		sendstat_post();
		closesocket(sendstat_socket);
		last_sendstat_post = current_time;
		sendstat_stage = SENDSTATSTAGE_COMPLETED;
	}

	if (sendstat_stage == SENDSTATSTAGE_COMPLETED)
		chprintln(ch,
				  "{n statistics sent to http://" SENDSTAT_SUBMIT_DOMAIN
				  SENDSTAT_SUBMIT_URL ".");
	else
		chprintln(ch,
				  "There was an error posting {n statistics on http://"
				  SENDSTAT_SUBMIT_DOMAIN SENDSTAT_SUBMIT_URL ".");
#endif
}

void sendstat_update(void)
{
#ifndef DISABLE_SENDSTAT
	static time_t wait_until = 0;

	if ((int) sendstat_stage < (int) SENDSTATSTAGE_COMPLETED)
	{
		if (!wait_until || sendstat_stage != SENDSTATSTAGE_WAIT)
		{
			sendstat_logf("sendstat_update(%d)", (int) sendstat_stage);
		}
	}

	switch (sendstat_stage)
	{
		case SENDSTATSTAGE_WAIT:
			if (wait_until == 0)
			{
				wait_until = current_time + MINUTE * 30;
			}
			else if (wait_until < current_time)
			{

				wait_until = 0;
				sendstat_logf("moving on to resolving stage.");
				sendstat_resolve_domain();
			}
			break;

		case SENDSTATSTAGE_DOMAIN_RESOLVED:
			sendstat_logf("initiating connection to '%s:80'",
						  inet_ntoa(sendstat_address));
			sendstat_initiate_connection();
			break;

		case SENDSTATSTAGE_CONNECT_IN_PROGRESS:
			sendstat_logf("processing connection.");
			sendstat_process_connect();
			break;

		case SENDSTATSTAGE_GENERATE_STATS:
			sendstat_logf("generating statistics.");
			sendstat_generate_stats();
			break;

		case SENDSTATSTAGE_POSTING:
			sendstat_logf("posting statistics.");
			sendstat_post();
			break;

		case SENDSTATSTAGE_CLOSE_CONNECT:
			sendstat_logf("closing socket.");
			closesocket(sendstat_socket);
			sendstat_stage = SENDSTATSTAGE_COMPLETED;
			break;

		case SENDSTATSTAGE_COMPLETED:
			last_sendstat_post = current_time;
		case SENDSTATSTAGE_ABORTED:

		{
			static time_t redo_in = 0;

			if (redo_in)
			{
				if (redo_in < current_time)
				{
					sendstat_logf("restarting sendstats");

					sendstat_stage = SENDSTATSTAGE_WAIT;
					redo_in = 0;
				}
			}
			else
			{
				redo_in = current_time + (24 * HOUR);
			}

		}
		default:
			break;
	};
#endif
}
