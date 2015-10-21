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

import contextlib
import re
import time

import base
import dbaccess

from dbutils.session import Session

class InvalidCursorError(base.ImplementationError):
    pass

# Raised when "SELECT ... FOR UPDATE NOWAIT" fails to acquire row locks (without
# blocking.)
class FailedToLock(Exception):
    pass

# Singleton used as the value to Database.Cursor.execute()'s 'for_update'
# argument to request NOWAIT behavior (fail instead of blocking if rows are
# already locked.)
class NoWait:
    pass
NOWAIT = NoWait()

class _CursorIterator(object):
    def __init__(self, base):
        self.__base = base
        self.__invalid = False

    def next(self):
        if self.__invalid:
            raise InvalidCursorError("cursor re-used during iteration")
        return next(self.__base)

    def invalidate(self):
        self.__invalid = True

class _CursorBase(object):
    def __init__(self, db, cursor, profiling):
        self.db = db
        self.__cursor = cursor
        self.__profiling = profiling is not None
        self.__rows = None
        self.__iterators = []

    def __iter__(self):
        if self.__rows:
            base = iter(self.__rows)
            self.__rows = None
        else:
            base = iter(self.__cursor)
        iterator = _CursorIterator(base)
        self.__iterators.append(iterator)
        return iterator

    def __getitem__(self, index):
        if not self.__profiling:
            return self.__cursor[index]
        else:
            return self.__rows[index]

    @property
    def description(self):
        return self.__cursor.description

    def fetchone(self):
        if not self.__profiling:
            return self.__cursor.fetchone()
        elif self.__rows:
            row = self.__rows[0]
            self.__rows = self.__rows[1:]
            return row
        else:
            return None

    def fetchall(self):
        if not self.__profiling:
            return self.__cursor.fetchall()
        else:
            return self.__rows

    def execute(self, query, params=(), for_update=False):
        self.validate(query, for_update)
        if for_update:
            assert query.upper().startswith("SELECT ")
            query += " FOR UPDATE"
            if for_update is NOWAIT:
                query += " NOWAIT"
        try:
            if not self.__profiling:
                self.__cursor.execute(query, params)
            else:
                map(_CursorIterator.invalidate, self.__iterators)
                self.__iterators = []
                before = time.time()
                self.__cursor.execute(query, params)
                try:
                    self.__rows = self.__cursor.fetchall()
                except dbaccess.ProgrammingError:
                    self.__rows = None
                after = time.time()
                self.db.recordProfiling(query, after - before, rows=len(self.__rows) if self.__rows else 0)
        except dbaccess.OperationalError:
            if for_update is NOWAIT:
                raise FailedToLock()
            raise

    def executemany(self, query, params=()):
        self.validate(query, False)
        if self.__profiling is None:
            self.__cursor.executemany(query, params)
        else:
            before = time.time()
            params = list(params)
            self.__cursor.executemany(query, params)
            after = time.time()
            self.db.recordProfiling(query, after - before, repetitions=len(params))

    def mogrify(self, *args):
        return self.__cursor.mogrify(*args)

    def validate(self, query, for_update):
        raise InvalidCursorError("invalid use of _CursorBase")

class _UnsafeCursor(_CursorBase):
    def validate(self, query, for_update):
        try:
            command, _ = Database.analyzeQuery(query)
        except ValueError:
            command = None
        if command != "SELECT" or for_update:
            self.db.unsafe_queries = True

class _ReadOnlyCursor(_CursorBase):
    def validate(self, query, for_update):
        try:
            command, _ = Database.analyzeQuery(query)
        except ValueError as error:
            raise InvalidCursorError(error.message)
        if command != "SELECT" or for_update:
            raise InvalidCursorError(
                "invalid SQL query for read-only cursor: " +
                query.split(None, 1)[0])

class _UpdatingCursor(_ReadOnlyCursor):
    def __init__(self, tables, *args):
        super(_UpdatingCursor, self).__init__(*args)
        self.__disabled = False
        self.__tables = set(tables)

    @property
    def disabled(self):
        return self.__disabled

    def validate(self, query, for_update):
        if self.__disabled:
            raise InvalidCursorError("disabled updating cursor used")
        try:
            command, table = Database.analyzeQuery(query)
        except ValueError as error:
            raise InvalidCursorError(error.message)
        if command == "SELECT":
            return True
        elif command not in ("INSERT", "UPDATE", "DELETE"):
            raise InvalidCursorError(
                "invalid query for updating cursor: " + command)
        elif table not in self.__tables:
            raise InvalidCursorError(
                "invalid table for updating cursor: " + table)
        else:
            return True

    def disable(self):
        self.__disabled = True

RE_COMMAND = re.compile(
    # Optional WITH clause first:
    r"(?:WITH\s+\w+\s+\(\)\s+AS\s+\(\)(?:\s*,\s*\w+\s+\(\)\s+AS\s+\(\))*\s*)?"
    # Then query start.
    r"(INSERT(?=\s+INTO)|UPDATE|DELETE(?=\s+FROM)|SELECT)\s+(.*)",
    # Let . match line breaks, and ignore case.
    re.DOTALL | re.IGNORECASE)

class Database(Session):
    def __init__(self, allow_unsafe_cursors=True):
        super(Database, self).__init__()
        self.__connection = dbaccess.connect()
        self.__transaction_callbacks = []
        self.__allow_unsafe_cursors = allow_unsafe_cursors
        self.__updating_cursor = None
        self.unsafe_queries = False

    def __call_transaction_callbacks(self, *args):
        keep_transaction_callbacks = []
        for callback in self.__transaction_callbacks:
            if callback(*args):
                keep_transaction_callbacks.append(callback)
        self.__transaction_callbacks = keep_transaction_callbacks

    def cursor(self):
        if not self.__allow_unsafe_cursors:
            raise InvalidCursorError("unsafe cursors are not allowed")
        return _UnsafeCursor(self, self.__connection.cursor(), self.profiling)

    def readonly_cursor(self):
        return _ReadOnlyCursor(self, self.__connection.cursor(), self.profiling)

    @contextlib.contextmanager
    def updating_cursor(self, *tables):
        if self.__updating_cursor:
            raise InvalidCursorError("concurrent updating cursor requested")
        if self.unsafe_queries:
            raise InvalidCursorError("mixed unsafe and updating cursors")
        # Commit the current transaction.  It's guaranteed to have made no
        # modifications at this point, but might hold locks from earlier
        # queries that could increase the likelihook of deadlocks.
        self.commit()
        self.__updating_cursor = _UpdatingCursor(
            tables, self, self.__connection.cursor(), self.profiling)
        rolled_back = False
        try:
            yield self.__updating_cursor
            if self.unsafe_queries:
                raise InvalidCursorError("mixed unsafe and updating cursors")
        except: # Yes, we really mean to handle *all* exceptions here.
            rolled_back = True
            self.rollback()
            raise
        finally:
            do_commit = not (rolled_back or self.__updating_cursor.disabled)
            self.__updating_cursor.disable()
            self.__updating_cursor = None
            if do_commit:
                self.commit()

    def commit(self):
        if self.__updating_cursor:
            raise InvalidCursorError("manual commit when using updating cursor")
        before = time.time()
        self.__connection.commit()
        after = time.time()
        self.recordProfiling("<commit>", after - before, 0)
        self.__call_transaction_callbacks("commit")
        self.unsafe_queries = False

    def rollback(self):
        if self.__updating_cursor:
            self.__updating_cursor.disable()
        before = time.time()
        self.__connection.rollback()
        after = time.time()
        self.recordProfiling("<rollback>", after - before, 0)
        self.__call_transaction_callbacks("rollback")
        self.unsafe_queries = False

    def close(self):
        super(Database, self).close()
        if self.__connection:
            self.__connection.rollback()
            self.__connection.close()
            self.__connection = None

    def closed(self):
        return self.__connection is None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False

    def registerTransactionCallback(self, callback):
        self.__transaction_callbacks.append(callback)

    @staticmethod
    def analyzeQuery(query):
        """Extract the SQL command and affected table (if any) from a query

           Supported commands are SELECT, UPDATE, INSERT and DELETE.  Any other
           kind of query will raise a ValueError."""

        level = 0
        top_level = ""

        for part in re.split("([()])", query):
            if part == ")":
                level -= 1
            if level == 0:
                top_level += part
            if part == "(":
                level += 1

        match = RE_COMMAND.match(top_level)

        if not match:
            raise ValueError("unrecognized query: %s" % query.split()[0])

        command, rest = match.groups()

        if command in ("INSERT", "UPDATE", "DELETE"):
            rest = rest.split()
            if command in ("INSERT", "DELETE"):
                table = rest[1]
            else:
                table = rest[0]
        else:
            table = None

        return command, table

    @staticmethod
    def forUser():
        return Database()

    @staticmethod
    def forSystem():
        import dbutils

        db = Database()
        db.setUser(dbutils.User.makeSystem())
        return db

    @staticmethod
    def forTesting():
        try:
            import configuration
        except ImportError:
            # Not an installed system.
            pass
        else:
            assert configuration.debug.IS_TESTING

        return Database.forSystem()

# This function performs a NULL-safe conversion from a "truth" value or
# arbitrary type to True/False (or None.)  It's a utility for working around the
# fact that SQLite stores booleans as integers (zero or one.)
def boolean(value):
    return None if value is None else bool(value)
