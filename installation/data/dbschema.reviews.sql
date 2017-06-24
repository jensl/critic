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
    -- The review branch.
    branch INTEGER NOT NULL REFERENCES branches,
    -- The (non-review) branch from which this review was created, if any.
    origin INTEGER REFERENCES branches ON DELETE SET NULL,
    state reviewstate NOT NULL,
    serial INTEGER NOT NULL DEFAULT 0,
    closed_by INTEGER REFERENCES users,
    dropped_by INTEGER REFERENCES users,
    applyfilters BOOLEAN NOT NULL,
    applyparentfilters BOOLEAN NOT NULL,

    summary TEXT,
    description TEXT );
CREATE INDEX reviews_branch ON reviews (branch);

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

-- Review branch updates:
--   One row per row in the 'branchupdates' table that refers to branches
--   connected with a review.
CREATE TABLE reviewupdates
  ( -- The branch update record.
    branchupdate INTEGER PRIMARY KEY REFERENCES branchupdates ON DELETE CASCADE,
    -- The review whose branch was updated.
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    -- Output, displayed in logs and also echoed by the post-receive hook if the
    -- update is performed via Git (after the regular branch update output.)
    output TEXT,
    -- Error message, if the update failed to be processed.  Since the validity
    -- of the branch update itself is checked before it happens, errors occuring
    -- at this stage are almost certainly implementation errors.
    --
    -- The error is displayed to administrators, and prevents repeated
    -- processing of the branch update (by way of inserting a review update
    -- record, despite the review not actually having been updated.)
    error TEXT );
CREATE INDEX reviewupdates_review
          ON reviewupdates (review);

-- Changesets (diffs) that are part of reviews:
--   One row per changeset that is part of a review.
CREATE TABLE reviewchangesets
  ( -- The review.
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    -- The review update that added the changeset to the review.
    branchupdate INTEGER NOT NULL REFERENCES reviewupdates ON DELETE CASCADE,
    -- The changeset.
    changeset INTEGER NOT NULL REFERENCES changesets,

    PRIMARY KEY (review, changeset) );
CREATE INDEX reviewchangesets_branchupdate
          ON reviewchangesets (branchupdate);

-- Prepared or performed review rebases:
--   One row per prepared or performed review rebase.
--
-- Record of a rebase of the review branch, or the current prepared (pending)
-- rebase of a review branch.
CREATE TABLE reviewrebases
  ( id SERIAL PRIMARY KEY,

    -- The review that will be or was rebased.
    review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
    -- The user that prepared (and later performed) the rebase.
    uid INTEGER NOT NULL REFERENCES users,
    -- The review update that performed the rebase.  NULL until the rebase has
    -- been performed (i.e. while the rebase is pending.)
    branchupdate INTEGER REFERENCES reviewupdates ON DELETE CASCADE,

    -- Upstream commit before the rebase.  NULL means the rebase is a history
    -- rewrite.
    old_upstream INTEGER REFERENCES commits,
    -- Upstream commit after the rebase.  If |old_upstream| is not NULL, NULL
    -- means "squashed into a single commit."  In this case it's set to the
    -- parent of the new head commit as part of performing the rebase.
    new_upstream INTEGER REFERENCES commits,

    -- Equivalent merge, set in case of a fast-forward move rebase.  This is a
    -- generated merge commit that is equivalent to merging the new upstream
    -- commit into the pre-rebase branch (at the old head commit.)
    equivalent_merge INTEGER REFERENCES commits,
    -- Replayed rebase, set in case of a non-ff move rebase.  This is a commit
    -- generated by cherry-picking a squash of the old review branch onto the
    -- new upstream commit.
    replayed_rebase INTEGER REFERENCES commits,

    -- Purely informative: name of branch the review was rebased onto.
    branch VARCHAR(256) );

-- Allow only one pending rebase per review.
CREATE UNIQUE INDEX reviewrebases_review
                 ON reviewrebases (review)
              WHERE branchupdate IS NULL;

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

CREATE TABLE reviewrecipientfilters
  ( review INTEGER NOT NULL REFERENCES reviews,
    uid INTEGER REFERENCES users,
    include BOOLEAN NOT NULL,

    UNIQUE (review, uid) );

CREATE TABLE checkbranchnotes
  ( repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
    branch VARCHAR(256) NOT NULL,
    upstream VARCHAR(256) NOT NULL,
    sha1 CHAR(40) NOT NULL,
    uid INTEGER NOT NULL REFERENCES users,
    review INTEGER REFERENCES reviews ON DELETE SET NULL,
    text TEXT,

    PRIMARY KEY (repository, branch, upstream, sha1) );
