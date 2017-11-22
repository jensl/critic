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

CREATE TABLE extensions (

  id SERIAL,

  -- Local user who published the extension (i.e. made it available to install
  -- on this Critic system.) NULL means its a system extension ("published" by
  -- an unnamed system administrator.)
  publisher INTEGER,
  -- Extension name.
  name VARCHAR(64) NOT NULL,
  -- Repository URI, if hosted externally.
  uri TEXT,

  PRIMARY KEY (id),
  FOREIGN KEY (publisher) REFERENCES users,
  UNIQUE (publisher, name)

);

-- Individual extension versions.
--
-- There will be one row per commit that has (or might have been) installed of
-- a given named version of an extension.
CREATE TABLE extensionversions (

  id SERIAL,

  -- The extension this is a version of.
  extension INTEGER NOT NULL,
  -- The version name, e.g. "stable". NULL means "live" version.
  name VARCHAR(256),
  -- The SHA-1 of the commit.
  sha1 CHAR(40) NOT NULL,
  -- True if this is the current version of the extension, i.e. the one users
  -- would typically install when installing the named version.
  current BOOLEAN NOT NULL DEFAULT TRUE,
  -- True if the extension was invalid at this point, and thus can't be
  -- installed.
  invalid BOOLEAN NOT NULL,
  -- Error message if `invalid` is true.
  message TEXT,

  PRIMARY KEY (id),
  FOREIGN KEY (extension) REFERENCES extensions ON DELETE CASCADE,
  UNIQUE (extension, name, sha1)

);

-- Installed extensions.
-- If uid=NULL, it is a "universal install" (affecting all users.)
-- If version=NULL, the "LIVE" version is installed.
CREATE TABLE extensioninstalls (
  id SERIAL,

  uid INTEGER,
  extension INTEGER NOT NULL,
  version INTEGER,

  PRIMARY KEY (id),
  FOREIGN KEY (uid) REFERENCES users ON DELETE CASCADE,
  FOREIGN KEY (extension) REFERENCES extensions ON DELETE CASCADE,
  FOREIGN KEY (version) REFERENCES extensionversions ON DELETE CASCADE,
  UNIQUE (uid, extension)
);

CREATE TABLE extensionroles
  ( id SERIAL PRIMARY KEY,
    version INTEGER NOT NULL REFERENCES extensionversions ON DELETE CASCADE,
    description TEXT NOT NULL,
    flavor VARCHAR(16),
    entrypoint VARCHAR(256),
    script VARCHAR(256),
    function VARCHAR(64) );

CREATE TABLE extensionendpointroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL );

CREATE TABLE extensionprocesscommitsroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE );

CREATE TABLE extensionfilterhookroles
  ( role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    title VARCHAR(64) NOT NULL,
    role_description TEXT,
    data_description TEXT );

CREATE TABLE extensionuiaddonroles (
  role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,
  name VARCHAR(64) NOT NULL,
  bundle_js VARCHAR(256),
  bundle_css VARCHAR(256)
);

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
  ( extension INTEGER NOT NULL REFERENCES extensions ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    key VARCHAR(64) NOT NULL,
    text TEXT NOT NULL,

    PRIMARY KEY (extension, uid, key) );

CREATE TABLE extensionlog
  ( extension INTEGER NOT NULL REFERENCES extensions ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    category VARCHAR(64) NOT NULL DEFAULT 'default',
    time TIMESTAMP NOT NULL DEFAULT NOW(),
    text TEXT NOT NULL );
CREATE INDEX extensionlog_extension_uid_category ON extensionlog(extension, uid, category);

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

CREATE TABLE extensionsubscriptionroles (

  role INTEGER NOT NULL REFERENCES extensionroles ON DELETE CASCADE,

  channel VARCHAR NOT NULL

);

CREATE TABLE extensionpubsubreservations (

  install_id INTEGER NOT NULL REFERENCES extensioninstalls ON DELETE CASCADE,
  reservation_id INTEGER NOT NULL REFERENCES pubsubreservations,

  PRIMARY KEY (install_id, reservation_id)

);
