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

# New definitions in dbschema.user.sql.
dbschema.update("""

CREATE TYPE accesscontrolrule AS ENUM
  ( 'allow',
    'deny' );

CREATE TABLE accesscontrolprofiles
  ( id SERIAL PRIMARY KEY,
    title TEXT,

    -- Access token that this profile belongs to.
    access_token INTEGER REFERENCES accesstokens ON DELETE CASCADE,

    http accesscontrolrule NOT NULL DEFAULT 'allow',
    repositories accesscontrolrule NOT NULL DEFAULT 'allow',
    extensions accesscontrolrule NOT NULL DEFAULT 'allow',

    UNIQUE (access_token) );

CREATE TYPE httprequestmethod AS ENUM
  ( 'GET',
    'HEAD',
    'OPTIONS',
    'POST',
    'PUT',
    'DELETE' );

-- Exceptions for HTTP requests.
CREATE TABLE accesscontrol_http
  ( id SERIAL PRIMARY KEY,

    -- The profile this exception belongs to.
    profile INTEGER NOT NULL REFERENCES accesscontrolprofiles ON DELETE CASCADE,

    -- HTTP request method.  NULL means "all methods".
    request_method httprequestmethod,
    -- Python regular expression that must match the entire path.  NULL means
    -- "all paths".
    path_pattern TEXT );
CREATE INDEX accesscontrol_http_profile
          ON accesscontrol_http (profile);

CREATE TABLE useraccesscontrolprofiles
  ( -- The type of access that is controlled.
    access_type systemaccesstype NOT NULL DEFAULT 'user',

    -- The user (when access_type='user') or NULL.  If access_type='user' and
    -- this is NULL, then this is the default profile association.
    uid INTEGER REFERENCES users,

    -- Access control profile.
    profile INTEGER NOT NULL REFERENCES accesscontrolprofiles ON DELETE CASCADE,

    CONSTRAINT valid_user CHECK (access_type='user' OR uid IS NULL) );
CREATE INDEX useraccesscontrolprofiles_uid
          ON useraccesscontrolprofiles (uid);

CREATE TABLE labeledaccesscontrolprofiles
  ( -- Authentication labels from user authentication, typically indicating some
    -- type of group memberships. Labels should be sorted lexicographically and
    -- separated by pipe ('|') characters.
    labels VARCHAR(256) PRIMARY KEY,

    -- Access control profile.
    profile INTEGER NOT NULL REFERENCES accesscontrolprofiles ON DELETE CASCADE );

""")

# New definitions in dbschema.git.sql.
dbschema.update("""

CREATE TYPE repositoryaccesstype AS ENUM
  ( 'read',
    'modify' );

CREATE TABLE accesscontrol_repositories
  ( id SERIAL PRIMARY KEY,

    -- The profile this exception belongs to.
    profile INTEGER NOT NULL REFERENCES accesscontrolprofiles ON DELETE CASCADE,

    -- Type of access.  NULL means "any type".
    access_type repositoryaccesstype,
    -- Repository to access.  NULL means "any repository".
    repository INTEGER REFERENCES repositories ON DELETE CASCADE );
CREATE INDEX accesscontrol_repositories_profile
          ON accesscontrol_repositories (profile);

""")

# Check if dbschema.extensions.sql has been loaded at all.  It wasn't until
# extension support (the extend.py script) was fully added.  If the 'extensions'
# table doesn't exist, it obviously hasn't, and the tables below would be added
# along with everything else when dbschema.extensions.sql is loaded by
# extend.py.
if dbschema.table_exists("extensions"):
    # New definitions in dbschema.extensions.sql.
    dbschema.update("""

CREATE TYPE extensionaccesstype AS ENUM
  ( 'install',
    'execute' );

CREATE TABLE accesscontrol_extensions
  ( id SERIAL PRIMARY KEY,

    -- The profile this exception belongs to.
    profile INTEGER NOT NULL REFERENCES accesscontrolprofiles ON DELETE CASCADE,

    -- Type of extension access.  NULL means "any type".
    access_type extensionaccesstype,
    -- Extension key: <auther username>/<extension name> for user extensions and
    -- <extension name> for system extensions.  NULL means "any extension".
    extension_key TEXT );
CREATE INDEX accesscontrol_extensions_profile
          ON accesscontrol_extensions (profile);

    """)
