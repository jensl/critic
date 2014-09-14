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

import os
import json
import textwrap
import subprocess

import installation

def add_preference(db, item, data, silent=False):
    relevance = data.get("relevance", {})

    cursor = db.cursor()
    cursor.execute("""INSERT INTO preferences (item, type, description,
                                               per_system, per_user,
                                               per_repository, per_filter)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                   (item, data["type"], data["description"],
                    relevance.get("system", True), relevance.get("user", True),
                    relevance.get("repository", False), relevance.get("filter", False)))

    if data["type"] == "string":
        cursor.execute("""INSERT INTO userpreferences (item, string)
                               VALUES (%s, %s)""",
                       (item, data["default"]))
    else:
        cursor.execute("""INSERT INTO userpreferences (item, integer)
                               VALUES (%s, %s)""",
                       (item, int(data["default"])))

    if not silent and not installation.quiet:
        print "Added preference: '%s'" % item

def update_preference(db, item, data, type_changed):
    relevance = data.get("relevance", {})

    cursor = db.cursor()
    cursor.execute("""UPDATE preferences
                         SET type=%s,
                             description=%s,
                             per_system=%s,
                             per_user=%s,
                             per_repository=%s,
                             per_filter=%s
                       WHERE item=%s""",
                   (data["type"], data["description"],
                    relevance.get("system", True), relevance.get("user", True),
                    relevance.get("repository", False), relevance.get("filter", False),
                    item))

    if data["type"] == "string":
        cursor.execute("""UPDATE userpreferences
                             SET integer=NULL,
                                 string=%s
                           WHERE item=%s
                             AND uid IS NULL
                             AND repository IS NULL""",
                       (data["default"], item))
    else:
        cursor.execute("""UPDATE userpreferences
                             SET integer=%s,
                                 string=NULL
                           WHERE item=%s
                             AND uid IS NULL
                             AND repository IS NULL""",
                       (int(data["default"]), item))

    if type_changed:
        # Delete all per-user or per-repository overrides; they will be of an
        # incorrect type.
        cursor.execute("""DELETE FROM userpreferences
                                WHERE item=%s
                                  AND (uid IS NOT NULL
                                    OR repository IS NOT NULL)""",
                       (item,))

def remove_preference(db, item):
    cursor = db.cursor()
    cursor.execute("DELETE FROM userpreferences WHERE item=%s", (item,))
    cursor.execute("DELETE FROM preferences WHERE item=%s", (item,))

def load_preferences(db):
    cursor = db.cursor()
    cursor.execute("""SELECT preferences.item, type, integer, string, description
                        FROM preferences
                        JOIN userpreferences USING (item)
                       WHERE uid IS NULL
                         AND repository IS NULL""")
    preferences = {}
    for item, item_type, default_integer, default_string, description in cursor:
        data = { "type": item_type,
                 "description": description }
        if item_type == "string":
            data["default"] = default_string
        elif item_type == "boolean":
            data["default"] = bool(default_integer)
        else:
            data["default"] = default_integer
        preferences[item] = data
    return preferences

def install(data):
    path = os.path.join(installation.root_dir, "src", "data",
                        "preferences.json")

    with open(path) as preferences_file:
        preferences = json.load(preferences_file)

    import dbutils

    with installation.utils.as_critic_system_user():
        with dbutils.Database() as db:
            for item in sorted(preferences.keys()):
                add_preference(db, item, preferences[item], silent=True)

            db.commit()

            if not installation.quiet:
                print "Added %d preferences." % len(preferences)

    return True

def upgrade(arguments, data):
    git = data["installation.prereqs.git"]
    path = "src/data/preferences.json"

    old_sha1 = data["sha1"]
    old_file_sha1 = installation.utils.get_file_sha1(git, old_sha1, path)

    new_sha1 = installation.utils.run_git([git, "rev-parse", "HEAD"],
                                          cwd=installation.root_dir).strip()
    new_file_sha1 = installation.utils.get_file_sha1(git, new_sha1, path)

    if old_file_sha1:
        old_source = installation.utils.run_git([git, "cat-file", "blob", old_file_sha1],
                                                cwd=installation.root_dir)
        old_preferences = json.loads(old_source)
    else:
        old_preferences = {}

    preferences_path = os.path.join(installation.root_dir, path)

    with open(preferences_path) as preferences_file:
        new_preferences = json.load(preferences_file)

    def update_preferences(old_preferences, new_preferences, db_preferences):
        for item in new_preferences.keys():
            if item not in db_preferences:
                add_preference(db, item, new_preferences[item])
            elif db_preferences[item] != new_preferences[item]:
                type_changed = False
                if db_preferences[item]["type"] != new_preferences[item]["type"]:
                    # If the type has changed, we really have to update it; code
                    # will depend on it having the right type.
                    update = True
                    type_changed = True
                elif item in old_preferences \
                        and db_preferences[item] == old_preferences[item]:
                    # The preference in the database is identical to what we
                    # originally installed; there should be no harm in updating
                    # it.
                    update = True
                elif db_preferences[item]["default"] == new_preferences[item]["default"]:
                    # The default value is the same => only description or flags
                    # has changed.  Probably safe to silently update.
                    update = True
                else:
                    if item in old_preferences \
                            and db_preferences[item]["default"] != old_preferences[item]["default"]:
                        # The default value appears to have been changed in the
                        # database.  Ask the user before overwriting it with an
                        # updated default value.
                        print
                        print textwrap.fill(
                            "The default value for the preference '%s' has been "
                            "changed in this version of Critic, but it appears to "
                            "also have been modified in the database."
                            % item)
                        default = False
                    else:
                        # The default value has changed, and we don't know if
                        # the value is what was originally installed, because we
                        # don't know what was originally installed.  Ask the
                        # user before overwriting the current value.
                        print
                        print textwrap.fill(
                            "The default value for the preference '%s' has been "
                            "changed in this version of Critic."
                            % item)
                        default = True

                    print
                    print "  Value in database: %r" % db_preferences[item]["default"]
                    print "  New/updated value: %r" % new_preferences[item]["default"]
                    print

                    update = installation.input.yes_or_no(
                        "Would you like to update the database with the new value?",
                        default=default)

                if update:
                    update_preference(db, item, new_preferences[item], type_changed)

        # Only check for preferences to remove if the preference data has
        # changed.  Otherwise, every upgrade would ask to remove any extra
        # preferences in the database.
        if old_file_sha1 != new_file_sha1:
            for item in db_preferences.keys():
                if item not in new_preferences:
                    if item in old_preferences \
                            and db_preferences[item] == old_preferences[item]:
                        # The preference in the database is identical to what we
                        # originally installed; there should be no harm in
                        # updating it.
                        remove = True
                    else:
                        print
                        print textwrap.fill(
                            "The preference '%s' exists in the database but "
                            "not in the installation data, meaning it would "
                            "not have been added to the database if this "
                            "version of Critic was installed from scratch."
                            % item)
                        print

                        remove = installation.input.yes_or_no(
                            "Would you like to remove it from the database?",
                            default=True)

                    if remove:
                        remove_preference(db, item)

        db.commit()

    import dbutils

    with installation.utils.as_critic_system_user():
        with dbutils.Database() as db:
            update_preferences(old_preferences,
                               new_preferences,
                               load_preferences(db))

    return True
