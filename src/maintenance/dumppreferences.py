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

print("PREFERENCES = [ ", end=' ', file=installpreferences_py)

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

print(" ]", file=installpreferences_py)
print(file=installpreferences_py)
print("def installPreferences(db, quiet):", file=installpreferences_py)
print("    cursor = db.cursor()", file=installpreferences_py)
print(file=installpreferences_py)
print("    for preference in PREFERENCES:", file=installpreferences_py)
print("        item = preference[\"item\"]", file=installpreferences_py)
print("        type = preference[\"type\"]", file=installpreferences_py)
print("        default_integer = preference.get(\"default_integer\")", file=installpreferences_py)
print("        default_string = preference.get(\"default_string\")", file=installpreferences_py)
print("        description = preference[\"description\"]", file=installpreferences_py)
print(file=installpreferences_py)
print("        cursor.execute(\"SELECT 1 FROM preferences WHERE item=%s\", (item,))", file=installpreferences_py)
print(file=installpreferences_py)
print("        if cursor.fetchone():", file=installpreferences_py)
print("            if not quiet: print \"Updating: %s\" % item", file=installpreferences_py)
print("            cursor.execute(\"UPDATE preferences SET type=%s, default_integer=%s, default_string=%s, description=%s WHERE item=%s\", (type, default_integer, default_string, description, item))", file=installpreferences_py)
print("        else:", file=installpreferences_py)
print("            if not quiet: print \"Adding:   %s\" % item", file=installpreferences_py)
print("            cursor.execute(\"INSERT INTO preferences (item, type, default_integer, default_string, description) VALUES (%s, %s, %s, %s, %s)\", (item, type, default_integer, default_string, description))", file=installpreferences_py)
print(file=installpreferences_py)
print("if __name__ == \"__main__\":", file=installpreferences_py)
print("    import sys", file=installpreferences_py)
print("    import os.path", file=installpreferences_py)
print(file=installpreferences_py)
print("    sys.path.insert(0, os.path.dirname(os.path.dirname(sys.argv[0])))", file=installpreferences_py)
print(file=installpreferences_py)
print("    import dbaccess", file=installpreferences_py)
print(file=installpreferences_py)
print("    db = dbaccess.connect()", file=installpreferences_py)
print(file=installpreferences_py)
print("    installPreferences(db, \"--quiet\" in sys.argv or \"-q\" in sys.argv)", file=installpreferences_py)
print(file=installpreferences_py)
print("    db.commit()", file=installpreferences_py)
