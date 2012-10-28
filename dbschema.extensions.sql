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

CREATE TABLE extensions
  ( id SERIAL PRIMARY KEY,
    author INTEGER NOT NULL REFERENCES users,
    name VARCHAR(64),

    UNIQUE (author, name) );

CREATE TABLE extensionversions
  ( id SERIAL PRIMARY KEY,
    sha1 CHAR(40),
    extension INTEGER NOT NULL REFERENCES extensions,

    UNIQUE (sha1) );

CREATE TABLE extensionroles
  ( id SERIAL PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users,
    version INTEGER NOT NULL REFERENCES extensionversions,
    script VARCHAR(64) NOT NULL,
    function VARCHAR(64) NOT NULL );

CREATE TABLE extensionpageroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    path VARCHAR(64) NOT NULL );

CREATE VIEW extensionroles_page AS
  SELECT uid, version, path, script, function
    FROM extensionroles
    JOIN extensionpageroles ON (role=id);

CREATE TABLE extensioninjectroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    path VARCHAR(64) NOT NULL );

CREATE VIEW extensionroles_inject AS
  SELECT uid, version, path, script, function
    FROM extensionroles
    JOIN extensioninjectroles ON (role=id);

CREATE TABLE extensionprocesscommitsroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    filter INTEGER REFERENCES filters );

CREATE VIEW extensionroles_processcommits AS
  SELECT uid, version, filter, script, function
    FROM extensionroles
    JOIN extensionprocesscommitsroles ON (role=id);

CREATE TABLE extensionprocesschangesroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    skip INTEGER NOT NULL REFERENCES batches );

CREATE VIEW extensionroles_processchanges AS
  SELECT id, skip, uid, version, script, function
    FROM extensionroles
    JOIN extensionprocesschangesroles ON (role=id);

CREATE TABLE extensionprocessedbatches
  ( role INTEGER NOT NULL REFERENCES extensionroles,
    batch INTEGER NOT NULL REFERENCES batches,

    PRIMARY KEY (batch, role) );

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
