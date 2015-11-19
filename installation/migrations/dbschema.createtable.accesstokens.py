# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

# Handles command line arguments and sets uid/gid.
installation.utils.start_migration()

dbschema = installation.utils.DatabaseSchema()

# New definitions in dbschema.user.git.
dbschema.update("""

CREATE TYPE systemaccesstype AS ENUM
  ( -- The system is accessed as a named user.
    'user',
    -- The system is accessed by a system service or similar.
    'system',
    -- The system is accessed anonymously.
    'anonymous' );

CREATE TABLE accesstokens
  ( id SERIAL PRIMARY KEY,

    -- The type of access granted by this access token.
    access_type systemaccesstype NOT NULL DEFAULT 'user',
    -- The user (when access_type='user') or NULL.
    uid INTEGER REFERENCES users ON DELETE CASCADE,

    -- First part of access token ("username").
    part1 VARCHAR(32) NOT NULL,
    -- Second part of access token ("password").
    part2 VARCHAR(32) NOT NULL,

    -- Access token title.
    title VARCHAR(256),

    UNIQUE (part1, part2),

    CONSTRAINT valid_user CHECK ((access_type='user' AND uid IS NOT NULL) OR
                                 (access_type!='user' AND uid IS NULL)) );

""")
