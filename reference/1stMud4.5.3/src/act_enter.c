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
#include "interp.h"
#include "tables.h"

RoomIndex *get_random_room(CharData * ch)
{
	RoomIndex *room;

	for (;;)
	{
		room = get_room_index(number_range(0, 65535));
		if (room != NULL)
			if (can_see_room(ch, room) && !room_is_private(room)
				&& !IsSet(room->room_flags, ROOM_PRIVATE)
				&& !IsSet(room->room_flags, ROOM_SOLITARY)
				&& !IsSet(room->area->area_flags, AREA_CLOSED)
				&& !IsSet(room->room_flags, ROOM_ARENA)
				&& !IsSet(room->room_flags, ROOM_SAFE) && (IsNPC(ch)
														   || IsSet(ch->act,
																	ACT_AGGRESSIVE)
														   ||
														   !IsSet
														   (room->room_flags,
															ROOM_LAW)))
				break;
	}

	return room;
}

Do_Fun(do_enter)
{
	RoomIndex *location;

	if (ch->fighting != NULL)
		return;

	if (!NullStr(argument))
	{
		RoomIndex *old_room;
		ObjData *portal;
		CharData *fch, *fch_next;

		old_room = ch->in_room;

		portal = get_obj_list(ch, argument, ch->in_room->content_first);

		if (portal == NULL)
		{
			chprintln(ch, "You don't see that here.");
			return;
		}

		if (portal->item_type != ITEM_PORTAL
			|| (IsSet(portal->value[1], EX_CLOSED) && !IsTrusted(ch, ANGEL)))
		{
			chprintln(ch, "You can't seem to find a way in.");
			return;
		}

		if (!IsTrusted(ch, ANGEL) && !IsSet(portal->value[2], GATE_NOCURSE)
			&& (IsAffected(ch, AFF_CURSE)
				|| IsSet(old_room->room_flags, ROOM_NO_RECALL)))
		{
			chprintln(ch, "Something prevents you from leaving...");
			return;
		}

		if (IsSet(portal->value[2], GATE_RANDOM) || portal->value[3] == -1)
		{
			location = get_random_room(ch);
			portal->value[3] = location->vnum;
		}
		else if (IsSet(portal->value[2], GATE_BUGGY)
				 && (number_percent() < 5))
			location = get_random_room(ch);
		else
			location = get_room_index(portal->value[3]);

		if (location == NULL || location == old_room
			|| !can_see_room(ch, location) || (room_is_private(location)
											   && !IsTrusted(ch,
															 IMPLEMENTOR)))
		{
			act("$p doesn't seem to go anywhere.", ch, portal, NULL, TO_CHAR);
			return;
		}

		if (IsNPC(ch) && IsSet(ch->act, ACT_AGGRESSIVE)
			&& IsSet(location->room_flags, ROOM_LAW))
		{
			chprintln(ch, "Something prevents you from leaving...");
			return;
		}

		act("$n steps into $p.", ch, portal, NULL, TO_ROOM);

		if (IsSet(portal->value[2], GATE_NORMAL_EXIT))
			act("You enter $p.", ch, portal, NULL, TO_CHAR);
		else
			act("You walk through $p and find yourself somewhere else...", ch,
				portal, NULL, TO_CHAR);

		char_from_room(ch);
		char_to_room(ch, location);

		if (IsSet(portal->value[2], GATE_GOWITH))
		{
			obj_from_room(portal);
			obj_to_room(portal, location);
		}

		if (IsSet(portal->value[2], GATE_NORMAL_EXIT))
			act("$n has arrived.", ch, portal, NULL, TO_ROOM);
		else
			act("$n has arrived through $p.", ch, portal, NULL, TO_ROOM);

		do_function(ch, &do_look, "auto");

		if (portal->value[0] > 0)
		{
			portal->value[0]--;
			if (portal->value[0] == 0)
				portal->value[0] = -1;
		}

		if (old_room == location)
			return;

		for (fch = old_room->person_first; fch != NULL; fch = fch_next)
		{
			fch_next = fch->next_in_room;

			if (portal == NULL || portal->value[0] == -1)

				continue;

			if (fch->master == ch && IsAffected(fch, AFF_CHARM)
				&& fch->position < POS_STANDING)
				do_function(fch, &do_stand, "");

			if (fch->master == ch && fch->position == POS_STANDING)
			{

				if (IsSet(ch->in_room->room_flags, ROOM_LAW)
					&& (IsNPC(fch) && IsSet(fch->act, ACT_AGGRESSIVE)))
				{
					act("You can't bring $N into the city.", ch, NULL, fch,
						TO_CHAR);
					act("You aren't allowed in the city.", fch, NULL, NULL,
						TO_CHAR);
					continue;
				}

				act("You follow $N.", fch, NULL, ch, TO_CHAR);
				do_function(fch, &do_enter, argument);
			}
		}

		if (portal != NULL && portal->value[0] == -1)
		{
			act("$p fades out of existence.", ch, portal, NULL, TO_CHAR);
			if (ch->in_room == old_room)
				act("$p fades out of existence.", ch, portal, NULL, TO_ROOM);
			else if (old_room->person_first != NULL)
			{
				act("$p fades out of existence.", old_room->person_first,
					portal, NULL, TO_CHAR);
				act("$p fades out of existence.", old_room->person_first,
					portal, NULL, TO_ROOM);
			}
			extract_obj(portal);
		}

		if (IsNPC(ch) && HasTriggerMob(ch, TRIG_ENTRY))
			p_percent_trigger(ch, NULL, NULL, NULL, NULL, NULL, TRIG_ENTRY);
		if (!IsNPC(ch))
		{
			p_greet_trigger(ch, PRG_MPROG);
			p_greet_trigger(ch, PRG_OPROG);
			p_greet_trigger(ch, PRG_RPROG);
		}

		return;
	}

	chprintln(ch, "Nope, can't do it.");
	return;
}

Do_Fun(do_worship)
{
	CharData *priest;
	DeityData *i;

	if (NullStr(argument))
	{
		cmd_syntax(ch, NULL, n_fun, "<deity>", "list", NULL);
		return;
	}

	if (!str_cmp(argument, "list"))
	{
		int e;

		for (e = ETHOS_LAWFUL_GOOD; e != ETHOS_CHAOTIC_EVIL; e--)
		{
			for (i = deity_first; i; i = i->next)
			{
				if (i->ethos != (ethos_t) e)
					continue;

				chprintlnf(ch, "\t%-12s (%s): %s", i->name,
						   flag_string(ethos_types, i->ethos), i->desc);
			}
		}
		return;
	}

	for (priest = ch->in_room->person_first; priest != NULL;
		 priest = priest->next_in_room)
		if (IsNPC(priest) && IsSet(priest->act, ACT_IS_HEALER))
			break;

	if (priest == NULL)
	{
		chprintln(ch, "There is no priest here!");
		return;
	}

	if (ch->pcdata->quest.points < 250)
	{
		chprintln(ch, "You need 250 questpoints to change your deity.");
		return;
	}

	i = deity_lookup(argument);

	if (i == NULL)
	{
		chprintln(ch, "That deity doesn't exist.");
		return;
	}

	ch->deity = i;
	chprintlnf(ch, "You now worship %s.", i->name);
	ch->pcdata->quest.points -= 250;
	return;
}

Do_Fun(do_heel)
{
	if (ch->pet == NULL)
	{
		chprintln(ch, "You don't have a pet!");
		return;
	}
	if (IsSet(ch->in_room->room_flags, ROOM_ARENA))
	{
		act("$N can't hear your whistle with all the screaming.", ch, NULL,
			ch->pet, TO_CHAR);
		return;
	}
	char_from_room(ch->pet);
	char_to_room(ch->pet, ch->in_room);
	act("$n lets out a loud whistle and $N comes running.", ch, NULL, ch->pet,
		TO_ROOM);
	act("You let out a loud whistle and $N comes running.", ch, NULL, ch->pet,
		TO_CHAR);
}

char *path_to_area(CharData * ch, AreaData * pArea)
{
	ExitData *pexit, *pexit2;
	RoomIndex *pRoomIndex, *queueIn, *queueOut, *source;
	int iHash = 0, door, door2;
	static char buf[MAX_STRING_LENGTH], buf2[MAX_STRING_LENGTH];

	if ((source = ch->in_room) == NULL)
		return "Not accessable.";

	if (!pArea)
	{
		bug("passing invalid area");
		return "Ah this is an error.";
	}

	if (AreaFlag(pArea, AREA_CLOSED) || pArea->clan)
		return "Restricted Area.";

	if (source->area == pArea)
		return "You are here.";

	buf[0] = NUL;
	for (iHash = 0; iHash < MAX_KEY_HASH; iHash++)
	{
		for (pRoomIndex = room_index_hash[iHash]; pRoomIndex != NULL;
			 pRoomIndex = pRoomIndex->next)
		{
			pRoomIndex->distance_from_source = INT_MAX;
			pRoomIndex->shortest_from_room = NULL;
			pRoomIndex->shortest_next_room = NULL;
		}
	}
	source->distance_from_source = 0;
	queueIn = source;
	for (queueOut = source; queueOut; queueOut = queueOut->shortest_next_room)
	{
		if (AreaFlag(queueOut->area, AREA_PLAYER_HOMES)
			|| queueOut->area->clan != NULL)
			continue;

		for (door = 0; door < MAX_DIR; door++)
		{
			if ((pexit = queueOut->exit[door]) != NULL
				&& pexit->u1.to_room != NULL)
			{
				if (pexit->u1.to_room->distance_from_source >
					queueOut->distance_from_source + 1)
				{
					pexit->u1.to_room->distance_from_source =
						queueOut->distance_from_source + 1;
					if (pexit->u1.to_room->area == pArea)
					{
						int count = 1;
						char buf3[3];

						sprintf(buf3, "%c", dir_name[door][0]);
						sprintf(buf2, "%s", buf3);
						for (pRoomIndex = queueOut;
							 pRoomIndex->shortest_from_room;
							 pRoomIndex = pRoomIndex->shortest_from_room)
						{
							for (door2 = 0; door2 < MAX_DIR; door2++)
							{
								if (
									(pexit2 =
									 pRoomIndex->shortest_from_room->
									 exit[door2]) != NULL
									&& pexit2->u1.to_room == pRoomIndex)
								{
									if (dir_name[door2][0] == buf3[0])
									{
										count++;
									}
									else
									{
										sprintf(buf, "%s", buf2);
										if (count > 1)
										{

											sprintf(buf2, "%c%d%s",
													dir_name[door2][0], count,
													buf);
										}
										else
										{
											sprintf(buf2, "%c%s",
													dir_name[door2][0], buf);
										}
										count = 1;
										sprintf(buf3, "%c",
												dir_name[door2][0]);
									}
								}
							}
						}
						if (count > 1)
						{
							sprintf(buf, "%s", buf2);
							sprintf(buf2, "%d%s", count, buf);
						}
						sprintf(buf, "%s", buf2);
						return (buf);
					}
					pexit->u1.to_room->shortest_from_room = queueOut;
					queueIn->shortest_next_room = pexit->u1.to_room;
					queueIn = pexit->u1.to_room;
				}
			}
		}
	}
	return "Not accessable.";
}

Do_Fun(do_path)
{
	RoomIndex *pRoomIndex, *queueIn, *queueOut, *source, *destination = NULL;
	int iHash, door, door2;
	ExitData *pexit, *pexit2;
	char buf[MAX_STRING_LENGTH], buf2[MAX_STRING_LENGTH];
	bool fArea = false;
	CharData *victim = NULL;
	AreaData *area;

	// Use a breadth-first search to find shortest path.
	if (NullStr(argument))
	{
		cmd_syntax(ch, NULL, n_fun, "<destination player, mob, or area>",
				   NULL);
		return;
	}
	// First, find source and destination rooms:
	if ((source = ch->in_room) == NULL)
	{
		chprintln(ch, "You must be somewhere to go anywhere.");
		return;
	}

	if ((area = area_lookup(argument)) != NULL)
	{
		destination = area_begin(area);
		fArea = true;
	}
	else if ((victim = get_char_world(ch, argument)) != NULL
			 || victim->in_room == NULL || !can_see_room(ch, victim->in_room)
			 || IsSet(victim->in_room->room_flags,
					  ROOM_SAFE | ROOM_ARENA | ROOM_PRIVATE | ROOM_SOLITARY |
					  ROOM_NO_RECALL)
			 || IsSet(ch->in_room->room_flags, ROOM_ARENA | ROOM_NO_RECALL)
			 || (IsNPC(victim)
				 && is_gqmob(NULL, victim->pIndexData->vnum) != -1)
			 || (IsNPC(victim) && IsQuester(ch)
				 && ch->pcdata->quest.mob == victim)
			 || victim->level >= ch->level + 3 || (is_clan(victim)
												   && !is_same_clan(ch,
																	victim))
			 || (!IsNPC(victim) && victim->level >= MAX_MORTAL_LEVEL)
			 || (IsNPC(victim) && IsSet(victim->imm_flags, IMM_SUMMON))
			 || (IsNPC(victim) && saves_spell(ch->level, victim, DAM_OTHER)))
		destination = victim->in_room;

	if (destination == NULL)
	{
		chprintln(ch, "No such destination.");
		return;
	}

	if ((fArea && source->area == destination->area) || source == destination)
	{
		chprintln(ch, "No need to walk to get there!");
		return;
	}

	if (AreaFlag(destination->area, AREA_CLOSED) || destination->area->clan)
	{
		chprintln(ch, "That area is restricted.");
		return;
	}

	for (iHash = 0; iHash < MAX_KEY_HASH; iHash++)
	{
		for (pRoomIndex = room_index_hash[iHash]; pRoomIndex != NULL;
			 pRoomIndex = pRoomIndex->next)
		{
			pRoomIndex->distance_from_source = INT_MAX;
			pRoomIndex->shortest_from_room = NULL;
			pRoomIndex->shortest_next_room = NULL;
		}
	}
	// Now set source distance to 0 and put it on the "search" queue
	source->distance_from_source = 0;
	queueIn = source;
	// Now, set distance for all adjacent rooms to search room + 1 until
	// destination.
	// If destination not found, put each unsearched adjacent room on queue
	// and repeat
	for (queueOut = source; queueOut; queueOut = queueOut->shortest_next_room)
	{
		if (AreaFlag(queueOut->area, AREA_PLAYER_HOMES)
			|| queueOut->area->clan != NULL)
			continue;

		// for each exit to search room:
		for (door = 0; door < MAX_DIR; door++)
		{
			if ((pexit = queueOut->exit[door]) != NULL
				&& pexit->u1.to_room != NULL)
			{
				// if we haven't looked here, set distance and add to search
				// list
				if (pexit->u1.to_room->distance_from_source >
					queueOut->distance_from_source + 1)
				{
					pexit->u1.to_room->distance_from_source =
						queueOut->distance_from_source + 1;
					// if we've found destination, we're done!
					if (
						(fArea
						 && pexit->u1.to_room->area == destination->area)
						|| pexit->u1.to_room == destination)
					{
						int count = 1;
						char buf3[3];

						// print the directions in reverse order as we walk
						// back
						sprintf(buf3, "%c", dir_name[door][0]);
						sprintf(buf2, "%s", buf3);
						for (pRoomIndex = queueOut;
							 pRoomIndex->shortest_from_room;
							 pRoomIndex = pRoomIndex->shortest_from_room)
						{
							for (door2 = 0; door2 < MAX_DIR; door2++)
							{
								if (
									(pexit2 =
									 pRoomIndex->shortest_from_room->
									 exit[door2]) != NULL
									&& pexit2->u1.to_room == pRoomIndex)
								{
									if (dir_name[door2][0] == buf3[0])
									{
										count++;
									}
									else
									{
										sprintf(buf, "%s", buf2);
										if (count > 1)
										{
											sprintf(buf2, "%c%d%s",
													dir_name[door2][0], count,
													buf);
										}
										else
										{
											sprintf(buf2, "%c%s",
													dir_name[door2][0], buf);
										}
										count = 1;
										sprintf(buf3, "%c",
												dir_name[door2][0]);
									}
								}
							}
						}
						if (count > 1)
						{
							sprintf(buf, "%s", buf2);
							sprintf(buf2, "%d%s", count, buf);
						}
						if (fArea)
						{
							chprintlnf(ch,
									   "Shortest path to %s is %d steps: %s.",
									   destination->area->name,
									   pexit->u1.
									   to_room->distance_from_source, buf2);
						}
						else if (victim)
						{
							chprintlnf(ch,
									   "Shortest path to %s is %d steps: %s.",
									   GetName(victim),
									   pexit->u1.
									   to_room->distance_from_source, buf2);
						}
						return;
					}
					// Didn't find destination, add to queue
					pexit->u1.to_room->shortest_from_room = queueOut;
					queueIn->shortest_next_room = pexit->u1.to_room;
					queueIn = pexit->u1.to_room;
				}
			}
		}
	}
	chprintln(ch, "No path to destination.");
	return;
}
