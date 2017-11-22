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

import contextlib
import logging
import psycopg2

logger = logging.getLogger(__name__)

from . import convert_from_legacy
from . import convert_changesets
from . import convert_useremails
from . import fix_branchupdates_id

from critic import base
from critic import dbutils

modules = [
    convert_from_legacy,
    convert_changesets,
    convert_useremails,
    fix_branchupdates_id,
]


def connect():
    parameters = base.configuration()["database.parameters"]
    return psycopg2.connect(*parameters["args"], **parameters["kwargs"])


class DatabaseSchemaHelper(object):
    """Database schema updating utility class

       This class is primarily intended for use in migration scripts."""

    def __init__(self, critic):
        from ... import as_user

        self.critic = critic
        with as_user(name=base.configuration()["system.username"]):
            self.database = connect()

    @contextlib.contextmanager
    def no_transaction(self):
        self.database.autocommit = True
        try:
            yield
        finally:
            self.database.autocommit = False
            self.commit()

    def execute(self, command, *args):
        self.database.cursor().execute(command, *args)

    def executemany(self, command, *args):
        psycopg2.extras.execute_batch(self.database.cursor(), command, *args)

    def commit(self):
        self.database.commit()

    def rollback(self):
        self.database.rollback()

    def table_exists(self, table_name):
        try:
            self.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        except psycopg2.ProgrammingError:
            self.rollback()
            return False
        else:
            # Above statement would have thrown a ProgrammingError if the
            # table didn't exist, but it didn't, so the table must exist.
            return True

    def column_exists(self, table_name, column_name):
        try:
            self.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
        except psycopg2.ProgrammingError:
            self.rollback()
            return False
        else:
            # Above statement would have thrown a ProgrammingError if the
            # table didn't exist, but it didn't, so the table must exist.
            return True

    def create_table(self, statement):
        import re

        (table_name,) = re.search("CREATE TABLE (\w+)", statement).groups()

        # Make sure the table doesn't already exist.
        if not self.table_exists(table_name):
            logger.debug("CREATE TABLE %s", table_name)
            self.execute(statement)
            self.commit()

    def rename_table(self, old_name, new_name):
        if not self.table_exists(new_name):
            assert self.table_exists(old_name)
            logger.debug("ALTER TABLE %s RENAME TO %s", old_name, new_name)
            self.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
            self.commit()
        else:
            assert not self.table_exists(old_name)

    def drop_table(self, table_name):
        if self.table_exists(table_name):
            logger.debug("DROP TABLE %s", table_name)
            self.execute(f"DROP TABLE {table_name}")
            self.commit()

    def create_index(self, statement):
        import re

        match = re.search("CREATE(?: UNIQUE)? INDEX (\w+)", statement)
        (index_name,) = match.groups()

        self.drop_index(index_name)
        self.execute(statement)
        self.commit()

    def drop_index(self, index_name):
        self.execute(f"DROP INDEX IF EXISTS {index_name}")
        self.commit()

    def add_column(self, table_name, column_name, column_definition):
        if not self.column_exists(table_name, column_name):
            logger.debug("ALTER TABLE %s ADD %s", table_name, column_name)
            self.execute(
                f"ALTER TABLE {table_name}" f"  ADD {column_name} {column_definition}"
            )
            self.commit()

    def rename_column(self, table_name, old_name, new_name):
        if self.column_exists(table_name, old_name):
            logger.debug(
                "ALTER TABLE %s RENAME %s TO %s", table_name, old_name, new_name
            )
            self.execute(
                f"ALTER TABLE {table_name}" f"  RENAME {old_name} TO {new_name}"
            )
            self.commit()

    def alter_column(self, table_name, column_name, not_null=None, default=None):
        alter_column = f"ALTER TABLE {table_name} ALTER {column_name}"
        if not_null is not None:
            set_or_drop = "SET" if not_null else "DROP"
            self.execute(f"{alter_column} {set_or_drop} NOT NULL")
        if default is not None:
            self.execute(f"{alter_column} SET DEFAULT {default}")

    def drop_column(self, table_name, column_name):
        if self.column_exists(table_name, column_name):
            logger.debug("ALTER TABLE %s DROP %s", table_name, column_name)
            self.execute(f"ALTER TABLE {table_name}" f"  DROP {column_name}")
            self.commit()

    def add_constraint(self, table_name, constraint_name, definition):
        self.execute(
            f"ALTER TABLE {table_name}"
            f"  ADD CONSTRAINT {constraint_name}"
            f"  {definition}"
        )
        self.commit()

    def drop_constraint(self, constraint_name):
        table_name, _, _ = constraint_name.partition("_")
        self.execute(f"ALTER TABLE {table_name}" f"  DROP CONSTRAINT {constraint_name}")
        self.commit()

    def type_exists(self, type_name):
        try:
            self.execute("SELECT NULL::%s" % type_name)
        except psycopg2.ProgrammingError:
            self.rollback()
            return False
        else:
            # Above statement would have thrown a ProgrammingError if the
            # type didn't exist, but it didn't, so the table must exist.
            return True

    def create_type(self, statement):
        import re

        (type_name,) = re.search("CREATE TYPE (\w+)", statement).groups()

        # Make sure the type doesn't already exist.
        if not self.type_exists(type_name):
            self.execute(statement)
            self.commit()

    def add_enum_value(self, enum_name, value):
        with self.no_transaction():
            self.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")

    def drop_type(self, type_name):
        self.execute(f"DROP TYPE IF EXISTS {type_name}")
        self.commit()

    def create_view(self, statement):
        import re

        match = re.search("CREATE VIEW (\w+)", statement)
        (view_name,) = match.groups()

        self.drop_view(view_name)
        self.execute(statement)
        self.commit()

    def drop_view(self, view_name):
        self.execute(f"DROP VIEW IF EXISTS {view_name}")
        self.commit()

    def update(self, statements):
        from ... import fail

        def strip_comment(line):
            line, _, comment = line.partition("--")
            assert (line.count("'") & 1) == 0
            return line

        # Remove top-level comments; they interfere with out very simple
        # statement identification below.  Other comments are fine.
        lines = [strip_comment(line) for line in statements.splitlines()]
        statements = " ".join(lines).split(";")

        for statement in statements:
            statement = statement.strip()

            if not statement:
                continue

            if statement.startswith("CREATE TABLE"):
                self.create_table(statement)
            elif statement.startswith("CREATE INDEX") or statement.startswith(
                "CREATE UNIQUE INDEX"
            ):
                self.create_index(statement)
            elif statement.startswith("CREATE TYPE"):
                self.create_type(statement)
            elif statement.startswith("CREATE VIEW"):
                self.create_view(statement)
            else:
                fail("Unexpected SQL statement: %r" % statement)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.database.close()
