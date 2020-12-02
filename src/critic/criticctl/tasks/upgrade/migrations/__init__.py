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

from __future__ import annotations

import argparse
import contextlib
import logging
import psycopg2
import psycopg2.extras
import re
from typing import Any, Collection, Literal, Optional, Protocol, Sequence, cast

from ....utils import as_user
from ...types import DatabaseConnection
from ...utils import fail

logger = logging.getLogger(__name__)

from critic import api
from critic import base


class MigrationModule(Protocol):
    index: int
    title: str
    scope: Collection[Literal["database"]]

    async def perform(
        self, critic: api.critic.Critic, arguments: argparse.Namespace
    ) -> None:
        ...


modules = cast(Sequence[MigrationModule], [])


def connect() -> DatabaseConnection:
    parameters = base.configuration()["database.parameters"]
    return psycopg2.connect(*parameters["args"], **parameters["kwargs"])


class DatabaseSchemaHelper(object):
    """Database schema updating utility class

    This class is primarily intended for use in migration scripts."""

    def __init__(self, critic: api.critic.Critic):
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

    def execute(self, sql: str, *args: Any) -> None:
        self.database.cursor().execute(sql, *args)

    def executemany(self, sql: str, *args: Any):
        psycopg2.extras.execute_batch(  # type: ignore
            self.database.cursor(), sql, *args
        )

    def commit(self):
        self.database.commit()

    def rollback(self):
        self.database.rollback()

    def table_exists(self, table_name: str) -> bool:
        try:
            self.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        except psycopg2.ProgrammingError:
            self.rollback()
            return False
        else:
            # Above statement would have thrown a ProgrammingError if the
            # table didn't exist, but it didn't, so the table must exist.
            return True

    def column_exists(self, table_name: str, column_name: str) -> bool:
        try:
            self.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
        except psycopg2.ProgrammingError:
            self.rollback()
            return False
        else:
            # Above statement would have thrown a ProgrammingError if the
            # table didn't exist, but it didn't, so the table must exist.
            return True

    def create_table(self, statement: str) -> None:
        match = re.search(r"CREATE TABLE (\w+)", statement)
        assert match

        (table_name,) = match.groups()

        # Make sure the table doesn't already exist.
        if not self.table_exists(table_name):
            logger.debug("CREATE TABLE %s", table_name)
            self.execute(statement)
            self.commit()

    def rename_table(self, old_name: str, new_name: str) -> None:
        if not self.table_exists(new_name):
            assert self.table_exists(old_name)
            logger.debug("ALTER TABLE %s RENAME TO %s", old_name, new_name)
            self.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
            self.commit()
        else:
            assert not self.table_exists(old_name)

    def drop_table(self, table_name: str) -> None:
        if self.table_exists(table_name):
            logger.debug("DROP TABLE %s", table_name)
            self.execute(f"DROP TABLE {table_name}")
            self.commit()

    def create_index(self, statement: str) -> None:
        match = re.search(r"CREATE(?: UNIQUE)? INDEX (\w+)", statement)
        assert match

        (index_name,) = match.groups()

        self.drop_index(index_name)
        self.execute(statement)
        self.commit()

    def drop_index(self, index_name: str) -> None:
        self.execute(f"DROP INDEX IF EXISTS {index_name}")
        self.commit()

    def add_column(
        self, table_name: str, column_name: str, column_definition: str
    ) -> None:
        if not self.column_exists(table_name, column_name):
            logger.debug("ALTER TABLE %s ADD %s", table_name, column_name)
            self.execute(
                f"ALTER TABLE {table_name}" f"  ADD {column_name} {column_definition}"
            )
            self.commit()

    def rename_column(self, table_name: str, old_name: str, new_name: str) -> None:
        if self.column_exists(table_name, old_name):
            logger.debug(
                "ALTER TABLE %s RENAME %s TO %s", table_name, old_name, new_name
            )
            self.execute(
                f"ALTER TABLE {table_name}" f"  RENAME {old_name} TO {new_name}"
            )
            self.commit()

    def alter_column(
        self,
        table_name: str,
        column_name: str,
        not_null: Optional[bool] = None,
        default: Optional[str] = None,
    ):
        alter_column = f"ALTER TABLE {table_name} ALTER {column_name}"
        if not_null is not None:
            set_or_drop = "SET" if not_null else "DROP"
            self.execute(f"{alter_column} {set_or_drop} NOT NULL")
        if default is not None:
            self.execute(f"{alter_column} SET DEFAULT {default}")

    def drop_column(self, table_name: str, column_name: str):
        if self.column_exists(table_name, column_name):
            logger.debug("ALTER TABLE %s DROP %s", table_name, column_name)
            self.execute(f"ALTER TABLE {table_name}" f"  DROP {column_name:str}")
            self.commit()

    def add_constraint(
        self, table_name: str, constraint_name: str, definition: str
    ) -> None:
        self.execute(
            f"ALTER TABLE {table_name}"
            f"  ADD CONSTRAINT {constraint_name}"
            f"  {definition}"
        )
        self.commit()

    def drop_constraint(self, constraint_name: str) -> None:
        table_name, _, _ = constraint_name.partition("_")
        self.execute(f"ALTER TABLE {table_name}" f"  DROP CONSTRAINT {constraint_name}")
        self.commit()

    def type_exists(self, type_name: str) -> bool:
        try:
            self.execute("SELECT NULL::%s" % type_name)
        except psycopg2.ProgrammingError:
            self.rollback()
            return False
        else:
            # Above statement would have thrown a ProgrammingError if the
            # type didn't exist, but it didn't, so the table must exist.
            return True

    def create_type(self, statement: str) -> None:
        match = re.search(r"CREATE TYPE (\w+)", statement)
        assert match

        (type_name,) = match.groups()

        # Make sure the type doesn't already exist.
        if not self.type_exists(type_name):
            self.execute(statement)
            self.commit()

    def add_enum_value(self, enum_name: str, value: str) -> None:
        with self.no_transaction():
            self.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")

    def drop_type(self, type_name: str) -> None:
        self.execute(f"DROP TYPE IF EXISTS {type_name}")
        self.commit()

    def create_view(self, statement: str) -> None:
        match = re.search(r"CREATE VIEW (\w+)", statement)
        assert match

        (view_name,) = match.groups()

        self.drop_view(view_name)
        self.execute(statement)
        self.commit()

    def drop_view(self, view_name: str) -> None:
        self.execute(f"DROP VIEW IF EXISTS {view_name}")
        self.commit()

    def update(self, sql: str) -> None:
        def strip_comment(line: str) -> str:
            line, _, _ = line.partition("--")
            assert (line.count("'") & 1) == 0
            return line

        # Remove top-level comments; they interfere with out very simple
        # statement identification below.  Other comments are fine.
        lines = [strip_comment(line) for line in sql.splitlines()]
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

    def __enter__(self) -> DatabaseSchemaHelper:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.database.close()
