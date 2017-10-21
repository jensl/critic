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
import sys
import textwrap
import subprocess
import tempfile
import datetime
import hashlib
import contextlib
import json

import installation

class UpdateModifiedFile:
    def __init__(self, arguments, message, versions, options, generateVersion):
        """\
        Constructor.

        Arguments:

          arguments  Command-line arguments.
          message    Printed once.
          versions   Dictionary (label => path) of file versions involved.
          options    List of options to present to the user.
          prompt     Prompt printed when asking what to do.
        """

        self.__arguments = arguments
        self.__message = message
        self.__versions = versions
        self.__options = options
        self.__option_keys = [key for key, action in options]
        self.__option_map = dict((key, action) for key, action in options)
        self.__generateVersion = generateVersion
        self.__generated = []

    def printMessage(self):
        print(self.__message % self.__versions)

    def printOptions(self):
        alternatives = []

        for key, action in self.__options:
            if isinstance(action, str):
                alternatives.append("'%s' to %s" % (key, action))
            else:
                alternatives.append("'%s' to display the differences between the %s version and the %s version"
                                    % (key, action[0], action[1]))

        print(textwrap.fill("Input %s and %s." % (", ".join(alternatives[:-1]), alternatives[-1])))
        print()

    def displayDifferences(self, from_version, to_version):
        print()
        print("=" * 80)

        diff = subprocess.Popen(["diff", "-u", self.__versions[from_version], self.__versions[to_version]])
        diff.wait()

        print("=" * 80)
        print()

    def prompt(self):
        if self.__arguments.headless:
            # The first choice is typically "install updated version" or "remove
            # (obsolete) file" and is appropriate when --headless was used.
            return self.__options[0][0]

        try:
            for label, path in self.__versions.items():
                if not os.path.exists(path):
                    self.__generateVersion(label, path)
                    self.__generated.append(path)

            self.printMessage()

            while True:
                self.printOptions()

                def validResponse(value):
                    if value not in self.__option_keys:
                        return "please answer %s or %s" % (", ".join(self.__option_keys[:-1]), self.__option_keys[-1])

                response = installation.input.string("What do you want to do?", check=validResponse)
                action = self.__option_map[response]

                if isinstance(action, str):
                    print()
                    return response

                from_version, to_version = action

                self.displayDifferences(from_version, to_version)
        finally:
            for path in self.__generated:
                os.unlink(path)

def run_git(args, **kwargs):
    with installation.utils.as_effective_user_from_path(
            os.path.join(installation.root_dir, ".git")):
        return subprocess.check_output(args, **kwargs)

def update_from_template(arguments, data, template_path, target_path, message):
    git = data["installation.prereqs.git"]

    old_commit_sha1 = data["sha1"]
    new_commit_sha1 = run_git([git, "rev-parse", "HEAD"],
                              cwd=installation.root_dir).strip()

    old_template = read_file(git, old_commit_sha1, template_path)
    new_template = read_file(git, new_commit_sha1, template_path)

    old_source = old_template.decode("utf-8") % data
    new_source = new_template.decode("utf-8") % data

    with open(target_path) as target_file:
        current_source = target_file.read().decode("utf-8")

    if current_source == new_source:
        # The current version is what we would install now.  Nothing to do.
        return
    elif old_source == current_source:
        # The current version is what we installed (or would have installed with
        # the old template and current settings.)  Update the target file
        # without asking.
        write_target = True
    else:
        def generate_version(label, path):
            if label == "installed":
                source = old_source
            elif label == "updated":
                source = new_source
            else:
                return
            write_file(path, source.encode("utf-8"))

        versions = """\
  Installed version: %(installed)s
  Current version:   %(current)s
  Updated version:   %(updated)s"""

        update_query = UpdateModifiedFile(
            arguments,
            message=message % { "versions": versions },
            versions={ "installed": target_path + ".org",
                       "current": target_path,
                       "updated": target_path + ".new" },
            options=[ ("i", "install the updated version"),
                      ("k", "keep the current version"),
                      ("do", ("installed", "current")),
                      ("dn", ("current", "updated")) ],
            generateVersion=generate_version)

        write_target = update_query.prompt() == "i"

    if write_target:
        print("Updated file: %s" % target_path)

        if not arguments.dry_run:
            backup_path = os.path.join(os.path.dirname(target_path),
                                       ".%s.org" % os.path.basename(target_path))
            copy_file(target_path, backup_path)
            with open(target_path, "w") as target_file:
                target_file.write(new_source.encode("utf-8"))
            return backup_path

def write_file(path, source):
    # Use os.open() with O_EXCL to avoid trampling some existing file.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w") as target:
        target.write(source)

def copy_file(source_path, target_path):
    with open(source_path) as source:
        stat = os.fstat(source.fileno())
        # Use os.open() with O_EXCL to avoid trampling some existing file.
        fd = os.open(target_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w") as target:
            target.write(source.read())
            os.fchmod(target.fileno(), stat.st_mode)
            os.fchown(target.fileno(), stat.st_uid, stat.st_gid)

def hash_file(git, path):
    if os.path.islink(path):
        value = os.readlink(path)
    else:
        with open(path) as file:
            value = file.read()
    return hashlib.sha1("blob %d\0%s" % (len(value), value)).hexdigest()

def get_entry_sha1(git, commit_sha1, path, entry_type):
    lstree = run_git([git, "ls-tree", commit_sha1, path],
                     cwd=installation.root_dir).strip()

    if lstree:
        lstree_mode, lstree_type, lstree_sha1, lstree_path = lstree.split()

        assert lstree_type == entry_type
        assert lstree_path == path

        return lstree_sha1
    else:
        return None

def get_file_sha1(git, commit_sha1, path):
    return get_entry_sha1(git, commit_sha1, path, "blob")

def get_tree_sha1(git, commit_sha1, path):
    return get_entry_sha1(git, commit_sha1, path, "tree")

def read_file(git, commit_sha1, path):
    file_sha1 = get_file_sha1(git, commit_sha1, path)
    if file_sha1 is None:
        return None
    return run_git([git, "cat-file", "blob", file_sha1],
                   cwd=installation.root_dir)

def get_initial_commit_date(git, path):
    initial_commit_timestamp = run_git([git, "log", "--oneline",
            "--format=%ct", "--", path], cwd=installation.root_dir).splitlines()[-1]
    return datetime.datetime.fromtimestamp(int(initial_commit_timestamp))

def clean_root_pyc_files():
    print("Cleaning up .pyc files owned by root ...")
    for root, _, files in os.walk(installation.root_dir):
        for file in files:
            file = os.path.join(root, file)
            if file.endswith(".pyc") and os.stat(file).st_uid == 0:
                os.unlink(file)

@contextlib.contextmanager
def temporary_cwd():
    saved_cwd = os.getcwd()
    os.chdir(tempfile.gettempdir())
    try:
        yield
    finally:
        os.chdir(saved_cwd)

@contextlib.contextmanager
def as_critic_system_user():
    if installation.is_quick_start:
        yield
        return

    saved_cwd = os.getcwd()
    os.chdir(tempfile.gettempdir())
    os.setegid(installation.system.gid)
    os.seteuid(installation.system.uid)
    try:
        yield
    finally:
        os.seteuid(os.getresuid()[0])
        os.setegid(os.getresgid()[0])
        os.chdir(saved_cwd)

@contextlib.contextmanager
def as_effective_user_from_path(path):
    stat = os.stat(path)
    os.setegid(stat.st_gid)
    os.seteuid(stat.st_uid)
    try:
        yield
    finally:
        os.seteuid(os.getresuid()[0])
        os.setegid(os.getresgid()[0])

def deunicode(v):
    if isinstance(v, unicode): return v.encode("utf-8")
    elif isinstance(v, list): return list(map(deunicode, v))
    elif isinstance(v, dict): return dict([(deunicode(a), deunicode(b)) for a, b in v.items()])
    else: return v

def read_install_data(arguments, fail_softly=False):
    etc_path = os.path.join(arguments.etc_dir, arguments.identity)

    if not os.path.isdir(etc_path):
        if fail_softly:
            return None
        print("""
ERROR: %s: no such directory
HINT: Make sure the --etc-dir[=%s] and --identity[=%s] options
      correctly define where the installed system's configuration is stored.""" % (etc_path, arguments.etc_dir, arguments.identity))
        sys.exit(1)

    sys.path.insert(0, etc_path)

    try:
        import configuration
    except ImportError:
        if fail_softly:
            return None
        print("""
ERROR: Failed to import 'configuration' module.
HINT: Make sure the --etc-dir[=%s] and --identity[=%s] options
      correctly define where the installed system's configuration is stored.""" % (arguments.etc_dir, arguments.identity))
        sys.exit(1)

    install_data_path = os.path.join(configuration.paths.INSTALL_DIR, ".install.data")

    if not os.path.isfile(install_data_path):
        if fail_softly:
            return None
        print("""\
%s: no such file

This installation of Critic appears to be incomplete or corrupt.""" % install_data_path)
        sys.exit(1)

    try:
        with open(install_data_path, "r") as install_data_file:
            install_data = deunicode(json.load(install_data_file))
            if not isinstance(install_data, dict): raise ValueError
    except ValueError:
        if fail_softly:
            return None
        print("""\
%s: failed to parse JSON object to dictionary

This installation of Critic appears to be incomplete or corrupt.""" % install_data_path)
        sys.exit(1)

    return install_data

def write_install_data(arguments, install_data):
    install_data_path = os.path.join(installation.paths.install_dir, ".install.data")

    if not getattr(arguments, "dry_run", False):
        with open(install_data_path, "w") as install_data_file:
            json.dump(install_data, install_data_file)

        os.chown(install_data_path, installation.system.uid, installation.system.gid)
        os.chmod(install_data_path, 0o640)

def start_migration(connect=False):
    import sys
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--uid", type=int)
    parser.add_argument("--gid", type=int)

    arguments = parser.parse_args()

    os.setgid(arguments.gid)
    os.setuid(arguments.uid)

    if connect:
        import configuration
        import psycopg2

        return psycopg2.connect(**configuration.database.PARAMETERS)

class DatabaseSchema(object):
    """Database schema updating utility class

       This class is primarily intended for use in migration scripts."""

    def __init__(self, db=None):
        if db is not None:
            self.db = db
        else:
            import configuration
            import psycopg2

            self.db = psycopg2.connect(**configuration.database.PARAMETERS)

    def table_exists(self, table_name):
        import psycopg2

        try:
            self.db.cursor().execute("SELECT 1 FROM %s LIMIT 1" % table_name)
        except psycopg2.ProgrammingError:
            self.db.rollback()
            return False
        else:
            # Above statement would have thrown a psycopg2.ProgrammingError if the
            # table didn't exist, but it didn't, so the table must exist.
            return True

    def column_exists(self, table_name, column_name):
        import psycopg2

        try:
            self.db.cursor().execute("SELECT %s FROM %s LIMIT 1"
                                     % (column_name, table_name))
        except psycopg2.ProgrammingError:
            self.db.rollback()
            return False
        else:
            # Above statement would have thrown a psycopg2.ProgrammingError if the
            # table didn't exist, but it didn't, so the table must exist.
            return True

    def create_table(self, statement):
        import re

        (table_name,) = re.search("CREATE TABLE (\w+)", statement).groups()

        # Make sure the table doesn't already exist.
        if not self.table_exists(table_name):
            self.db.cursor().execute(statement)
            self.db.commit()

    def create_index(self, statement):
        import re

        (index_name,) = re.search("CREATE INDEX (\w+)", statement).groups()

        cursor = self.db.cursor()
        cursor.execute("DROP INDEX IF EXISTS %s" % index_name)
        cursor.execute(statement)
        self.db.commit()

    def create_column(self, table_name, column_name, column_definition):
        if not self.column_exists(table_name, column_name):
            self.db.cursor().execute(
                "ALTER TABLE %s ADD %s %s"
                % (table_name, column_name, column_definition))
            self.db.commit()

    def type_exists(self, type_name):
        import psycopg2

        try:
            self.db.cursor().execute("SELECT NULL::%s" % type_name)
        except psycopg2.ProgrammingError:
            self.db.rollback()
            return False
        else:
            # Above statement would have thrown a psycopg2.ProgrammingError if the
            # type didn't exist, but it didn't, so the table must exist.
            return True

    def create_type(self, statement):
        import re

        (type_name,) = re.search("CREATE TYPE (\w+)", statement).groups()

        # Make sure the type doesn't already exist.
        if not self.type_exists(type_name):
            self.db.cursor().execute(statement)
            self.db.commit()

    def update(self, statements):
        # Remove top-level comments; they interfere with out very simple
        # statement identification below.  Other comments are fine.
        lines = [line for line in statements.splitlines()
                 if not line.startswith("--")]
        statements = "\n".join(lines)

        for statement in statements.split(";"):
            statement = statement.strip()

            if not statement:
                continue

            if statement.startswith("CREATE TABLE"):
                self.create_table(statement)
            elif statement.startswith("CREATE INDEX"):
                self.create_index(statement)
            elif statement.startswith("CREATE TYPE"):
                self.create_type(statement)
            else:
                print("Unexpected SQL statement: %r" % statement, file=sys.stderr)
                sys.exit(1)

def read_lifecycle(git=None, sha1=None):
    filename = "installation/lifecycle.json"
    if sha1 is None:
        path = os.path.join(installation.root_dir, filename)
        with open(path, "r") as lifecycle_file:
            lifecycle_source = lifecycle_file.read()
    else:
        lifecycle_source = read_file(git, sha1, filename)
        if lifecycle_source is None:
            # For systems installed before the lifecycle.json file was
            # introduced, hard-code the file's initial content.
            return {
                "branch": "version/1",
                "stable": True
            }
    return deunicode(json.loads(lifecycle_source))
