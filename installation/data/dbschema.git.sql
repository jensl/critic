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

CREATE TABLE repositories
  ( id SERIAL PRIMARY KEY,
    parent INTEGER REFERENCES repositories,
    name VARCHAR(64) NOT NULL UNIQUE,
    path VARCHAR(256) NOT NULL UNIQUE );

CREATE TABLE gitusers
  ( id SERIAL PRIMARY KEY,
    email VARCHAR(256) NOT NULL,
    fullname VARCHAR(256) NOT NULL,

    UNIQUE (email, fullname) );

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
    archived BOOLEAN NOT NULL DEFAULT FALSE,

    UNIQUE (repository, name) );

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

-- Cached result of 'git merge-base <all parents>' for commits.
CREATE TABLE mergebases
  ( commit INTEGER PRIMARY KEY REFERENCES commits ON DELETE CASCADE,
    mergebase CHAR(40) );

-- Cached per-file-and-parent "relevant" commits, for a merge commit.
--
-- Each row says that for the merge commit |commit|'s |parent|th parent and the
-- file |file|, |relevant| is a commit between the merge-base and the merge that
-- also modifies the file, and that isn't an ancestor of that parent.
CREATE TABLE relevantcommits
  ( commit INTEGER REFERENCES commits ON DELETE CASCADE,
    parent SMALLINT NOT NULL,
    file INTEGER REFERENCES files,
    relevant INTEGER REFERENCES commits ON DELETE CASCADE,

    PRIMARY KEY (commit, parent, file, relevant) );

CREATE TYPE repositoryaccesstype AS ENUM
  ( 'read',
    'modify' );

CREATE TABLE accesscontrol_repositories
  ( id SERIAL PRIMARY KEY,

    -- The profile this exception belongs to.
    profile INTEGER NOT NULL REFERENCES accesscontrolprofiles ON DELETE CASCADE,

    -- Type of access.  NULL means "any type".
    access_type repositoryaccesstype,
    -- Repository to access.  NULL means "any repository".
    repository INTEGER REFERENCES repositories ON DELETE CASCADE );
CREATE INDEX accesscontrol_repositories_profile
          ON accesscontrol_repositories (profile);
