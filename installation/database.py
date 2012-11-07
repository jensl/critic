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
import tempfile
import shutil
import stat
import os

user_created = False
database_created = False
language_created = False

def psql_import(sql_file):
    temp_file = tempfile.mkstemp()[1]
    shutil.copy(sql_file, temp_file)
    # Make sure file is readable by postgres user
    os.chmod(temp_file, stat.S_IROTH)
    process.check_output(["su", "-s", "/bin/sh", "-c", "psql -f %s" % temp_file, installation.system.username])
    os.unlink(temp_file)

def install(data):
    global user_created, database_created, language_created

    print "Creating database ..."

    # Several subsequent commands will run as Critic system user or "postgres" user,
    # and these users typically don't have read access to the installation 'root_dir'
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    original_dir = os.getcwd()
    try:
        # Set cwd to something that Critic system / "postgres" users has access to.
        os.chdir(tempfile.gettempdir())

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
        psql_import(os.path.join(root_dir, "dbschema.sql"))
        psql_import(os.path.join(root_dir, "dbschema.comments.sql"))
        psql_import(os.path.join(root_dir, "path.pgsql"))
        psql_import(os.path.join(root_dir, "comments.pgsql"))
        psql_import(os.path.join(root_dir, "roles.sql"))

        import psycopg2

        def adapt(value): return psycopg2.extensions.adapt(value).getquoted()

        process.check_input(["su", "-s", "/bin/sh", "-c", "psql -q -f -", installation.system.username],
                            stdin=("""INSERT INTO systemidentities (key, name, url_prefix, description)
                                          VALUES ('main', 'main', %s, 'Main');"""
                                   % adapt("http://%s" % installation.system.hostname)))

    finally:
        os.chdir(original_dir)

    return True

def undo():
    if language_created:
        process.check_output(["su", "-c", "droplang plpgsql critic", "postgres"])
    if database_created:
        process.check_output(["su", "-c", "psql -c 'DROP DATABASE \"critic\";'", "postgres"])
    if user_created:
        process.check_output(["su", "-c", "psql -c 'DROP USER \"%s\";'" % installation.system.username, "postgres"])
