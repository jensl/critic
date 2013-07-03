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

import sys
import os.path

sys.path.insert(0, os.path.dirname(os.path.dirname(sys.argv[0])))

from dbaccess import connect

db = connect()
cursor = db.cursor()

cursor.execute("SELECT item, type, default_integer, default_string, description FROM preferences")

preferences = cursor.fetchall()

installpreferences_py = open(os.path.join(os.path.dirname(sys.argv[0]), "installpreferences.py"), "w")

print >>installpreferences_py, "PREFERENCES = [ ",

for index, (item, type, default_integer, default_string, description) in enumerate(preferences):
    if index != 0:
        installpreferences_py.write(""",
                """)

    installpreferences_py.write("""{ "item": %r,
                  "type": %r,""" % (item, type))

    if type == "string":
        installpreferences_py.write("""
                  "default_string": %r,""" % default_string)
    else:
        installpreferences_py.write("""
                  "default_integer": %r,""" % default_integer)

    installpreferences_py.write("""
                  "description": %r }""" % description)

print >>installpreferences_py, " ]"
print >>installpreferences_py
print >>installpreferences_py, "def installPreferences(db, quiet):"
print >>installpreferences_py, "    cursor = db.cursor()"
print >>installpreferences_py
print >>installpreferences_py, "    for preference in PREFERENCES:"
print >>installpreferences_py, "        item = preference[\"item\"]"
print >>installpreferences_py, "        type = preference[\"type\"]"
print >>installpreferences_py, "        default_integer = preference.get(\"default_integer\")"
print >>installpreferences_py, "        default_string = preference.get(\"default_string\")"
print >>installpreferences_py, "        description = preference[\"description\"]"
print >>installpreferences_py
print >>installpreferences_py, "        cursor.execute(\"SELECT 1 FROM preferences WHERE item=%s\", (item,))"
print >>installpreferences_py
print >>installpreferences_py, "        if cursor.fetchone():"
print >>installpreferences_py, "            if not quiet: print \"Updating: %s\" % item"
print >>installpreferences_py, "            cursor.execute(\"UPDATE preferences SET type=%s, default_integer=%s, default_string=%s, description=%s WHERE item=%s\", (type, default_integer, default_string, description, item))"
print >>installpreferences_py, "        else:"
print >>installpreferences_py, "            if not quiet: print \"Adding:   %s\" % item"
print >>installpreferences_py, "            cursor.execute(\"INSERT INTO preferences (item, type, default_integer, default_string, description) VALUES (%s, %s, %s, %s, %s)\", (item, type, default_integer, default_string, description))"
print >>installpreferences_py
print >>installpreferences_py, "if __name__ == \"__main__\":"
print >>installpreferences_py, "    import sys"
print >>installpreferences_py, "    import os.path"
print >>installpreferences_py
print >>installpreferences_py, "    sys.path.insert(0, os.path.dirname(os.path.dirname(sys.argv[0])))"
print >>installpreferences_py
print >>installpreferences_py, "    import dbaccess"
print >>installpreferences_py
print >>installpreferences_py, "    db = dbaccess.connect()"
print >>installpreferences_py
print >>installpreferences_py, "    installPreferences(db, \"--quiet\" in sys.argv or \"-q\" in sys.argv)"
print >>installpreferences_py
print >>installpreferences_py, "    db.commit()"
