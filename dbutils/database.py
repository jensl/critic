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

import time
import dbaccess

from dbutils.session import Session

class InvalidCursorError(Exception):
    pass

class Database(Session):
    class Cursor(object):
        class Iterator(object):
            def __init__(self, base):
                self.__base = base
                self.__invalid = False

            def next(self):
                if self.__invalid:
                    raise InvalidCursorError("cursor re-used during iteration")
                return self.__base.next()

            def invalidate(self):
                self.__invalid = True

        def __init__(self, db, cursor, profiling):
            self.__db = db
            self.__cursor = cursor
            self.__profiling = self.__db.profiling is not None
            self.__rows = None
            self.__iterators = []

        def __iter__(self):
            if not self.__profiling:
                return iter(self.__cursor)
            else:
                iterator = Database.Cursor.Iterator(iter(self.__rows))
                self.__iterators.append(iterator)
                return iterator

        def __getitem__(self, index):
            if not self.__profiling:
                return self.__cursor[index]
            else:
                return self.__rows[index]

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

        def execute(self, query, params=None):
            if not self.__profiling:
                self.__cursor.execute(query, params)
            else:
                map(Database.Cursor.Iterator.invalidate, self.__iterators)
                self.__iterators = []
                before = time.time()
                self.__cursor.execute(query, params)
                try:
                    self.__rows = self.__cursor.fetchall()
                except dbaccess.ProgrammingError:
                    self.__rows = None
                after = time.time()
                self.__db.recordProfiling(query, after - before, rows=len(self.__rows) if self.__rows else 0)

        def executemany(self, query, params):
            if self.__profiling is None:
                self.__cursor.executemany(query, params)
            else:
                before = time.time()
                params = list(params)
                self.__cursor.executemany(query, params)
                after = time.time()
                self.__db.recordProfiling(query, after - before, repetitions=len(params))

    def __init__(self):
        super(Database, self).__init__()
        self.__connection = dbaccess.connect()

    def cursor(self):
        return Database.Cursor(self, self.__connection.cursor(), self.profiling)

    def commit(self):
        before = time.time()
        self.__connection.commit()
        after = time.time()
        self.recordProfiling("<commit>", after - before, 0)

    def rollback(self):
        before = time.time()
        self.__connection.rollback()
        after = time.time()
        self.recordProfiling("<rollback>", after - before, 0)

    def close(self):
        super(Database, self).close()
        self.__connection.close()
