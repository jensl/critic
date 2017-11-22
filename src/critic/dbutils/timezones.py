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

import datetime


async def loadTimezones(critic):
    """
    Insert (interesting) timezones from 'pg_timezone_names' into 'timezones'

    The 'pg_timezone_names' table contains all the information we want (but
    typically unnecessarily many different timezones) but is very slow to query,
    so can't be used during normal operations.
    """

    from critic import base

    if base.configuration()["database.driver"] != "postgresql":
        return

    async def insert_timezone(cursor, name, abbrev, utc_offset):
        await cursor.execute(
            """INSERT INTO timezones (name, abbrev, utc_offset)
               VALUES ({name}, {abbrev}, {utc_offset})""",
            name=name,
            abbrev=abbrev,
            utc_offset=utc_offset,
        )

    timezones = []
    async with critic.query(
        """SELECT name, abbrev, utc_offset
                 FROM pg_timezone_names"""
    ) as result:
        async for full_name, abbrev, utc_offset in result:
            region, _, name = full_name.partition("/")
            if region not in ("posix", "Etc") and name and "/" not in name:
                timezones.append((full_name, abbrev, utc_offset))

    async with critic.transaction() as cursor:
        await cursor.execute("DELETE FROM timezones")

        await insert_timezone(cursor, "Universal/UTC", "UTC", datetime.timedelta())

        for name, abbrev, utc_offset in timezones:
            await insert_timezone(cursor, name, abbrev, utc_offset)


async def updateTimezones(critic):
    """
    Update UTC offses in 'timezones' with values in 'pg_timezone_names'

    The UTC offsets in 'pg_timezone_names' are DST adjusted (for the timezones
    we care about) so we need to copy the values regularly to keep the cached
    values in 'timezones' up-to-date.
    """

    from critic import base

    if base.configuration()["database.driver"] != "postgresql":
        return

    async with critic.transaction() as cursor:
        await cursor.execute(
            """UPDATE timezones
                  SET utc_offset=pg_timezone_names.utc_offset
                 FROM pg_timezone_names
                WHERE pg_timezone_names.name=timezones.name"""
        )
