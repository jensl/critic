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
    filter INTEGER REFERENCES repositoryfilters ON DELETE CASCADE,

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
