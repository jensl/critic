-- -*- mode: sql -*-
--
-- Copyright 2015 the Critic contributors, Opera Software ASA
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

CREATE TABLE trackedbranches
  ( id SERIAL PRIMARY KEY,
    repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    local_name VARCHAR(256) NOT NULL,
    remote VARCHAR(256) NOT NULL,
    remote_name VARCHAR(256) NOT NULL,
    forced BOOLEAN NOT NULL,
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    updating BOOLEAN NOT NULL DEFAULT FALSE,
    delay INTERVAL NOT NULL,
    previous TIMESTAMP,
    next TIMESTAMP,

    UNIQUE (repository, local_name) );

CREATE TABLE trackedbranchusers
  ( branch INTEGER NOT NULL REFERENCES trackedbranches ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users,

    PRIMARY KEY (branch, uid) );

CREATE TABLE trackedbranchlog
  ( branch INTEGER NOT NULL REFERENCES trackedbranches ON DELETE CASCADE,
    time TIMESTAMP NOT NULL DEFAULT NOW(),
    from_sha1 CHAR(40),
    to_sha1 CHAR(40) NOT NULL,
    hook_output TEXT NOT NULL,
    successful BOOLEAN NOT NULL );
CREATE INDEX trackedbranchlog_branch ON trackedbranchlog (branch);
