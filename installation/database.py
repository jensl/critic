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

import installation
from installation import process
import tempfile
import shutil
import os
import time
import errno

user_created = False
database_created = False
language_created = False

def psql_import(sql_file):
    temp_file = tempfile.mkstemp()[1]
    shutil.copy(sql_file, temp_file)
    # Make sure file is readable by postgres user
    os.chmod(temp_file, 0644)
    process.check_output(["su", "-s", "/bin/sh", "-c", "psql -f %s" % temp_file, installation.system.username])
    os.unlink(temp_file)

def add_arguments(mode, parser):
    if mode == "upgrade":
        parser.add_argument("--backup-database", dest="database_backup", action="store_const", const=True,
                            help="backup database to default location without asking")
        parser.add_argument("--no-backup-database", dest="database_backup", action="store_const", const=False,
                            help="do not backup database before upgrading")

def prepare(mode, arguments, data):
    if mode == "upgrade":
        default_path = os.path.join(data["installation.paths.data_dir"],
                                    "backups",
                                    time.strftime("%Y%m%d_%H%M.dump", time.localtime()))

        if arguments.database_backup is False:
            backup_database = False
        elif arguments.database_backup is True:
            backup_database = True
            backup_path = default_path
        else:
            if installation.migrate.will_modify_dbschema(data):
                print """
The database schema will be modified by the upgrade.  Creating a
backup of the database first is strongly recommended.
"""
                default_backup = True
            else:
                default_backup = False

            if installation.input.yes_or_no("Do you want to create a backup of the database?",
                                            default=default_backup):
                backup_database = True
                backup_path = installation.input.string("Where should the backup be stored?",
                                                        default=default_path)
            else:
                backup_database = False

        if backup_database:
            try: os.makedirs(os.path.dirname(backup_path), 0750)
            except OSError, error:
                if error.errno == errno.EEXIST: pass
                else: raise

            print
            print "Dumping database ..."

            with open(backup_path, "w") as output_file:
                process.check_call(["su", "-s", "/bin/sh", "-c", "pg_dump -Fc critic", data["installation.system.username"]], stdout=output_file)

            print "Compressing database dump ..."
            print

            process.check_call(["bzip2", backup_path])

    return True

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
        except process.CalledProcessError:
            # The 'createlang' command fails if the language is already enabled
            # in the database, and we want to ignore such failures.  It might
            # also fail for other reasons, that we really don't mean to ignore,
            # but in that case importing the *.pgsql files below would fail,
            # since they define PL/pgSQL functions.
            pass

        process.check_output(["su", "-c", "psql -c 'GRANT ALL ON DATABASE \"critic\" TO \"%s\";'" % installation.system.username, "postgres"])
        psql_import(os.path.join(root_dir, "dbschema.sql"))
        psql_import(os.path.join(root_dir, "dbschema.comments.sql"))
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
