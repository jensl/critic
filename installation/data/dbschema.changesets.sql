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

CREATE TYPE changesettype AS ENUM
  ( 'direct',     -- Plain diff between immediate parent and child (including
                  -- cases where the child commit has other parents.)
    'custom',     -- Plain diff between any other two commits.
    'merge',      -- Relevance filtered merge diff between immediate parent and
                  -- child where child has other parents.
    'conflicts'); -- Diff between two merge commits, one automatically generated
                  -- and one "real."  The automatically generated merge commit
                  -- is created without resolving any conflicts (the conflict
                  -- markers inserted by "git merge" are committed as-is.)
CREATE TABLE changesets
  ( id SERIAL PRIMARY KEY,
    parent INTEGER REFERENCES commits ON DELETE CASCADE,
    child INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE,
    type changesettype NOT NULL,

    UNIQUE (parent, child, type) );
CREATE INDEX changesets_child ON changesets (child);

CREATE TABLE customchangesets
  ( changeset INTEGER PRIMARY KEY REFERENCES changesets ON DELETE CASCADE,
    time TIMESTAMP );

CREATE TABLE mergereplays (

  original INTEGER,
  replay INTEGER NOT NULL,

  PRIMARY KEY (original),
  FOREIGN KEY (original) REFERENCES commits ON DELETE CASCADE,
  FOREIGN KEY (replay) REFERENCES commits ON DELETE CASCADE

);

CREATE TABLE fileversions
  ( changeset INTEGER NOT NULL REFERENCES changesets ON DELETE CASCADE,
    file INTEGER NOT NULL REFERENCES files,
    old_sha1 CHAR(40),
    new_sha1 CHAR(40),
    old_mode CHAR(6),
    new_mode CHAR(6),

    PRIMARY KEY (changeset, file) );
CREATE INDEX fileversions_old_sha1 ON fileversions (file, old_sha1);
CREATE INDEX fileversions_new_sha1 ON fileversions (file, new_sha1);

CREATE TABLE chunks
  ( id SERIAL PRIMARY KEY,
    changeset INTEGER NOT NULL REFERENCES changesets ON DELETE CASCADE,
    file INTEGER NOT NULL REFERENCES files,

    deleteOffset INTEGER NOT NULL,
    deleteCount INTEGER NOT NULL,
    insertOffset INTEGER NOT NULL,
    insertCount INTEGER NOT NULL,
    analysis TEXT,
    whitespace INTEGER NOT NULL );
CREATE INDEX chunks_changeset_file ON chunks (changeset, file);

CREATE TABLE codecontexts
  ( sha1 CHAR(40),
    context VARCHAR(256) NOT NULL,
    first_line INTEGER NOT NULL,
    last_line INTEGER NOT NULL );
CREATE INDEX codecontexts_sha1_first_last ON codecontexts (sha1, first_line, last_line);
