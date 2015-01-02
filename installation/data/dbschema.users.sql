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

CREATE TABLE roles
  ( name VARCHAR(64) PRIMARY KEY,
    description TEXT );

INSERT INTO roles (name, description)
     VALUES ('administrator', 'Almighty system administrator.'),
            ('repositories', 'Allowed to add and configure repositories.'),
            ('developer', 'System developer.'),
            ('newswriter', 'Allowed to add and edit news items.');

CREATE TYPE userstatus AS ENUM
  ( 'unknown',
    'current',
    'absent',
    'retired' );

CREATE TABLE users
  ( id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL UNIQUE,
    fullname VARCHAR(256),
    password VARCHAR(256),
    email INTEGER, -- Foreign key constraint "REFERENCES useremails" set up later.
    status userstatus NOT NULL DEFAULT 'unknown' );

CREATE TABLE useremails
  ( id SERIAL PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    email VARCHAR(256) NOT NULL,
    verified BOOLEAN,
    verification_token VARCHAR(256),

    UNIQUE (uid, email) );

-- FIXME: This circular relation is unnecessary.  Should have a separate table
-- for mapping a user's selected email, or just store it as a boolean in the
-- useremails table instead.
ALTER TABLE users ADD CONSTRAINT users_email_fkey FOREIGN KEY (email) REFERENCES useremails;

CREATE TABLE usersessions
  ( key CHAR(28) PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users,
    atime TIMESTAMP DEFAULT NOW() );

CREATE TABLE usergitemails
  ( email VARCHAR(256),
    uid INTEGER REFERENCES users ON DELETE CASCADE,

    PRIMARY KEY (email, uid) );
CREATE INDEX usergitemails_uid ON usergitemails (uid);

CREATE TABLE userabsence
  ( uid INTEGER NOT NULL REFERENCES users,
    until DATE );
CREATE INDEX userabsence_uid_until ON userabsence (uid, until);

CREATE TABLE userroles
  ( uid INTEGER NOT NULL REFERENCES users,
    role VARCHAR(64) NOT NULL REFERENCES roles );

CREATE TABLE userresources
  ( uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    name VARCHAR(32) NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,

    PRIMARY KEY (uid, name, revision) );

CREATE TABLE externalusers
  ( id SERIAL PRIMARY KEY,
    uid INTEGER REFERENCES users,
    provider VARCHAR(16) NOT NULL,
    account VARCHAR(256) NOT NULL,
    email VARCHAR(256),
    token VARCHAR(256),

    UNIQUE (provider, account) );

CREATE TABLE oauthstates
  ( state VARCHAR(64) PRIMARY KEY,
    url TEXT,
    time TIMESTAMP NOT NULL DEFAULT NOW() );
