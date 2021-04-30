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
    'retired',
    'disabled' );

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(64) NOT NULL UNIQUE,
  fullname VARCHAR(256),
  password VARCHAR(256),
  status userstatus NOT NULL DEFAULT 'unknown'
);

ALTER TABLE settings
  ADD CONSTRAINT settings_user
    FOREIGN KEY ("user") REFERENCES users (id) ON DELETE CASCADE;

CREATE TYPE useremailstatus AS ENUM (
  'trusted',
  'verified',
  'unverified'
);

CREATE TABLE useremails (
  id SERIAL PRIMARY KEY,
  uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
  email VARCHAR(256) NOT NULL,
  status useremailstatus NOT NULL DEFAULT 'unverified',
  token VARCHAR(256),

  UNIQUE (id, uid),
  UNIQUE (uid, email)
);

CREATE INDEX useremails_id_uid
          ON useremails (id, uid);

CREATE TABLE selecteduseremails (
  uid INTEGER NOT NULL,
  email INTEGER NOT NULL,

  PRIMARY KEY (uid),
  FOREIGN KEY (uid) REFERENCES users ON DELETE CASCADE,
  FOREIGN KEY (email, uid) REFERENCES useremails (id, uid) ON DELETE CASCADE
);

CREATE INDEX selecteduseremails_email
          ON selecteduseremails (email);

CREATE VIEW userswithemail (id, name, fullname, password, status, email) AS
          SELECT users.id, users.name, users.fullname, users.password,
                 users.status, useremails.email
            FROM users
 LEFT OUTER JOIN selecteduseremails ON (selecteduseremails.uid=users.id)
 LEFT OUTER JOIN useremails ON (
                   useremails.id=selecteduseremails.email AND
                   useremails.status!='unverified'
                 );

CREATE VIEW useremailswithselected (id, uid, email, status, token,
                                    selected) AS
          SELECT useremails.id, useremails.uid, useremails.email,
                 useremails.status, useremails.token,
                 selecteduseremails.uid IS NOT NULL
            FROM useremails
 LEFT OUTER JOIN selecteduseremails ON (selecteduseremails.email=useremails.id);

CREATE TABLE externalusers (
  id SERIAL PRIMARY KEY,
  uid INTEGER REFERENCES users,
  provider VARCHAR(16) NOT NULL,
  account VARCHAR(256) NOT NULL,
  username VARCHAR(256),
  fullname VARCHAR(256),
  email VARCHAR(256),

  UNIQUE (provider, account)
);

CREATE TABLE usersessions (
  key CHAR(28) PRIMARY KEY,
  uid INTEGER REFERENCES users,
  external_uid INTEGER REFERENCES externalusers,
  labels VARCHAR(256),
  atime TIMESTAMP DEFAULT NOW(),

  CONSTRAINT check_uid_or_external_uid
    CHECK (uid IS NOT NULL OR external_uid IS NOT NULL)
);

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

CREATE TABLE oauthstates
  ( state VARCHAR(64) PRIMARY KEY,
    url TEXT,
    time TIMESTAMP NOT NULL DEFAULT NOW() );

CREATE TYPE systemaccesstype AS ENUM
  ( -- The system is accessed as a named user.
    'user',
    -- The system is accessed by a system service or similar.
    'system',
    -- The system is accessed anonymously.
    'anonymous' );

CREATE TABLE accesstokens (

  id SERIAL PRIMARY KEY,

  -- The type of access granted by this access token.
  access_type systemaccesstype NOT NULL DEFAULT 'user',
  -- The user (when access_type='user') or NULL.
  uid INTEGER REFERENCES users ON DELETE CASCADE,

  -- Secret part of access token.
  token VARCHAR NOT NULL,

  -- Access token title.
  title VARCHAR(256),

  UNIQUE (token),

  CONSTRAINT valid_user CHECK ((access_type='user' AND uid IS NOT NULL) OR
                                (access_type!='user' AND uid IS NULL))

);

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

CREATE TABLE usersettings (
  -- Unique id.
  id SERIAL PRIMARY KEY,

  -- User.
  uid INTEGER NOT NULL REFERENCES users,
  -- Setting scope, e.g. "ui".
  scope VARCHAR(64) NOT NULL,
  -- Setting name.
  name VARCHAR(256) NOT NULL,
  -- Setting value. Stored JSON encoded.
  value JSON NOT NULL,

  UNIQUE (uid, scope, name)
);

-- User-provided SSH keys. If Critic's SSH service is running, it will allow
-- users to authenticate as critic@<hostname> using these keys, and run Git over
-- SSH.
CREATE TABLE usersshkeys (
  -- Unique id.
  id SERIAL PRIMARY KEY,

  -- User who owns this key and can authenticate using it.
  uid INTEGER NOT NULL,
  -- Key type. Typically one of "rsa", "dsa", "ecdsa" or "ed25519", but we don't
  -- really care as long as the SSH daemon and sshpubkeys package like it.
  type VARCHAR(32) NOT NULL,
  -- The actual key, base64-encoded.
  key TEXT NOT NULL,
  -- Comment. Useful for users to keep track of the keys, but otherwise not
  -- significant.
  comment TEXT,

  FOREIGN KEY (uid)
    REFERENCES users ON DELETE CASCADE,

  -- There is no point for a user to register the same key twice, and it would
  -- be problematic if two users were to register the same key, since we would
  -- then not be able to tell them apart during authentication.
  UNIQUE (type, key)
);

CREATE INDEX usersshkeys_uid
          ON usersshkeys (uid);
