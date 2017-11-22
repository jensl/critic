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

import warnings
from typing import Type

from critic import base

execute_schema_definition = None

IntegrityError: Type[Exception] = Exception
OperationalError: Type[Exception] = Exception
ProgrammingError: Type[Exception] = Exception
InvalidQueryError: Type[Exception] = Exception
TransactionRollbackError: Type[Exception] = Exception


def initialize():
    global IntegrityError, OperationalError, ProgrammingError, InvalidQueryError
    global TransactionRollbackError, execute_schema_definition

    configuration = base.configuration()

    if configuration["database.driver"] == "postgresql":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            import psycopg2 as driver

        InvalidQueryError = driver.ProgrammingError
        TransactionRollbackError = driver.extensions.TransactionRollbackError

        def execute_schema_definition(cursor, cmd):
            cursor.execute(cmd)

    else:
        from critic import sqlitecompat as driver

        InvalidQueryError = (driver.OperationalError, driver.ProgrammingError)
        TransactionRollbackError = base.Error

        execute_schema_definition = driver.execute_schema_definition

    IntegrityError = driver.IntegrityError
    OperationalError = driver.OperationalError
    ProgrammingError = driver.ProgrammingError


def connect():
    initialize()

    configuration = base.configuration()

    if configuration["database.driver"] == "postgresql":
        import psycopg2 as driver
    else:
        from critic import sqlitecompat as driver

    parameters = configuration["database.parameters"]

    return driver.connect(*parameters["args"], **parameters["kwargs"])
