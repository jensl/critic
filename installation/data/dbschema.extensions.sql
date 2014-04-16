-- -*- mode: sql -*-
--
-- Copyright 2012 Jens Lindström, Opera Software ASA
--
-- Licensed under the Apache License, Version 2.0 (the "License"); you may not
-- use this file except in compliance with the License.  You may obtain a copy of
-- the License at
--
--   http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
-- WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
-- License for the specific language governing permissions and limitations under
-- the License.

-- Disable notices about implicitly created indexes and sequences.
SET client_min_messages TO WARNING;

CREATE TABLE extensions
  ( id SERIAL PRIMARY KEY,
    author INTEGER REFERENCES users, -- NULL means system extension
    name VARCHAR(64) NOT NULL,

    UNIQUE (author, name) );

CREATE TABLE extensionversions
  ( id SERIAL PRIMARY KEY,
    extension INTEGER NOT NULL REFERENCES extensions,
    name VARCHAR(256) NOT NULL,
    sha1 CHAR(40) NOT NULL,

    UNIQUE (sha1) );

-- Installed extensions.
-- If uid=NULL, it is a "universal install" (affecting all users.)
-- If version=NULL, the "LIVE" version is installed.
CREATE TABLE extensioninstalls
  ( id SERIAL PRIMARY KEY,
    uid INTEGER REFERENCES users,
    extension INTEGER NOT NULL REFERENCES extensions,
    version INTEGER REFERENCES extensionversions,

    UNIQUE (uid, extension) );

CREATE TABLE extensionroles
  ( id SERIAL PRIMARY KEY,
    version INTEGER NOT NULL REFERENCES extensionversions,
    script VARCHAR(64) NOT NULL,
    function VARCHAR(64) NOT NULL );

CREATE TABLE extensionpageroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    path VARCHAR(64) NOT NULL );

CREATE VIEW extensionroles_page AS
  SELECT version, path, script, function
    FROM extensionroles
    JOIN extensionpageroles ON (role=id);

CREATE TABLE extensioninjectroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    path VARCHAR(64) NOT NULL );

CREATE VIEW extensionroles_inject AS
  SELECT version, path, script, function
    FROM extensionroles
    JOIN extensioninjectroles ON (role=id);

CREATE TABLE extensionprocesscommitsroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE );

CREATE TABLE extensionfilterhookroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    title VARCHAR(64) NOT NULL,
    role_description TEXT,
    data_description TEXT );

CREATE TABLE extensionhookfilters
  ( id SERIAL PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    extension INTEGER NOT NULL REFERENCES extensions ON DELETE CASCADE,
    repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    path TEXT NOT NULL,
    data TEXT );
CREATE INDEX extensionhookfilters_uid_extension
          ON extensionhookfilters (uid, extension);
CREATE INDEX extensionhookfilters_repository
          ON extensionhookfilters (repository);

CREATE TABLE extensionfilterhookevents
  ( id SERIAL PRIMARY KEY,
    filter INTEGER NOT NULL REFERENCES extensionhookfilters ON DELETE CASCADE,
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    data TEXT );
CREATE TABLE extensionfilterhookcommits
  ( event INTEGER NOT NULL REFERENCES extensionfilterhookevents ON DELETE CASCADE,
    commit INTEGER NOT NULL REFERENCES commits );
CREATE INDEX extensionfilterhookcommits_event
          ON extensionfilterhookcommits (event);
CREATE TABLE extensionfilterhookfiles
  ( event INTEGER NOT NULL REFERENCES extensionfilterhookevents ON DELETE CASCADE,
    file INTEGER NOT NULL REFERENCES files );
CREATE INDEX extensionfilterhookfiles_event
          ON extensionfilterhookfiles (event);

CREATE TABLE extensionstorage
  ( extension INTEGER NOT NULL REFERENCES extensions,
    uid INTEGER NOT NULL REFERENCES users,
    key VARCHAR(64) NOT NULL,
    text TEXT NOT NULL,

    PRIMARY KEY (extension, uid, key) );

CREATE TABLE extensionlog
  ( extension INTEGER NOT NULL REFERENCES extensions,
    uid INTEGER NOT NULL REFERENCES users,
    category VARCHAR(64) NOT NULL DEFAULT 'default',
    time TIMESTAMP NOT NULL DEFAULT now(),
    text TEXT NOT NULL );
CREATE INDEX extensionlog_extension_uid_category ON extensionlog(extension, uid, category);
