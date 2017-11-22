# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import logging

logger = logging.getLogger(__name__)

from critic import base
from critic import data

name = "install:preferences"
description = "Install/update the set of preferences in Critic's database."

driver = None


def query(string):
    if driver.paramstyle == "qmark":
        return string.replace("%s", "?")
    return string


def update_preference(critic, item, data):
    relevance = data.get("relevance", {})

    cursor = critic.database.cursor()
    cursor.execute(query("SELECT 1 FROM preferences WHERE item=%s"), (item,))

    if cursor.fetchone():
        cursor.execute(
            query(
                """UPDATE preferences
                      SET description=%s,
                          per_system=%s,
                          per_user=%s,
                          per_repository=%s,
                          per_filter=%s
                    WHERE item=%s"""
            ),
            (
                data["description"],
                relevance.get("system", True),
                relevance.get("user", True),
                relevance.get("repository", False),
                relevance.get("filter", False),
                item,
            ),
        )
    else:
        cursor.execute(
            query(
                """INSERT
                     INTO preferences (
                            item, type, description, per_system, per_user,
                            per_repository, per_filter
                          )
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            ),
            (
                item,
                data["type"],
                data["description"],
                relevance.get("system", True),
                relevance.get("user", True),
                relevance.get("repository", False),
                relevance.get("filter", False),
            ),
        )

    cursor.execute(
        query(
            """DELETE
                 FROM userpreferences
                WHERE item=%s
                  AND uid IS NULL
                  AND repository IS NULL
                  AND filter IS NULL"""
        ),
        (item,),
    )

    if data["type"] == "string":
        cursor.execute(
            query(
                """INSERT INTO userpreferences (item, string)
                   VALUES (%s, %s)"""
            ),
            (item, data["default"]),
        )
    else:
        cursor.execute(
            query(
                """INSERT INTO userpreferences (item, integer)
                   VALUES (%s, %s)"""
            ),
            (item, int(data["default"])),
        )


def setup(parser):
    parser.set_defaults(need_session=True)


def main(critic, arguments):
    global driver

    if base.configuration()["database.driver"] == "postgresql":
        import psycopg2

        driver = psycopg2
    else:
        import sqlite3

        driver = sqlite3

    preferences = data.load_json("preferences.json")
    for item in sorted(preferences.items()):
        update_preference(critic, *item)

    critic.database.commit()
