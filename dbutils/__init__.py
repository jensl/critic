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

from dbaccess import IntegrityError

from dbutils.session import Session
from dbutils.database import Database
from dbutils.user import NoSuchUser, User
from dbutils.review import ReviewState, Review
from dbutils.branch import Branch
from dbutils.paths import is_directory, find_directory, describe_directory, \
                          is_file, find_file, find_files, describe_file, \
                          find_directory_file, explode_path, contained_files

def getURLPrefix(db):
    import configuration
    cursor = db.cursor()
    cursor.execute("SELECT url_prefix FROM systemidentities WHERE name=%s", (configuration.base.SYSTEM_IDENTITY,))
    return cursor.fetchone()[0]
