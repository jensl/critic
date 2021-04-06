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

CREATE TYPE reviewstate AS ENUM
  ( 'draft',
    'open',
    'closed',
    'dropped' );
CREATE TABLE reviews (

  id SERIAL,

  -- The repository in which the commits to review live.
  repository INTEGER NOT NULL,
  -- The review branch.
  branch INTEGER,
  -- The (non-review) branch from which this review was created, if any.
  origin INTEGER,
  state reviewstate NOT NULL DEFAULT 'draft',
  serial INTEGER NOT NULL DEFAULT 0,
  closed_by INTEGER,
  dropped_by INTEGER,
  applyfilters BOOLEAN NOT NULL DEFAULT TRUE,
  applyparentfilters BOOLEAN NOT NULL DEFAULT TRUE,

  -- Integration target branch.
  integration_target INTEGER,
  -- Last evaluated update of the target branch. When the target branch is
  -- updated, we update the count in `integration_behind` and also the
  -- `reviewintegrationconflicts` table based on the new target branch state.
  integration_branchupdate INTEGER,
  -- The count returned by `git rev-list --count <target> ^<review>`.
  integration_behind INTEGER,
  -- True if the review has been integrated into the target branch. Typically
  -- set to true at the same time as the review is closed, if it has a target
  -- branch.
  integration_performed BOOLEAN NOT NULL DEFAULT FALSE,

  summary TEXT,
  description TEXT,

  PRIMARY KEY (id),
  FOREIGN KEY (repository) REFERENCES repositories,
  FOREIGN KEY (branch) REFERENCES branches,
  FOREIGN KEY (origin) REFERENCES branches ON DELETE SET NULL,
  FOREIGN KEY (closed_by) REFERENCES users,
  FOREIGN KEY (dropped_by) REFERENCES users,
  FOREIGN KEY (integration_target) REFERENCES branches

);
CREATE INDEX reviews_branch ON reviews (branch);
CREATE INDEX reviews_integration_target ON reviews (integration_target);

CREATE TYPE revieweventtype AS ENUM (
  'created',
  'ready',
  'published',
  'closed',
  'dropped',
  'reopened',
  'pinged',
  'assignments',
  'branchupdate',
  'batch'
);

CREATE TABLE reviewevents (
  -- Unique event id.
  id SERIAL PRIMARY KEY,

  -- The review in which the event occurred.
  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  -- User that triggered the event, or NULL if it was triggered by the system.
  uid INTEGER REFERENCES users,
  -- Type of event.
  type revieweventtype NOT NULL,

  -- Set to true when the event has been processed by the "reviewevents"
  -- background service. For most events, this involves generating emails about
  -- the event to send to reviewers and watchers.
  processed BOOLEAN NOT NULL DEFAULT FALSE,

  -- Set to true if processing the event fails.
  failed BOOLEAN NOT NULL DEFAULT FALSE,

  -- The point in time when the event occurred.
  time TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX reviewevents_review_uid
          ON reviewevents (review, uid);

CREATE TABLE scheduledreviewbrancharchivals
  ( review INTEGER PRIMARY KEY REFERENCES reviews ON DELETE CASCADE,
    deadline TIMESTAMP NOT NULL );

CREATE TABLE batches (
  id SERIAL PRIMARY KEY,
  event INTEGER NOT NULL REFERENCES reviewevents ON DELETE CASCADE,
  comment INTEGER -- REFERENCES comments
);
CREATE INDEX batches_event
          ON batches (event);

CREATE TYPE reviewusertype AS ENUM
  ( 'automatic',
    'manual' );
CREATE TABLE reviewusers (

  review INTEGER NOT NULL,
  event INTEGER NOT NULL,
  uid INTEGER NOT NULL,
  owner BOOLEAN NOT NULL DEFAULT FALSE,
  type reviewusertype NOT NULL DEFAULT 'automatic',

  PRIMARY KEY (review, uid),
  FOREIGN KEY (review) REFERENCES reviews ON DELETE CASCADE,
  FOREIGN KEY (event) REFERENCES reviewevents ON DELETE CASCADE,
  FOREIGN KEY (uid) REFERENCES users

);
CREATE INDEX reviewusers_uid ON reviewusers (uid);
CREATE INDEX reviewusers_review_event ON reviewusers (review, event);

-- Review branch updates:
--   One row per row in the 'branchupdates' table that refers to branches
--   connected with a review.
CREATE TABLE reviewupdates (
  -- The branch update record.
  branchupdate INTEGER PRIMARY KEY REFERENCES branchupdates ON DELETE CASCADE,
  -- The corresponding review event.
  event INTEGER NOT NULL REFERENCES reviewevents ON DELETE CASCADE,
  -- Error message, if the update failed to be processed.  Since the validity
  -- of the branch update itself is checked before it happens, errors occuring
  -- at this stage are almost certainly implementation errors.
  --
  -- The error is displayed to administrators, and prevents repeated
  -- processing of the branch update (by way of inserting a review update
  -- record, despite the review not actually having been updated.)
  error TEXT
);
CREATE INDEX reviewupdates_event
          ON reviewupdates (event);

-- Commits that are part of the review:
--   One row per commit that is part of a review.
CREATE TABLE reviewcommits (
 -- The review.
  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  -- The review update that added the commit to the review, or NULL if the
  -- commit was added when the review was created.
  branchupdate INTEGER REFERENCES reviewupdates ON DELETE CASCADE,
  -- The commit.
  commit INTEGER NOT NULL REFERENCES commits,

  PRIMARY KEY (review, commit)
);
CREATE INDEX reviewcommits_branchupdate
          ON reviewcommits (branchupdate);

-- Changesets (diffs) that are part of reviews:
--   One row per changeset that is part of a review.
CREATE TABLE reviewchangesets (
  -- The review.
  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  -- The review update that added the changeset to the review.
  branchupdate INTEGER REFERENCES reviewupdates ON DELETE CASCADE,
  -- The changeset.
  changeset INTEGER NOT NULL REFERENCES changesets ON DELETE CASCADE,

  PRIMARY KEY (review, changeset)
);
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
    uid INTEGER REFERENCES users,
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

CREATE INDEX reviewrebases_branchupdate
          ON reviewrebases (branchupdate);

CREATE TABLE reviewscopes (

  id SERIAL PRIMARY KEY,

  name VARCHAR(256),
  UNIQUE (name)

);

CREATE TABLE reviewscopefilters (

  id SERIAL PRIMARY KEY,

  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  scope INTEGER NOT NULL REFERENCES reviewscopes ON DELETE CASCADE,

  path TEXT NOT NULL,
  included BOOLEAN NOT NULL

);


CREATE TYPE filtertype AS ENUM (

  'reviewer',
  'watcher',
  'ignored'

);
CREATE TABLE repositoryfilters (

  id SERIAL PRIMARY KEY,
  uid INTEGER NOT NULL REFERENCES users,
  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  path TEXT NOT NULL,
  type filtertype NOT NULL,
  default_scope BOOLEAN NOT NULL

);

-- Index used to enforce uniqueness.
CREATE UNIQUE INDEX repositoryfilters_uid_repository_path_md5
                 ON repositoryfilters (uid, repository, MD5(path));

CREATE TABLE repositoryfilterscopes (

  "filter" INTEGER REFERENCES repositoryfilters ON DELETE CASCADE,
  "scope" INTEGER REFERENCES reviewscopes ON DELETE CASCADE,

  PRIMARY KEY ("filter", "scope")

);

CREATE TABLE repositoryfilterdelegates (

  "filter" INTEGER REFERENCES repositoryfilters ON DELETE CASCADE,
  "uid" INTEGER REFERENCES users ON DELETE CASCADE,

  PRIMARY KEY ("filter", "uid")

);

CREATE TABLE reviewfilters (

  id SERIAL PRIMARY KEY,

  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
  path TEXT NOT NULL,
  type filtertype NOT NULL,
  default_scope BOOLEAN NOT NULL,
  creator INTEGER NOT NULL REFERENCES users ON DELETE CASCADE

);

-- Index used to enforce uniqueness.
CREATE UNIQUE INDEX reviewfilters_review_uid_path_md5 ON reviewfilters (review, uid, MD5(path));

CREATE TABLE reviewfilterscopes (

  "filter" INTEGER REFERENCES reviewfilters ON DELETE CASCADE,
  "scope" INTEGER REFERENCES reviewscopes ON DELETE CASCADE,

  PRIMARY KEY ("filter", "scope")

);

CREATE TABLE reviewfiles (

  id SERIAL PRIMARY KEY,

  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  changeset INTEGER NOT NULL REFERENCES changesets ON DELETE CASCADE,
  file INTEGER NOT NULL REFERENCES files ON DELETE CASCADE,
  scope INTEGER REFERENCES reviewscopes ON DELETE CASCADE,

  deleted INTEGER NOT NULL,
  inserted INTEGER NOT NULL,

  reviewed BOOLEAN NOT NULL DEFAULT FALSE,
  time TIMESTAMP,

  FOREIGN KEY (review, changeset) REFERENCES reviewchangesets ON DELETE CASCADE,
  FOREIGN KEY (changeset, file) REFERENCES changesetfiles ON DELETE CASCADE

);

CREATE INDEX reviewfiles_review_changeset ON reviewfiles (review, changeset);
CREATE INDEX reviewfiles_review_reviewed ON reviewfiles (review, reviewed);

CREATE TABLE reviewassignmentstransactions (

  id SERIAL PRIMARY KEY,

  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  event INTEGER NOT NULL REFERENCES reviewevents ON DELETE CASCADE,
  assigner INTEGER NOT NULL REFERENCES users,
  note TEXT,

  time TIMESTAMP DEFAULT NOW()

);

CREATE TABLE reviewassignmentchanges (

  transaction INTEGER NOT NULL REFERENCES reviewassignmentstransactions,

  file INTEGER NOT NULL REFERENCES reviewfiles ON DELETE CASCADE,
  uid INTEGER NOT NULL REFERENCES users,
  assigned BOOLEAN NOT NULL,

  PRIMARY KEY (transaction, file, uid)

);

CREATE TABLE reviewfilterchanges (

  transaction INTEGER NOT NULL REFERENCES reviewassignmentstransactions ON DELETE CASCADE,

  uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
  path TEXT NOT NULL,
  type filtertype NOT NULL,
  created BOOLEAN NOT NULL

);

CREATE TABLE reviewuserfiles (

  file INTEGER NOT NULL REFERENCES reviewfiles ON DELETE CASCADE,
  uid INTEGER NOT NULL REFERENCES users,

  reviewed BOOLEAN NOT NULL DEFAULT FALSE,
  time TIMESTAMP DEFAULT NOW(),

  PRIMARY KEY (file, uid)

);

CREATE INDEX reviewuserfiles_uid ON reviewuserfiles (uid);

CREATE VIEW reviewfilesharing
  AS SELECT reviewfiles.review AS review, reviewfiles.id AS file, COUNT(reviewuserfiles.uid) AS reviewers
       FROM reviewfiles
       JOIN reviewuserfiles ON (reviewfiles.id=reviewuserfiles.file)
       JOIN users ON (users.id=reviewuserfiles.uid)
      WHERE users.status='current'
   GROUP BY reviewfiles.review, reviewfiles.id;

CREATE TYPE reviewuserfilechangestate AS ENUM (

  'draft',     -- This change hasn't been performed yet.
  'performed', -- The change has been performed.
  'rejected'   -- The change was rejected; affected file wasn't in expected
               -- state (concurrent update.)

);

CREATE TABLE reviewuserfilechanges (

  batch INTEGER REFERENCES batches,
  file INTEGER NOT NULL REFERENCES reviewfiles ON DELETE CASCADE,
  uid INTEGER NOT NULL REFERENCES users,

  time TIMESTAMP NOT NULL DEFAULT NOW(),
  state reviewuserfilechangestate NOT NULL DEFAULT 'draft',
  from_reviewed BOOLEAN NOT NULL,
  to_reviewed BOOLEAN NOT NULL,

  FOREIGN KEY (file, uid) REFERENCES reviewuserfiles ON DELETE CASCADE

);

CREATE INDEX reviewuserfilechanges_batch ON reviewuserfilechanges (batch);
CREATE INDEX reviewuserfilechanges_file ON reviewuserfilechanges (file);
CREATE INDEX reviewuserfilechanges_uid_state ON reviewuserfilechanges (uid, state);
CREATE INDEX reviewuserfilechanges_time ON reviewuserfilechanges (time);

CREATE TABLE lockedreviews (

  review INTEGER PRIMARY KEY REFERENCES reviews

);

CREATE TABLE reviewmessageids (

  uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  messageid CHAR(24) NOT NULL,

  PRIMARY KEY (uid, review)

);

CREATE INDEX reviewmessageids_review ON reviewmessageids (review);

CREATE TABLE reviewrecipientfilters (

  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  uid INTEGER REFERENCES users,
  include BOOLEAN NOT NULL,

  UNIQUE (review, uid)

);

CREATE TABLE checkbranchnotes (

  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  branch VARCHAR(256) NOT NULL,
  upstream VARCHAR(256) NOT NULL,
  sha1 CHAR(40) NOT NULL,
  uid INTEGER NOT NULL REFERENCES users,
  review INTEGER REFERENCES reviews ON DELETE SET NULL,
  text TEXT,

  PRIMARY KEY (repository, branch, upstream, sha1)

);

-- Rebase replay request:
--   One row per review rebase to replay.
CREATE TABLE rebasereplayrequests (

  -- The rebase being replayed.
  rebase INTEGER PRIMARY KEY REFERENCES reviewrebases ON DELETE CASCADE,
  -- The branch update. This duplicates the corresponding column in
  -- |reviewrebases| but is needed since the replay is requested before the
  -- column in |reviewrebases| is set to a non-NULL value.
  branchupdate INTEGER REFERENCES branchupdates ON DELETE CASCADE,
  -- New upstream. This duplicates the corresponding column in |reviewrebases|
  -- but is needed since the replay is sometimes requested before the column in
  -- |reviewrebases| is set to a non-NULL value.
  new_upstream INTEGER REFERENCES commits ON DELETE CASCADE,

  -- The commit produced by replaying or NULL if not replayed yet.
  replay INTEGER REFERENCES commits,
  -- A Python traceback, if replaying failed.  NULL otherwise.
  traceback TEXT,

  CHECK (replay IS NULL OR traceback IS NULL)

);

-- Available review tags:
--   One row per review tag.
CREATE TABLE reviewtags (

  -- The tag id.
  id SERIAL PRIMARY KEY,
  -- The tag name. A short unique name.
  name VARCHAR(64),
  -- Description of the tag.
  description TEXT,

  UNIQUE (name)

);

-- Calculated review tags:
--   One row per review, user and tag that applies.
--
-- Tags are typically calculated from other review state in the database, for
-- the purpose of speeding up queries.
CREATE TABLE reviewusertags (

  -- The tagged review.
  review INTEGER REFERENCES reviews ON DELETE CASCADE,
  -- The user for whom the tag is relevant.
  uid INTEGER REFERENCES users ON DELETE CASCADE,
  -- The tag.
  tag INTEGER REFERENCES reviewtags ON DELETE CASCADE,

  PRIMARY KEY (review, uid, tag),
  FOREIGN KEY (review, uid) REFERENCES reviewusers ON DELETE CASCADE

);

CREATE INDEX reviewusertags_uid
          ON reviewusertags (uid);

CREATE INDEX reviewusertags_tag
          ON reviewusertags (tag);

-- Review pings:
--   One row per sent review ping.
--
-- Pings are used by review owners (typically) to alert assigned reviewers of
-- pending (perhaps urgent) changes that need to be reviewed.
CREATE TABLE reviewpings (

  -- The corresponding review event of type 'pinged'.
  event INTEGER NOT NULL,
  -- The message sent.
  message TEXT NOT NULL,

  PRIMARY KEY (event),
  FOREIGN KEY (event) REFERENCES reviewevents ON DELETE CASCADE

);

CREATE TABLE reviewintegrationconflicts (

  review INTEGER NOT NULL,
  file INTEGER NOT NULL,

  PRIMARY KEY (review, file),
  FOREIGN KEY (review) REFERENCES reviews ON DELETE CASCADE,
  FOREIGN KEY (file) REFERENCES files

);

CREATE TYPE reviewintegrationstrategy AS ENUM (

  -- The changes were integrated by fast-forwarding the target branch.
  'fast-forward',
  -- The changes (a single commit) were integrated by cherry-picking the commit
  -- onto the target branch.
  'cherry-pick',
  -- The changes were integrated by rebasing the review branch onto the target
  -- branch and then fast-forwarding the target branch.
  'rebase',
  -- The changes were integrated by merging the review branch into the target
  -- branch. A merge commit will have been created, even if a fast-forward was
  -- possible. If fast-forwards are allowed and one was possible, the strategy
  -- used would have been `fast-forwarded`.
  'merge'

);

CREATE TABLE reviewintegrationrequests (

  id SERIAL,

  -- The review to integrate.
  review INTEGER NOT NULL,
  -- The branch to integrate into.
  target INTEGER NOT NULL,
  -- The most recent update of the review branch. Used to ensure that what is
  -- eventually integrated matches the state when the request was initially
  -- made. Note: This is updated if the integration process rebases the review
  -- or rewrites the history on the review branch.
  branchupdate INTEGER NOT NULL,

  -- If true, all changes on the review branch will be squashed into a single
  -- commit in a preliminary step.
  do_squash BOOLEAN NOT NULL,
  -- Commit message to use for the single commit, if `do_squash` is true.
  squash_message TEXT,

  -- If true, perform a `git rebase --autosquash` style in-place history rewrite
  -- in a preliminary step.
  do_autosquash BOOLEAN NOT NULL,

  -- If true, actually attempt the integration, If false, only the squash and
  -- autosquash steps will be performed.
  do_integrate BOOLEAN NOT NULL,

  -- State tracking:
  --   These columns are updated incrementally as the

  -- PRELIMINARY
  -- True if the changes on the review branch were squashed into a single
  -- commit. This is preliminary and is left in place even if the actual
  -- integration later were to fail.
  squashed BOOLEAN NOT NULL DEFAULT FALSE,
  -- True if the review branch's history has been rewritten to eliminate fixup!
  -- and squash! commits. This is preliminary and is left in place even if the
  -- actual integration later were to fail.
  autosquashed BOOLEAN NOT NULL DEFAULT FALSE,

  -- FINAL
  -- The integration strategy eventually used/attempted.
  strategy_used reviewintegrationstrategy,
  -- True if the attempt to integrate the changes was successful, and false if
  -- they it failed. If false, `error_message` will contain a description of the
  -- failure.
  successful BOOLEAN,
  -- Error message, if `failed` is true.
  error_message TEXT,

  PRIMARY KEY (id),
  FOREIGN KEY (review) REFERENCES reviews ON DELETE CASCADE,
  FOREIGN KEY (target) REFERENCES branches ON DELETE CASCADE,
  FOREIGN KEY (branchupdate) REFERENCES branchupdates

);
CREATE UNIQUE INDEX reviewintegrationrequests_review
                 ON reviewintegrationrequests (review)
              WHERE strategy_used IS NULL;
