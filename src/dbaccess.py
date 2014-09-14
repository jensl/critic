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

try:
    import configuration
except ImportError:
    IntegrityError = ProgrammingError = OperationalError = Exception
    TransactionRollbackError = Exception

    def connect():
        raise Exception("not supported")
else:
    if configuration.database.DRIVER == "postgresql":
        import psycopg2 as driver

        TransactionRollbackError = driver.extensions.TransactionRollbackError
    else:
        import sys
        import os

        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

        import installation.qs.sqlite as driver

        # SQLite doesn't appear to be throwing this type of error.
        class TransactionRollbackError(Exception):
            pass

    IntegrityError = driver.IntegrityError
    OperationalError = driver.OperationalError
    ProgrammingError = driver.ProgrammingError

    def connect():
        return driver.connect(**configuration.database.PARAMETERS)
