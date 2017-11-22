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

CREATE TABLE repositories (

  id SERIAL PRIMARY KEY,
  parent INTEGER REFERENCES repositories,
  name VARCHAR(64) NOT NULL UNIQUE,
  path VARCHAR(256) NOT NULL UNIQUE,
  ready BOOLEAN NOT NULL DEFAULT FALSE

);

CREATE TABLE gitusers (

  id SERIAL PRIMARY KEY,
  email VARCHAR(256) NOT NULL,
  fullname VARCHAR(256) NOT NULL,

  UNIQUE (email, fullname)

);

CREATE TABLE commits (

  id SERIAL PRIMARY KEY,
  sha1 CHAR(40) NOT NULL UNIQUE,
  author_gituser INTEGER NOT NULL REFERENCES gitusers,
  commit_gituser INTEGER NOT NULL REFERENCES gitusers,
  author_time TIMESTAMP NOT NULL,
  commit_time TIMESTAMP NOT NULL

);

CREATE TABLE edges (

  parent INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE,
  child INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE

);
CREATE INDEX edges_parent ON edges (parent);
CREATE INDEX edges_child ON edges (child);

CREATE TYPE branchtype AS ENUM (

  'normal',
  'review'

);
CREATE TABLE branches (

  id SERIAL PRIMARY KEY,
  name VARCHAR(256) NOT NULL,
  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  head INTEGER NOT NULL REFERENCES commits,
  base INTEGER REFERENCES branches ON DELETE SET NULL,
  type branchtype NOT NULL DEFAULT 'normal',
  archived BOOLEAN NOT NULL DEFAULT FALSE,

  -- The |merged| flag is set when the branch's |head| commit is associated
  -- with another branch. The flag is cleared when the branch's |head| is
  -- updated to a commit that is not already associated with another branch.
  --
  -- Exception: a branch with a NULL |base| will never be flagged as merged.
  merged BOOLEAN NOT NULL DEFAULT FALSE,
  -- The number of commits associated with the branch. This is only stored as
  -- an optimization; counting rows in the |branchcommits| will give the same
  -- result.
  size INTEGER NOT NULL,

  UNIQUE (repository, name)

);
CREATE INDEX branches_base
          ON branches (base);

-- Branch updates:
--   One row per update (ff or not) of a branch.
CREATE TABLE branchupdates (

  id SERIAL PRIMARY KEY,

  -- The branch that was updated.
  branch INTEGER NOT NULL REFERENCES branches ON DELETE CASCADE,
  -- User that performed the update.  NULL means the update was performed by
  -- the system (e.g. the branch tracker) rather than by a user.
  updater INTEGER REFERENCES users,
  -- Previous value of |branches.head|.  NULL means the branch was created.
  from_head INTEGER REFERENCES commits,
  -- New value of |branches.head|.
  to_head INTEGER NOT NULL REFERENCES commits,
  -- Previous value of |branches.base|.
  from_base INTEGER REFERENCES branches ON DELETE SET NULL,
  -- New value of |branches.base|.
  to_base INTEGER REFERENCES branches ON DELETE SET NULL,
  -- When the update was performed.
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  -- Output, displayed in logs and also echoed by the post-receive hook if the
  -- update is performed via Git.
  output TEXT

);
CREATE INDEX branchupdates_branch_to_from
          ON branchupdates (branch, to_head, from_head);
CREATE INDEX branchupdates_from_base
          ON branchupdates (from_base);
CREATE INDEX branchupdates_to_base
          ON branchupdates (to_base);

-- Branch merges:
--   One row per branch update that caused one branch to be merged into another.
CREATE TABLE branchmerges (

  id SERIAL PRIMARY KEY,

  -- The branch being merged (whose |branches.merged| flag was set).
  branch INTEGER NOT NULL REFERENCES branches ON DELETE CASCADE,
  -- The branch update (of the branch into which the branch was merged) that
  -- caused the flag to be set.
  branchupdate INTEGER NOT NULL REFERENCES branchupdates ON DELETE CASCADE,

  UNIQUE (branch, branchupdate)

);

-- Branch commits:
--   One row per commit associated with a branch.
--
-- Note that this does not (typically) mean "all reachable commits",
-- since then most commits would be associated with most branches in a
-- repository with a long history.
CREATE TABLE branchcommits (

  branch INTEGER NOT NULL REFERENCES branches ON DELETE CASCADE,
  commit INTEGER NOT NULL REFERENCES commits,

  PRIMARY KEY (branch, commit)

);
CREATE INDEX branchcommits_commit
          ON branchcommits (commit);

-- Branch update commits:
--   One row per commit (dis)associated with a branch by an update.
--
-- This table documents the changes to the |branchcommits| table by each branch
-- update.
CREATE TABLE branchupdatecommits (

  branchupdate INTEGER NOT NULL REFERENCES branchupdates ON DELETE CASCADE,
  commit INTEGER NOT NULL REFERENCES commits,
  associated BOOLEAN NOT NULL,

  PRIMARY KEY (branchupdate, commit)

);

CREATE TABLE tags (

  id SERIAL PRIMARY KEY,
  name VARCHAR(256) NOT NULL,
  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  sha1 CHAR(40) NOT NULL,

  UNIQUE (repository, name)

);
CREATE INDEX tags_repository_sha1
          ON tags (repository, sha1);

-- Cached result of 'git merge-base <all parents>' for commits.
CREATE TABLE mergebases (

  commit INTEGER PRIMARY KEY REFERENCES commits ON DELETE CASCADE,
  mergebase CHAR(40)

);

-- Cached per-file-and-parent "relevant" commits, for a merge commit.
--
-- Each row says that for the merge commit |commit|'s |parent|th parent and the
-- file |file|, |relevant| is a commit between the merge-base and the merge that
-- also modifies the file, and that isn't an ancestor of that parent.
CREATE TABLE relevantcommits (

  commit INTEGER REFERENCES commits ON DELETE CASCADE,
  parent SMALLINT NOT NULL,
  file INTEGER REFERENCES files,
  relevant INTEGER REFERENCES commits ON DELETE CASCADE,

  PRIMARY KEY (commit, parent, file, relevant)

);

CREATE TYPE repositoryaccesstype AS ENUM (

  'read',
  'modify'

);

CREATE TABLE accesscontrol_repositories (

  id SERIAL PRIMARY KEY,

  -- The profile this exception belongs to.
  profile INTEGER NOT NULL REFERENCES accesscontrolprofiles ON DELETE CASCADE,

  -- Type of access.  NULL means "any type".
  access_type repositoryaccesstype,
  -- Repository to access.  NULL means "any repository".
  repository INTEGER REFERENCES repositories ON DELETE CASCADE

);
CREATE INDEX accesscontrol_repositories_profile
          ON accesscontrol_repositories (profile);

CREATE TYPE pendingrefupdatestate AS ENUM (

  -- Update has been approved by the pre-receive hook.  The ref in the Git
  -- repository may or may not have been updated, and may never be.
  'preliminary',
  -- Update has been processed by the branchupdater service, but was of a
  -- review branch and has yet to be processed by the reviewupdater service.
  'processed',
  -- Update has been processed by the branchupdater service, and the
  -- reviewupdater service if it was of a review branch.  Any output from the
  -- processing has been recorded in |pendingrefupdateoutputs| by this time.
  'finished',
  -- Update has been handled, but the handling failed due to an implementation
  -- error.
  'failed'

);

-- Pending ref updates:
--   One row per pending update, deleted once fully processed.
--
-- This table stores raw SHA-1 sums instead of commit ids so that rows can be
-- inserted into it without first recording commits into the 'commits' table.
-- The recording of commits can be costly, so we prefer to do that in the
-- background instead of directly from the pre-receive hook.
CREATE TABLE pendingrefupdates (

  id SERIAL PRIMARY KEY,

  -- User that is responsible for the update, or NULL if the system is
  -- performing the update.
  updater INTEGER REFERENCES users,
  -- Repository being updated.
  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  -- Name of ref being updated.  This includes the "refs/.../" prefix (the ref
  -- being updated might not be a branch.)
  name VARCHAR(256) NOT NULL,
  -- Old value (SHA-1).  All zeroes means ref was created.
  old_sha1 CHAR(40) NOT NULL,
  -- New vaule (SHA-1).  All zeroes means ref was deleted.
  new_sha1 CHAR(40) NOT NULL,
  -- JSON encoded flags received from the Git hook.
  flags JSON,
  -- State of the update.
  state pendingrefupdatestate NOT NULL DEFAULT 'preliminary',
  -- Timestamp.  Used to time out preliminary updates, for which the
  -- post-receive hook was seemingly never called.
  started_at TIMESTAMP NOT NULL DEFAULT NOW(),
  -- Timestamp.  Used to clean up / revert finished and failed updates.
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  -- True if the post-receive hook has stopped waiting for the update to be
  -- processed.  Updates in this state are cleaned up by the branchupdate
  -- service, and the user notified by email in case of failure.
  abandoned BOOLEAN NOT NULL DEFAULT FALSE,
  -- Branch update record.  Is deleted when cleaning up the pending ref update
  -- in case of failure.
  branchupdate INTEGER REFERENCES branchupdates ON DELETE SET NULL

);

CREATE INDEX pendingrefupdates_repository_name
          ON pendingrefupdates (repository, name);
CREATE INDEX pendingrefupdates_branchupdate
          ON pendingrefupdates (branchupdate);

-- Output associated with pending ref updates:
--   Zero or more rows per pending update, deleted along with the pending ref
--   update itself.
CREATE TABLE pendingrefupdateoutputs (

  id SERIAL PRIMARY KEY,

  pendingrefupdate INTEGER NOT NULL REFERENCES pendingrefupdates ON DELETE CASCADE,
  output TEXT NOT NULL

);

CREATE INDEX pendingrefupdateoutputs_pendingrefupdate
          ON pendingrefupdateoutputs (pendingrefupdate);

CREATE TABLE repositorysettings (

  -- Unique id.
  id SERIAL PRIMARY KEY,

  -- Repository.
  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  -- Setting scope, e.g. "integration".
  scope VARCHAR(64) NOT NULL,
  -- Setting name.
  name VARCHAR(256) NOT NULL,
  -- Setting value. Stored JSON encoded.
  value JSON NOT NULL,

  UNIQUE (repository, scope, name)

);

CREATE TABLE branchsettings (

  -- Unique id.
  id SERIAL PRIMARY KEY,

  -- Repository.
  branch INTEGER NOT NULL REFERENCES branches,
  -- Setting scope, e.g. "integration".
  scope VARCHAR(64) NOT NULL,
  -- Setting name.
  name VARCHAR(256) NOT NULL,
  -- Setting value. Stored JSON encoded.
  value JSON NOT NULL,

  UNIQUE (branch, scope, name)

);
