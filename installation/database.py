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

import re

import installation
from installation import process

def prepare(arguments):
    return True

user_created = False
database_created = False
language_created = False

def execute():
    global user_created, database_created

    print "Creating database ..."

    process.check_output(["su", "-c", "psql -c 'CREATE USER \"%s\";'" % installation.system.username, "postgres"])
    user_created = True

    process.check_output(["su", "-c", "psql -c 'CREATE DATABASE \"critic\";'", "postgres"])
    database_created = True

    try:
        process.check_output(["su", "-c", "createlang plpgsql critic", "postgres"], stderr=process.STDOUT)
        language_created = True
    except process.CalledProcessError, error:
        if re.search(r"\blanguage\b.*\balready installed\b", error.output): pass
        else: raise

    process.check_output(["su", "-c", "psql -c 'GRANT ALL ON DATABASE \"critic\" TO \"%s\";'" % installation.system.username, "postgres"])
    process.check_output(["su", "-s", "/bin/sh", "-c", "psql -f dbschema.sql", installation.system.username])
    process.check_output(["su", "-s", "/bin/sh", "-c", "psql -f dbschema.comments.sql", installation.system.username])
    process.check_output(["su", "-s", "/bin/sh", "-c", "psql -f path.pgsql", installation.system.username])
    process.check_output(["su", "-s", "/bin/sh", "-c", "psql -f comments.pgsql", installation.system.username])
    process.check_output(["su", "-s", "/bin/sh", "-c", "psql -f roles.sql", installation.system.username])

    import psycopg2

    def adapt(value): return psycopg2.extensions.adapt(value).getquoted()

    process.check_input(["su", "-s", "/bin/sh", "-c", "psql -q -f -", installation.system.username],
                        stdin=("""INSERT INTO systemidentities (key, name, url_prefix, description)
                                      VALUES ('main', 'main', %s, 'Main');"""
                               % adapt("http://%s" % installation.system.hostname)))

    return True

def undo():
    if language_created:
        process.check_output(["su", "-c", "droplang plpgsql critic", "postgres"])
    if database_created:
        process.check_output(["su", "-c", "psql -c 'DROP DATABASE \"critic\";'", "postgres"])
    if user_created:
        process.check_output(["su", "-c", "psql -c 'DROP USER \"%s\";'" % installation.system.username, "postgres"])
