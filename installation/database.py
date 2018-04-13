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

import tempfile
import shutil
import os
import time
import errno
import subprocess
from pipes import quote

import installation

server_hostname = None
server_port = None
username = None
password = None
name = None

user_created = False
database_created = False
language_created = False


def psql_run(*args, **kwargs):
    as_user = kwargs.get('as_user') or installation.system.username
    params = list(args)
    if server_hostname is not None:
        params.append("postgresql://%s:%s@%s:%d/%s" % (username, password, server_hostname, server_port, name))
    to_run = ['su', '-s', '/bin/sh', '-c', 'psql -v ON_ERROR_STOP=1 %s' % ' '.join(
            quote(parm) for parm in params)]
    if as_user:
        to_run.append(as_user)
    return to_run

def psql_import(sql_file, as_user=None):
    temp_file = tempfile.mkstemp()[1]
    shutil.copy(os.path.join(installation.root_dir, sql_file), temp_file)
    # Make sure file is readable by postgres user
    os.chmod(temp_file, 0644)
    subprocess.check_output(psql_run('-f', temp_file, as_user=as_user))
    os.unlink(temp_file)

def add_arguments(mode, parser):
    if mode == "install":
        parser.add_argument(
            "--db-server-hostname",
            help="Database server hostname [default: use local database]")
        parser.add_argument(
            "--db-server-port", type=int, default=5432,
            help="Database server port")

        parser.add_argument(
            "--db-username", default="critic",
            help="Database username")
        parser.add_argument(
            "--db-password", default="critic",
            help="Database password")
        parser.add_argument(
            "--db-name", default="critic",
            help="Database name")

    if mode == "upgrade":
        parser.add_argument("--backup-database", dest="database_backup", action="store_const", const=True,
                            help="backup database to default location without asking")
        parser.add_argument("--no-backup-database", dest="database_backup", action="store_const", const=False,
                            help="do not backup database before upgrading")

def prepare(mode, arguments, data):
    global server_hostname, server_port, username, password, name

    if arguments.db_server_hostname:
        server_hostname = arguments.db_server_hostname
        server_port = arguments.db_server_port
        username = arguments.db_username
        password = arguments.db_password
        name = arguments.db_name

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
            except OSError as error:
                if error.errno == errno.EEXIST: pass
                else: raise

            print
            print "Dumping database ..."

            with open(backup_path, "w") as output_file:
                subprocess.check_call(
                    ["su", "-s", "/bin/sh", "-c", "pg_dump -Fc critic",
                     data["installation.system.username"]],
                    stdout=output_file)

    data["installation.database.driver"] = "postgresql"

    if server_hostname is None:
        data["installation.database.parameters"] = {
            "database": "critic",
            "user": data["installation.system.username"]
        }
    else:
        data["installation.database.parameters"] = {
            "host": server_hostname,
            "port": str(server_port),
            "user": username,
            "password": password,
            "dbname": name,
        }

    return True

SCHEMA_FILES = [
    # No dependencies.
    "installation/data/dbschema.base.sql",
    "installation/data/dbschema.users.sql",

    # Depends on: base[files].
    "installation/data/dbschema.git.sql",

    # Depends on: users.
    "installation/data/dbschema.news.sql",

    # Depends on: git, users.
    "installation/data/dbschema.trackedbranches.sql",

    # Depends on: base[files], git.
    "installation/data/dbschema.changesets.sql",

    # Depends on: git, users.
    "installation/data/dbschema.filters.sql",

    # Depends on: git, users, filters.
    "installation/data/dbschema.preferences.sql",

    # Depends on: base[files], git, users, changesets.
    "installation/data/dbschema.reviews.sql",

    # Depends on: base[files], git, users, reviews.
    "installation/data/dbschema.comments.sql",

    # Depends on: base[files], git, users, reviews.
    "installation/data/dbschema.extensions.sql",
]

PGSQL_FILES = ["installation/data/comments.pgsql"]

def install_local():
    global user_created, database_created, language_created

    postgresql_version_output = subprocess.check_output(
        [installation.prereqs.psql.path, "--version"])

    postgresql_version = postgresql_version_output.splitlines()[0].split()[-1]
    postgresql_version_components = postgresql_version.split(".")

    postgresql_major = postgresql_version_components[0]
    postgresql_minor = postgresql_version_components[1]

    if postgresql_major < 9 or (postgresql_major == 9 and postgresql_minor < 1):
        print
        print """\
Unsupported PostgreSQL version: %s

ERROR: Critic requires PostgreSQL 9.1.x or later!
""" % postgresql_version
        return False

    print "Creating database ..."

    # Several subsequent commands will run as Critic system user or "postgres"
    # user, and these users typically don't have read access to the installation
    # 'root_dir', so set cwd to something that Critic system / "postgres" users
    # has access to.
    with installation.utils.temporary_cwd():
        uname = installation.system.username
        subprocess.check_output(["su", "-c", 'createuser "%s"' % uname,
                                 "postgres"])
        user_created = True
        subprocess.check_output(
            ["su", "-c", 'createdb -T template0 -E utf8 -O "{0}" "{0}"'.format(uname),
             "postgres"])
        database_created = True

        try:
            subprocess.check_output(["su", "-c", "createlang plpgsql critic", "postgres"],
                                    stderr=subprocess.STDOUT)
            language_created = True
        except subprocess.CalledProcessError:
            # The 'createlang' command fails if the language is already enabled
            # in the database, and we want to ignore such failures.  It might
            # also fail for other reasons, that we really don't mean to ignore,
            # but in that case importing the *.pgsql files below would fail,
            # since they define PL/pgSQL functions.
            pass

        subprocess.check_output(["su", "-c", "psql -v ON_ERROR_STOP=1 -c 'GRANT ALL ON DATABASE \"critic\" TO \"%s\";'" % installation.system.username, "postgres"])

def install(data):
    if not server_hostname:
        install_local()

    for schema_file in SCHEMA_FILES:
        psql_import(schema_file)
    for pgsql_file in PGSQL_FILES:
        psql_import(pgsql_file)

    import psycopg2

    def adapt(value): return psycopg2.extensions.adapt(value).getquoted()

    if installation.config.access_scheme in ("http", "https"):
        anonymous_scheme = authenticated_scheme = installation.config.access_scheme
    else:
        anonymous_scheme = "http"
        authenticated_scheme = "https"

    add_systemidentity_query = (
        """INSERT INTO systemidentities (key, name, anonymous_scheme,
                                         authenticated_scheme, hostname,
                                         description, installed_sha1)
                VALUES ('main', 'main', %s, %s, %s, 'Main', %s);"""
        % (adapt(anonymous_scheme), adapt(authenticated_scheme),
           adapt(installation.system.hostname), adapt(data["sha1"])))

    installation.process.check_input(
        psql_run('-q', as_user=installation.system.username),
        stdin=add_systemidentity_query)

    return True

def upgrade(arguments, data):
    git = data["installation.prereqs.git"]

    old_sha1 = data["sha1"]
    new_sha1 = installation.utils.run_git([git, "rev-parse", "HEAD"],
                                          cwd=installation.root_dir).strip()

    for pgsql_file in PGSQL_FILES:
        old_file_sha1 = installation.utils.get_file_sha1(
            git, old_sha1, pgsql_file)
        new_file_sha1 = installation.utils.get_file_sha1(
            git, new_sha1, pgsql_file)

        if old_file_sha1 == new_file_sha1:
            continue

        with installation.utils.temporary_cwd():
            # We assume that these files use CREATE OR REPLACE syntax, so that
            # we can simply re-import them when they change, and they'll update.
            # If they need more than that to update (for instance if a function
            # is removed) we'll need to use a migration script for that.
            print "Reloading: %s" % pgsql_file

            if not arguments.dry_run:
                psql_import(pgsql_file)

    return True

def undo():
    if language_created:
        subprocess.check_output(["su", "-c", "droplang plpgsql critic", "postgres"])
    if database_created:
        subprocess.check_output(["su", "-c", "dropdb critic", "postgres"])
    if user_created:
        subprocess.check_output(["su", "-c", "dropuser critic", "postgres"])
