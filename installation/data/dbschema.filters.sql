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

-- Disable notices about implicitly created indexes and sequences.
SET client_min_messages TO WARNING;

CREATE TYPE filtertype AS ENUM
  ( 'reviewer',
    'watcher',
    'ignored' );
CREATE TABLE filters
  ( id SERIAL PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users,
    repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    path TEXT NOT NULL,
    type filtertype NOT NULL,
    delegate TEXT );

-- Index used to enforce uniqueness.
CREATE UNIQUE INDEX filters_uid_repository_path_md5 ON filters (uid, repository, MD5(path));
