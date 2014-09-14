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

CREATE TABLE systemidentities
  ( key VARCHAR(32) PRIMARY KEY,
    name VARCHAR(64) UNIQUE,
    anonymous_scheme VARCHAR(5) NOT NULL,
    authenticated_scheme VARCHAR(5) NOT NULL,
    hostname VARCHAR(265) NOT NULL,
    description VARCHAR(256) NOT NULL,
    installed_sha1 CHAR(40) NOT NULL,
    installed_at TIMESTAMP DEFAULT NOW() NOT NULL );

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
    email INTEGER, -- Foreign key constraint "REFERENCES users" set up later.
    status userstatus NOT NULL DEFAULT 'unknown' );

CREATE TABLE useremails
  ( id SERIAL PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    email VARCHAR(256) NOT NULL,
    verified BOOLEAN,
    verification_token VARCHAR(256),

    UNIQUE (uid, email) );

ALTER TABLE users ADD CONSTRAINT users_email_fkey FOREIGN KEY (email) REFERENCES useremails;

CREATE TABLE usersessions
  ( key CHAR(28) PRIMARY KEY,
    uid INTEGER NOT NULL REFERENCES users,
    atime TIMESTAMP DEFAULT NOW() );

CREATE TABLE gitusers
  ( id SERIAL PRIMARY KEY,
    email VARCHAR(256) NOT NULL,
    fullname VARCHAR(256) NOT NULL,

    UNIQUE (email, fullname) );

CREATE TABLE usergitemails
  ( email VARCHAR(256),
    uid INTEGER REFERENCES users ON DELETE CASCADE,

    PRIMARY KEY (email, uid) );
CREATE INDEX usergitemails_uid ON usergitemails (uid);

CREATE TABLE userabsence
  ( uid INTEGER NOT NULL REFERENCES users,
    until DATE );
CREATE INDEX userabsence_uid_until ON userabsence (uid, until);

CREATE TABLE roles
  ( name VARCHAR(64) PRIMARY KEY,
    description TEXT );

CREATE TABLE userroles
  ( uid INTEGER NOT NULL REFERENCES users,
    role VARCHAR(64) NOT NULL REFERENCES roles );

CREATE TABLE repositories
  ( id SERIAL PRIMARY KEY,
    parent INTEGER REFERENCES repositories,
    branch INTEGER, -- Foreign key constraint "REFERENCES branches" set up later.
    name VARCHAR(64) NOT NULL UNIQUE,
    path VARCHAR(256) NOT NULL UNIQUE );

CREATE TABLE knownremotes
  ( url VARCHAR(256) PRIMARY KEY,
    pushing BOOLEAN NOT NULL -- This remote has a post-update hook (or similar)
                             -- that contacts the branchtrackerhook service and
                             -- triggers immediate updates of tracked branches.
  );

CREATE TABLE trackedbranches
  ( id SERIAL PRIMARY KEY,
    repository INTEGER NOT NULL REFERENCES repositories,
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

CREATE TABLE files
  ( id SERIAL PRIMARY KEY,
    path TEXT NOT NULL );

-- Index used to enforce uniqueness, and for quick lookup of single
-- paths (using "SELECT id FROM files WHERE MD5(path)=MD5(...)".
CREATE UNIQUE INDEX files_path_md5 ON files (MD5(path));

-- Index used for path searches, for instance when searching for
-- reviews that touch files in a certain directory.
CREATE INDEX files_path_gin ON files USING gin (STRING_TO_ARRAY(path, '/'));

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

CREATE TABLE commits
  ( id SERIAL PRIMARY KEY,
    sha1 CHAR(40) NOT NULL UNIQUE,
    author_gituser INTEGER NOT NULL REFERENCES gitusers,
    commit_gituser INTEGER NOT NULL REFERENCES gitusers,
    author_time TIMESTAMP NOT NULL,
    commit_time TIMESTAMP NOT NULL );

CREATE TABLE edges
  ( parent INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE,
    child INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE );
CREATE INDEX edges_parent ON edges (parent);
CREATE INDEX edges_child ON edges (child);

CREATE TYPE branchtype AS ENUM
  ( 'normal',
    'review' );
CREATE TABLE branches
  ( id SERIAL PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    head INTEGER NOT NULL REFERENCES commits,
    base INTEGER REFERENCES branches,
    tail INTEGER REFERENCES commits,
    type branchtype NOT NULL DEFAULT 'normal',
    review INTEGER, -- Foreign key constraint "REFERENCES reviews" set up later.
    archived BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (repository, name) );

ALTER TABLE repositories ADD CONSTRAINT repositories_branch_fkey FOREIGN KEY (branch) REFERENCES branches;

CREATE TABLE reachable
  ( branch INTEGER NOT NULL REFERENCES branches ON DELETE CASCADE,
    commit INTEGER NOT NULL REFERENCES commits,

    PRIMARY KEY (branch, commit) );
CREATE INDEX reachable_branch ON reachable (branch);
CREATE INDEX reachable_commit ON reachable (commit);

CREATE TABLE tags
  ( id SERIAL PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    sha1 CHAR(40) NOT NULL,

    UNIQUE (repository, name) );
CREATE INDEX tags_repository_sha1 ON tags (repository, sha1);

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

CREATE TABLE mergereplays
  ( original INTEGER PRIMARY KEY REFERENCES commits ON DELETE CASCADE,
    replay INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE );

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

CREATE TYPE reviewtype AS ENUM
  ( 'official',
    'rfc',
    'ad-hoc' );
CREATE TYPE reviewstate AS ENUM
  ( 'draft',
    'open',
    'closed',
    'dropped' );
CREATE TABLE reviews
  ( id SERIAL PRIMARY KEY,
    type reviewtype NOT NULL,
    branch INTEGER NOT NULL REFERENCES branches,
    state reviewstate NOT NULL,
    serial INTEGER NOT NULL DEFAULT 0,
    closed_by INTEGER REFERENCES users,
    dropped_by INTEGER REFERENCES users,
    applyfilters BOOLEAN NOT NULL,
    applyparentfilters BOOLEAN NOT NULL,

    summary TEXT,
    description TEXT );
CREATE INDEX reviews_branch ON reviews (branch);

ALTER TABLE branches ADD CONSTRAINT branches_review_fkey FOREIGN KEY (review) REFERENCES reviews ON DELETE SET NULL;

CREATE TABLE scheduledreviewbrancharchivals
  ( review INTEGER PRIMARY KEY REFERENCES reviews (id),
    deadline TIMESTAMP NOT NULL );

CREATE TABLE reviewfilters
  ( id SERIAL PRIMARY KEY,

    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    path TEXT NOT NULL,
    type filtertype NOT NULL,
    creator INTEGER NOT NULL REFERENCES users ON DELETE CASCADE );

-- Index used to enforce uniqueness.
CREATE UNIQUE INDEX reviewfilters_review_uid_path_md5 ON reviewfilters (review, uid, MD5(path));

CREATE TABLE batches
  ( id SERIAL PRIMARY KEY,
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    comment INTEGER, -- REFERENCES commentchains,
    time TIMESTAMP NOT NULL DEFAULT NOW() );
CREATE INDEX batches_review_uid ON batches (review, uid);

CREATE TYPE reviewusertype AS ENUM
  ( 'automatic',
    'manual' );
CREATE TABLE reviewusers
  ( review INTEGER NOT NULL,
    uid INTEGER NOT NULL,
    owner BOOLEAN NOT NULL DEFAULT FALSE,
    type reviewusertype NOT NULL DEFAULT 'automatic',

    PRIMARY KEY (review, uid),
    FOREIGN KEY (review) REFERENCES reviews(id) ON DELETE CASCADE,
    FOREIGN KEY (uid) REFERENCES users(id) );
CREATE INDEX reviewusers_uid ON reviewusers (uid);

CREATE TABLE reviewchangesets
  ( review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    changeset INTEGER NOT NULL REFERENCES changesets,

    PRIMARY KEY (review, changeset) );

CREATE TABLE reviewrebases
  ( id SERIAL PRIMARY KEY,
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    old_head INTEGER NOT NULL REFERENCES commits,
    new_head INTEGER REFERENCES commits,
    old_upstream INTEGER REFERENCES commits,
    new_upstream INTEGER REFERENCES commits,
    uid INTEGER NOT NULL REFERENCES users,
    branch VARCHAR(256),

    UNIQUE (review, old_head) );

CREATE TABLE previousreachable
  ( rebase INTEGER NOT NULL REFERENCES reviewrebases ON DELETE CASCADE,
    commit INTEGER NOT NULL REFERENCES commits );
CREATE INDEX previousreachable_rebase ON previousreachable (rebase);

CREATE TYPE reviewfilestate AS ENUM
  ( 'pending',    -- No one has said anything.
    'reviewed'    -- The file has been reviewed.
  );
CREATE TABLE reviewfiles
  ( id SERIAL PRIMARY KEY,

    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    changeset INTEGER NOT NULL REFERENCES changesets ON DELETE CASCADE,
    file INTEGER NOT NULL REFERENCES files ON DELETE CASCADE,

    deleted INTEGER NOT NULL,
    inserted INTEGER NOT NULL,

    state reviewfilestate NOT NULL DEFAULT 'pending',
    reviewer INTEGER REFERENCES users ON DELETE SET NULL,
    time TIMESTAMP,

    FOREIGN KEY (review, changeset) REFERENCES reviewchangesets ON DELETE CASCADE,
    FOREIGN KEY (changeset, file) REFERENCES fileversions ON DELETE CASCADE );

CREATE INDEX reviewfiles_review_changeset ON reviewfiles (review, changeset);
CREATE INDEX reviewfiles_review_state ON reviewfiles (review, state);

CREATE TABLE reviewassignmentstransactions
  ( id SERIAL PRIMARY KEY,

    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    assigner INTEGER NOT NULL REFERENCES users,
    note TEXT,

    time TIMESTAMP DEFAULT NOW() );

CREATE TABLE reviewassignmentchanges
  ( transaction INTEGER NOT NULL REFERENCES reviewassignmentstransactions,

    file INTEGER NOT NULL REFERENCES reviewfiles ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users,
    assigned BOOLEAN NOT NULL,

    PRIMARY KEY (transaction, file, uid) );

CREATE TABLE reviewfilterchanges
  ( transaction INTEGER NOT NULL REFERENCES reviewassignmentstransactions ON DELETE CASCADE,

    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    path TEXT NOT NULL,
    type filtertype NOT NULL,
    created BOOLEAN NOT NULL );

CREATE TABLE reviewuserfiles
  ( file INTEGER NOT NULL REFERENCES reviewfiles ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users,

    time TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (file, uid) );

CREATE INDEX reviewuserfiles_uid ON reviewuserfiles (uid);

CREATE VIEW reviewfilesharing
  AS SELECT reviewfiles.review AS review, reviewfiles.id AS file, COUNT(reviewuserfiles.uid) AS reviewers
       FROM reviewfiles
       JOIN reviewuserfiles ON (reviewfiles.id=reviewuserfiles.file)
       JOIN users ON (users.id=reviewuserfiles.uid)
      WHERE users.status='current'
   GROUP BY reviewfiles.review, reviewfiles.id;

CREATE TYPE reviewfilechangestate AS ENUM
  ( 'draft',     -- This change hasn't been performed yet.
    'performed', -- The change has been performed.
    'rejected'   -- The change was rejected; affected file wasn't in expected
                 -- state (concurrent update.)
  );
CREATE TABLE reviewfilechanges
  ( batch INTEGER REFERENCES batches,
    file INTEGER NOT NULL REFERENCES reviewfiles,
    uid INTEGER NOT NULL REFERENCES users,

    time TIMESTAMP NOT NULL DEFAULT NOW(),
    state reviewfilechangestate NOT NULL DEFAULT 'draft',
    from_state reviewfilestate NOT NULL,
    to_state reviewfilestate NOT NULL,

    FOREIGN KEY (file, uid) REFERENCES reviewuserfiles ON DELETE CASCADE );

CREATE INDEX reviewfilechanges_batch ON reviewfilechanges (batch);
CREATE INDEX reviewfilechanges_file ON reviewfilechanges (file);
CREATE INDEX reviewfilechanges_uid_state ON reviewfilechanges (uid, state);
CREATE INDEX reviewfilechanges_time ON reviewfilechanges (time);

CREATE TABLE lockedreviews
  ( review INTEGER PRIMARY KEY REFERENCES reviews );

CREATE VIEW fullreviewuserfiles
  AS SELECT reviewfiles.review as review,
            reviewfiles.changeset as changeset,
            reviewfiles.file as file,
            reviewfiles.deleted as deleted,
            reviewfiles.inserted as inserted,
            reviewfiles.state as state,
            reviewfiles.reviewer as reviewer,
            reviewuserfiles.uid as assignee
       FROM reviewfiles
       JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id);

CREATE TABLE reviewmessageids
  ( uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    messageid CHAR(24) NOT NULL,

    PRIMARY KEY (uid, review) );

CREATE INDEX reviewmessageids_review ON reviewmessageids (review);

CREATE TABLE userresources
  ( uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    name VARCHAR(32) NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,

    PRIMARY KEY (uid, name, revision) );

CREATE TABLE reviewmergeconfirmations
  ( id SERIAL PRIMARY KEY,
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    merge INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE,
    tail INTEGER REFERENCES commits ON DELETE CASCADE,
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (review, uid, merge) );

CREATE TABLE reviewmergecontributions
  ( id INTEGER NOT NULL REFERENCES reviewmergeconfirmations ON DELETE CASCADE,
    merged INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE,

    PRIMARY KEY (id, merged) );

CREATE TABLE newsitems
  ( id SERIAL PRIMARY KEY,
    date DATE DEFAULT NOW(),
    text TEXT NOT NULL );

CREATE TABLE newsread
  ( item INTEGER NOT NULL REFERENCES newsitems ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE );

CREATE TABLE checkbranchnotes
  ( repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    branch VARCHAR(256) NOT NULL,
    upstream VARCHAR(256) NOT NULL,
    sha1 CHAR(40) NOT NULL,
    uid INTEGER NOT NULL REFERENCES users,
    review INTEGER REFERENCES reviews ON DELETE SET NULL,
    text TEXT,

    PRIMARY KEY (repository, branch, upstream, sha1) );

CREATE TABLE mergebases
  ( commit INTEGER PRIMARY KEY REFERENCES commits ON DELETE CASCADE,
    mergebase CHAR(40) );

CREATE TABLE relevantcommits
  ( commit INTEGER REFERENCES commits ON DELETE CASCADE,
    parent SMALLINT NOT NULL,
    file INTEGER REFERENCES files,
    relevant INTEGER REFERENCES commits ON DELETE CASCADE,

    PRIMARY KEY (commit, parent, file, relevant) );

CREATE TABLE reviewrecipientfilters
  ( review INTEGER NOT NULL REFERENCES reviews,
    uid INTEGER REFERENCES users,
    include BOOLEAN NOT NULL,

    UNIQUE (review, uid) );

CREATE TABLE timezones
  ( name VARCHAR(256) PRIMARY KEY,
    abbrev VARCHAR(16) NOT NULL,
    utc_offset INTERVAL NOT NULL );

INSERT INTO timezones (name, abbrev, utc_offset)
     VALUES ('Universal/UTC', 'UTC', INTERVAL '0');

CREATE TYPE preferencetype AS ENUM
  ( 'boolean',
    'integer',
    'string' );
CREATE TABLE preferences
  ( item VARCHAR(64) PRIMARY KEY,
    type preferencetype NOT NULL,
    description TEXT NOT NULL,

    -- If TRUE, this preference is relevant to configure per system (IOW
    -- globally), per user, per repository and/or per filter.  This controls
    -- whether the preference is displayed on the corresponding /config page
    -- variant.
    per_system BOOLEAN NOT NULL DEFAULT TRUE,
    per_user BOOLEAN NOT NULL DEFAULT TRUE,
    per_repository BOOLEAN NOT NULL DEFAULT FALSE,
    per_filter BOOLEAN NOT NULL DEFAULT FALSE );

CREATE TABLE userpreferences
  ( item VARCHAR(64) NOT NULL REFERENCES preferences,
    uid INTEGER REFERENCES users ON DELETE CASCADE,
    repository INTEGER REFERENCES repositories ON DELETE CASCADE,
    filter INTEGER REFERENCES filters ON DELETE CASCADE,

    integer INTEGER,
    string TEXT,

    -- Invariant: If 'filter' is not NULL, then 'uid' must not be NULL.
    CONSTRAINT check_uid_filter CHECK (filter IS NULL OR uid IS NOT NULL),

    -- Invariant: At least one of 'repository' and 'filter' must be NULL.
    CONSTRAINT check_repository_filter CHECK (repository IS NULL OR filter IS NULL) );

-- These indexes are primarily used to enforce uniqueness.  The three columns
-- 'uid', 'repository' and 'filter' can all be NULL (in various configurations)
-- and from a uniqueness point of view, we want those NULL to behave as if they
-- compared equal.
CREATE UNIQUE INDEX userpreferences_item
                 ON userpreferences (item)
              WHERE uid IS NULL
                AND repository IS NULL
                AND filter IS NULL;
CREATE UNIQUE INDEX userpreferences_item_uid
                 ON userpreferences (item, uid)
              WHERE uid IS NOT NULL
                AND repository IS NULL
                AND filter IS NULL;
CREATE UNIQUE INDEX userpreferences_item_repository
                 ON userpreferences (item, repository)
              WHERE uid IS NULL
                AND repository IS NOT NULL
                AND filter IS NULL;
CREATE UNIQUE INDEX userpreferences_item_uid_repository
                 ON userpreferences (item, uid, repository)
              WHERE uid IS NOT NULL
                AND repository IS NOT NULL
                AND filter IS NULL;
CREATE UNIQUE INDEX userpreferences_item_uid_filter
                 ON userpreferences (item, uid, filter)
              WHERE uid IS NOT NULL
                AND repository IS NULL
                AND filter IS NOT NULL;

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
