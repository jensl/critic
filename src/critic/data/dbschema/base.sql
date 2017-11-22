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

CREATE TABLE systemidentities (
  key VARCHAR(32),
  name VARCHAR(64),
  anonymous_scheme VARCHAR(5) NOT NULL,
  authenticated_scheme VARCHAR(5) NOT NULL,
  hostname VARCHAR(265) NOT NULL,
  description VARCHAR(256) NOT NULL,
  installed_sha1 CHAR(40) NOT NULL,
  installed_at TIMESTAMP DEFAULT NOW() NOT NULL,

  PRIMARY KEY (key),
  UNIQUE (name)
);

CREATE TABLE systemsettings (
  id SERIAL,

  key VARCHAR(256) NOT NULL,
  value JSON NOT NULL,
  privileged BOOLEAN NOT NULL,
  description TEXT NOT NULL,

  PRIMARY KEY (id),
  UNIQUE (key)
);

CREATE TABLE systemevents (
  id SERIAL,

  category VARCHAR(32) NOT NULL,
  key VARCHAR(256) NOT NULL,
  title VARCHAR(256) NOT NULL,
  data TEXT NOT NULL DEFAULT 'null',
  handled BOOLEAN NOT NULL DEFAULT FALSE,

  PRIMARY KEY (id)
);
CREATE INDEX systemevents_category_key
          ON systemevents (category, key);

CREATE TABLE files (
  id SERIAL PRIMARY KEY,
  path TEXT NOT NULL
);

-- Index used to enforce uniqueness, and for quick lookup of single
-- paths (using "SELECT id FROM files WHERE MD5(path)=MD5(...)".
CREATE UNIQUE INDEX files_path_md5 ON files (MD5(path));

-- Index used for path searches, for instance when searching for
-- reviews that touch files in a certain directory.
CREATE INDEX files_path_gin ON files USING gin (STRING_TO_ARRAY(path, '/'));

CREATE TABLE knownremotes (
  url VARCHAR(256) PRIMARY KEY,
  -- True if this remote has a post-update hook (or similar) that contacts the
  -- branchtrackerhook service and triggers immediate updates of tracked
  -- branches.
  pushing BOOLEAN NOT NULL
);

CREATE TABLE timezones (
  name VARCHAR(256) PRIMARY KEY,
  abbrev VARCHAR(16) NOT NULL,
  utc_offset INTERVAL NOT NULL
);

INSERT INTO timezones (name, abbrev, utc_offset)
     VALUES ('Universal/UTC', 'UTC', INTERVAL '0');

CREATE TABLE pubsubreservations (

  reservation_id SERIAL,

  channel VARCHAR NOT NULL,

  PRIMARY KEY (reservation_id)

);

CREATE INDEX pubsubreservations_channel
          ON pubsubreservations (channel);

CREATE TABLE pubsubmessages (

  message_id SERIAL,

  published_at TIMESTAMP NOT NULL DEFAULT NOW(),
  payload BYTEA NOT NULL,

  PRIMARY KEY (message_id)

);

CREATE TABLE pubsubreservedmessages (

  reservation_id INTEGER REFERENCES pubsubreservations,
  message_id INTEGER REFERENCES pubsubmessages,

  PRIMARY KEY (reservation_id, message_id)

);
