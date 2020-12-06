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

CREATE TYPE commentchaintype AS ENUM (
  'issue',  -- The comment chain, while open, blocks the review.
  'note'    -- The comment chain doesn't block the review.
);
CREATE TYPE commentchainstate AS ENUM (
  'open',     -- The comment chain is open.
  'addressed',-- The commented code was changed by a later commit.
  'closed',   -- The comment chain is closed.
  'empty'     -- The comment chain has no comments.
);
CREATE TYPE commentchainorigin AS ENUM (
  'old',  -- The user commented the old/left-hand side in a diff.
  'new'   -- The user commented the new/right-hand side in a diff.
);

CREATE TABLE commentchains (
  id SERIAL PRIMARY KEY,

  type commentchaintype NOT NULL DEFAULT 'issue',
  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  batch INTEGER REFERENCES batches ON DELETE CASCADE,
  uid INTEGER NOT NULL REFERENCES users,
  text TEXT NOT NULL,
  time TIMESTAMP NOT NULL DEFAULT NOW(),

  -- Location
  origin commentchainorigin,
  file INTEGER REFERENCES files,
  first_commit INTEGER REFERENCES commits,
  last_commit INTEGER REFERENCES commits,

  -- State
  state commentchainstate NOT NULL DEFAULT 'open',
  closed_by INTEGER REFERENCES users,
  addressed_by INTEGER REFERENCES commits,
  addressed_by_update INTEGER REFERENCES branchupdates
);
CREATE INDEX commentchains_review_file
          ON commentchains(review, file);
CREATE INDEX commentchains_review_type_state
          ON commentchains(review, type, state);
CREATE INDEX commentchains_batch
          ON commentchains(batch);

-- FIXME: This circular relation is unnecessary.  Should have a separate table
-- for mapping batches to comments intead.
ALTER TABLE batches ADD CONSTRAINT batches_comment_fkey FOREIGN KEY (comment) REFERENCES commentchains ON DELETE CASCADE;

CREATE TYPE commentchainchangestate AS ENUM
  ( 'draft',     -- This change hasn't been performed yet.
    'performed', -- The change has been performed.
    'rejected'   -- The change was rejected; affected comment chain wasn't in
                 -- expected state.
  );
CREATE TABLE commentchainchanges
  ( batch INTEGER REFERENCES batches ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    chain INTEGER NOT NULL REFERENCES commentchains ON DELETE CASCADE,
    time TIMESTAMP NOT NULL DEFAULT NOW(),
    state commentchainchangestate NOT NULL DEFAULT 'draft',
    from_type commentchaintype,
    to_type commentchaintype,
    from_state commentchainstate,
    to_state commentchainstate,
    from_last_commit INTEGER REFERENCES commits,
    to_last_commit INTEGER REFERENCES commits,
    from_addressed_by INTEGER REFERENCES commits,
    to_addressed_by INTEGER REFERENCES commits );
CREATE INDEX commentchainchanges_batch ON commentchainchanges(batch);
CREATE INDEX commentchainchanges_chain ON commentchainchanges(chain);

CREATE VIEW effectivecommentchains (review, chain, uid, type, state ) AS
     SELECT cc.review, ccc.chain, ccc.uid,
            CASE WHEN ccc.from_type=cc.type THEN ccc.from_type
                 ELSE cc.type
            END,
            CASE WHEN ccc.from_state=cc.state THEN ccc.to_state
                 ELSE cc.state
            END
       FROM commentchains AS cc
       JOIN commentchainchanges AS ccc ON (ccc.chain=cc.id)
      WHERE ccc.state='draft';

CREATE TYPE commentchainlinesstate AS ENUM
  ( 'draft',
    'current'
  );

CREATE TABLE commentchainlines
  ( chain INTEGER NOT NULL REFERENCES commentchains ON DELETE CASCADE,
    uid INTEGER REFERENCES users,
    time TIMESTAMP NOT NULL DEFAULT NOW(),
    state commentchainlinesstate NOT NULL DEFAULT 'draft',
    sha1 CHAR(40) NOT NULL,
    first_line INTEGER NOT NULL,
    last_line INTEGER NOT NULL,

    -- This UNIQUE constraint is a bit fishy; it means two different users
    -- can't have a draft "reopening" of the commentchain at the same time,
    -- which strictly speaking wouldn't necessarily be a problem.
    UNIQUE (chain, sha1) );
CREATE INDEX commentchainlines_chain_sha1 ON commentchainlines(chain, sha1);

CREATE TABLE commentchainusers
  ( chain INTEGER NOT NULL REFERENCES commentchains ON DELETE CASCADE,
    uid INTEGER NOT NULL REFERENCES users,

    PRIMARY KEY (chain, uid) );

CREATE TABLE comments (
  id SERIAL PRIMARY KEY,

  chain INTEGER NOT NULL REFERENCES commentchains ON DELETE CASCADE,
  batch INTEGER REFERENCES batches ON DELETE CASCADE,
  uid INTEGER NOT NULL REFERENCES users,
  text TEXT NOT NULL,
  time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX comments_chain_uid ON comments (chain, uid);
CREATE INDEX comments_batch ON comments(batch);
CREATE INDEX comments_id_chain ON comments(id, chain);

CREATE TABLE commentstoread (
  uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
  comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,

  PRIMARY KEY (uid, comment)
);
CREATE INDEX commentstoread_comment ON commentstoread(comment);

CREATE TABLE commentmessageids (
  uid INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
  comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,
  messageid CHAR(24) NOT NULL,

  PRIMARY KEY (uid, comment)
);
CREATE INDEX commentmessageids_comment ON commentmessageids(comment);

CREATE TABLE commenttextbackups (
  id SERIAL PRIMARY KEY,

  uid INTEGER NOT NULL,
  comment INTEGER NOT NULL,
  reply INTEGER,

  value TEXT NOT NULL,
  timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

  FOREIGN KEY (uid) REFERENCES users ON DELETE CASCADE,
  FOREIGN KEY (comment) REFERENCES commentchains ON DELETE CASCADE,
  FOREIGN KEY (reply) REFERENCES comments ON DELETE CASCADE
);
CREATE UNIQUE INDEX commenttextbackups_uid_comment
                 ON commenttextbackups (uid, comment);
