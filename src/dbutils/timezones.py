# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import time
import datetime

def loadTimezones(db):
    """
    Insert (interesting) timezones from 'pg_timezone_names' into 'timezones'

    The 'pg_timezone_names' table contains all the information we want (but
    typically unnecessarily many different timezones) but is very slow to query,
    so can't be used during normal operations.
    """

    import configuration

    def add(name, abbrev, utc_offset):
        cursor.execute("""INSERT INTO timezones (name, abbrev, utc_offset)
                               VALUES (%s, %s, %s)""",
                       (name, abbrev, utc_offset))

    if configuration.database.DRIVER == "postgresql":
        with db.updating_cursor("timezones") as cursor:
            cursor.execute("DELETE FROM timezones")

            add("Universal/UTC", "UTC", datetime.timedelta())

            cursor.execute("SELECT name, abbrev, utc_offset FROM pg_timezone_names")
            for full_name, abbrev, utc_offset in cursor.fetchall():
                region, _, name = full_name.partition("/")
                if region not in ("posix", "Etc") and name and "/" not in name:
                    add(full_name, abbrev, utc_offset)

def updateTimezones(db):
    """
    Update UTC offses in 'timezones' with values in 'pg_timezone_names'

    The UTC offsets in 'pg_timezone_names' are DST adjusted (for the timezones
    we care about) so we need to copy the values regularly to keep the cached
    values in 'timezones' up-to-date.
    """

    import configuration

    if configuration.database.DRIVER == "postgresql":
        with db.updating_cursor("timezones") as cursor:
            cursor.execute("""UPDATE timezones
                                 SET utc_offset=pg_timezone_names.utc_offset
                                FROM pg_timezone_names
                               WHERE pg_timezone_names.name=timezones.name""")

def __fetchTimezones(db):
    groups = db.storage["Timezones"].get(None, {})

    if not groups:
        cursor = db.readonly_cursor()
        cursor.execute("SELECT name, abbrev, utc_offset FROM timezones")

        for full_name, abbrev, utc_offset in cursor.fetchall():
            group, name = full_name.split("/")
            if isinstance(utc_offset, int):
                utc_offset = datetime.timedelta(utc_offset)
            groups.setdefault(group, {})[name] = (abbrev, utc_offset)

        db.storage["Timezones"][None] = groups

    return groups

def sortedTimezones(db):
    groups = __fetchTimezones(db)
    result = []

    for key in sorted(groups.keys()):
        result.append((key, sorted([(name, abbrev, utc_offset) for name, (abbrev, utc_offset) in groups[key].items()])))

    return result

def __fetchUTCOffset(db, timezone):
    utc_offset = db.storage["Timezones"].get(timezone)

    if utc_offset is None:
        groups = db.storage["Timezones"].get(None)

        if groups:
            group, name = timezone.split("/")
            utc_offset = groups[group][name][2]
        else:
            cursor = db.readonly_cursor()
            cursor.execute("SELECT utc_offset FROM timezones WHERE name=%s", (timezone,))

            row = cursor.fetchone()
            if row:
                utc_offset = row[0]
            else:
                return 0

        db.storage["Timezones"][timezone] = utc_offset

    return utc_offset

def adjustTimestamp(db, timestamp, timezone):
    return timestamp + __fetchUTCOffset(db, timezone)

def formatTimestamp(db, timestamp, timezone):
    utc_offset = __fetchUTCOffset(db, timezone)
    seconds = utc_offset.total_seconds()
    offset = " %s%02d:%02d" % ("-" if seconds < 0 else "+", seconds / 3600, (seconds % 3600) / 60)

    return time.strftime("%Y-%m-%d %H:%M", (timestamp + utc_offset).timetuple()) + offset

def validTimezone(db, timezone):
    cursor = db.readonly_cursor()
    cursor.execute("SELECT 1 FROM timezones WHERE name=%s", (timezone,))
    return bool(cursor.fetchone())
