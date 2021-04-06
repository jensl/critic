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

CREATE TYPE commenttype AS ENUM (
  'issue',  -- The comment comment, while open, blocks the review.
  'note'    -- The comment comment doesn't block the review.
);
CREATE TYPE issuestate AS ENUM (
  'open',     -- The comment comment is open.
  'addressed',-- The commented code was changed by a later commit.
  'resolved'  -- The comment comment is resolved.
);
CREATE TYPE commentside AS ENUM (
  'old',  -- The user commented the old/left-hand side in a diff.
  'new'   -- The user commented the new/right-hand side in a diff.
);

CREATE TABLE comments (
  id SERIAL PRIMARY KEY,

  type commenttype NOT NULL,
  review INTEGER NOT NULL REFERENCES reviews ON DELETE CASCADE,
  batch INTEGER REFERENCES batches ON DELETE CASCADE,
  author INTEGER NOT NULL REFERENCES users,
  text TEXT NOT NULL,
  time TIMESTAMP NOT NULL DEFAULT NOW(),

  -- Location
  side commentside,
  file INTEGER REFERENCES files,
  first_commit INTEGER REFERENCES commits,
  last_commit INTEGER REFERENCES commits,

  -- State (issues only)
  issue_state issuestate NOT NULL DEFAULT 'open',
  closed_by INTEGER REFERENCES users,
  addressed_by INTEGER REFERENCES commits,
  addressed_by_update INTEGER REFERENCES branchupdates
);
CREATE INDEX comments_review_file
          ON comments(review, file);
CREATE INDEX comments_review_type_state
          ON comments(review, type, issue_state);
CREATE INDEX comments_batch
          ON comments(batch);

-- FIXME: This circular relation is unnecessary.  Should have a separate table
-- for mapping batches to comments intead.
ALTER TABLE batches ADD CONSTRAINT batches_comment_fkey FOREIGN KEY (comment) REFERENCES comments ON DELETE CASCADE;

CREATE TYPE commentchangestate AS ENUM
  ( 'draft',     -- This change hasn't been performed yet.
    'performed', -- The change has been performed.
    'rejected'   -- The change was rejected; affected comment comment wasn't in
                 -- expected state.
  );
CREATE TABLE commentchanges
  ( batch INTEGER REFERENCES batches ON DELETE CASCADE,
    author INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
    comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,
    time TIMESTAMP NOT NULL DEFAULT NOW(),
    state commentchangestate NOT NULL DEFAULT 'draft',
    from_type commenttype,
    to_type commenttype,
    from_state issuestate,
    to_state issuestate,
    from_last_commit INTEGER REFERENCES commits,
    to_last_commit INTEGER REFERENCES commits,
    from_addressed_by INTEGER REFERENCES commits,
    to_addressed_by INTEGER REFERENCES commits );
CREATE INDEX commentchanges_batch ON commentchanges(batch);
CREATE INDEX commentchanges_comment ON commentchanges(comment);

CREATE VIEW effectivecomments (review, comment, author, type, state ) AS
     SELECT cc.review, ccc.comment, ccc.author,
            CASE WHEN ccc.from_type=cc.type THEN ccc.from_type
                 ELSE cc.type
            END,
            CASE WHEN ccc.from_state=cc.issue_state THEN ccc.to_state
                 ELSE cc.issue_state
            END
       FROM comments AS cc
       JOIN commentchanges AS ccc ON (ccc.comment=cc.id)
      WHERE ccc.state='draft';

CREATE TYPE commentlinesstate AS ENUM
  ( 'draft',
    'current'
  );

CREATE TABLE commentlines
  ( comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,
    author INTEGER REFERENCES users,
    time TIMESTAMP NOT NULL DEFAULT NOW(),
    state commentlinesstate NOT NULL DEFAULT 'draft',
    sha1 CHAR(40) NOT NULL,
    first_line INTEGER NOT NULL,
    last_line INTEGER NOT NULL,

    -- This UNIQUE constraint is a bit fishy; it means two different users
    -- can't have a draft "reopening" of the comment at the same time,
    -- which strictly speaking wouldn't necessarily be a problem.
    UNIQUE (comment, sha1) );
CREATE INDEX commentlines_comment_sha1 ON commentlines(comment, sha1);

CREATE TABLE commentusers
  ( comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,
    author INTEGER NOT NULL REFERENCES users,

    PRIMARY KEY (comment, author) );

CREATE TABLE replies (
  id SERIAL PRIMARY KEY,

  comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,
  batch INTEGER REFERENCES batches ON DELETE CASCADE,
  author INTEGER NOT NULL REFERENCES users,
  text TEXT NOT NULL,
  time TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX replies_comment_author ON replies (comment, author);
CREATE INDEX replies_batch ON replies(batch);
CREATE INDEX replies_id_comment ON replies(id, comment);

-- CREATE TABLE commentstoread (
--   author INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
--   comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,

--   PRIMARY KEY (author, comment)
-- );
-- CREATE INDEX commentstoread_comment ON commentstoread(comment);

-- CREATE TABLE commentmessageids (
--   author INTEGER NOT NULL REFERENCES users ON DELETE CASCADE,
--   comment INTEGER NOT NULL REFERENCES comments ON DELETE CASCADE,
--   messageid CHAR(24) NOT NULL,

--   PRIMARY KEY (author, comment)
-- );
-- CREATE INDEX commentmessageids_comment ON commentmessageids(comment);

-- CREATE TABLE commenttextbackups (
--   id SERIAL PRIMARY KEY,

--   author INTEGER NOT NULL,
--   comment INTEGER NOT NULL,
--   reply INTEGER,

--   value TEXT NOT NULL,
--   timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

--   FOREIGN KEY (author) REFERENCES users ON DELETE CASCADE,
--   FOREIGN KEY (comment) REFERENCES comments ON DELETE CASCADE,
--   FOREIGN KEY (reply) REFERENCES comments ON DELETE CASCADE
-- );
-- CREATE UNIQUE INDEX commenttextbackups_author_comment
--                  ON commenttextbackups (author, comment);
