# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import grp
import json
import logging
import os
import pwd
import subprocess
import sys

logger = logging.getLogger(__name__)

from critic import api
from critic import base

index = 0
title = "Convert legacy (pre-2.0) Critic system."
scope = {"database"}


def update_git_sql(arguments, schema_helper):
    from .. import serialize_legacy_configuration

    legacy_configuration = serialize_legacy_configuration(arguments)
    git_dir = legacy_configuration["paths.git_dir"]

    cursor = schema_helper.database.cursor()
    cursor.execute("SELECT id, path FROM repositories")

    repository_paths = list(cursor)

    schema_helper.add_column("repositories", "ready", "BOOLEAN NOT NULL DEFAULT FALSE")
    # All current repositories are assumed to be ready. The ready column is only
    # needed now since creation becomes asynchronous as of this upgrade.
    schema_helper.execute("UPDATE repositories SET ready=TRUE")
    schema_helper.executemany(
        """UPDATE repositories
              SET path=%s
            WHERE id=%s""",
        [
            (os.path.relpath(path, git_dir), repository_id)
            for repository_id, path in repository_paths
        ],
    )
    schema_helper.commit()

    schema_helper.add_column("branches", "merged", "BOOLEAN NOT NULL DEFAULT FALSE")
    # Mark all branches as merged whose head commit is associated with its base
    # branch. This is not 100 % accurate, but the |merged| column is not
    # intended to be.
    schema_helper.execute(
        """UPDATE branches
              SET merged=TRUE
            WHERE base IS NOT NULL
              AND head IN (
                    SELECT commit
                      FROM branchcommits
                     WHERE branch=base
                  )"""
    )
    schema_helper.commit()

    schema_helper.add_column("branches", "size", "INTEGER")
    schema_helper.execute(
        """UPDATE branches
              SET size=(
                    SELECT COUNT(*)
                      FROM branchcommits
                     WHERE branchcommits.branch=branches.id
                  )"""
    )
    schema_helper.commit()
    schema_helper.alter_column("branches", "size", not_null=True)

    schema_helper.update(
        """

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

"""
    )

    # Insert "branch merge" records for each case where we set |branches.merged|
    # to TRUE above.
    schema_helper.execute(
        """INSERT
             INTO branchmerges (branch, branchupdate)
           SELECT merged.id, branchupdatecommits.branchupdate
             FROM branches AS merged
             JOIN branches AS bases ON (bases.id=merged.base)
             JOIN branchupdates ON (branchupdates.branch=bases.id)
             JOIN branchupdatecommits ON (
                    branchupdatecommits.branchupdate=branchupdates.id AND
                    branchupdatecommits.commit=merged.head
                  )
            WHERE branchupdatecommits.associated"""
    )
    schema_helper.commit()


def update_reviews_sql(schema_helper):
    cursor = schema_helper.database.cursor()

    schema_helper.add_column("reviews", "repository", "INTEGER REFERENCES repositories")
    schema_helper.execute(
        """UPDATE reviews
              SET repository=branches.repository
             FROM branches
            WHERE reviews.branch=branches.id"""
    )
    # The |reviews.branch| column is NOT NULL in a legacy database, so
    # setting |reviews.repository| to NOT NULL is safe.
    schema_helper.alter_column("reviews", "repository", not_null=True)
    # In a modern database, OTOH, the |reviews.branch| column should not be
    # NOT NULL.
    schema_helper.alter_column("reviews", "branch", not_null=False)

    schema_helper.drop_column("reviews", "type")
    schema_helper.drop_type("reviewtype")

    schema_helper.alter_column("reviews", "state", default="'draft'")
    schema_helper.alter_column("reviews", "applyfilters", default="TRUE")
    schema_helper.alter_column("reviews", "applyparentfilters", default=True)

    schema_helper.update(
        """

CREATE TYPE revieweventtype AS ENUM (
  'created',
  'published',
  'closed',
  'dropped',
  'reopened',
  'pinged',
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

"""
    )

    schema_helper.add_column(
        "batches", "event", "INTEGER REFERENCES reviewevents ON DELETE CASCADE"
    )
    # Temporary column mapping from created rows in |reviewevents| back to the
    # row in |batches|.
    schema_helper.add_column("reviewevents", "temporary_batch", "INTEGER")

    cursor.execute(
        """INSERT
             INTO reviewevents (review, uid, type, processed, time,
                                temporary_batch)
           SELECT review, uid, 'batch', TRUE, time, id
             FROM batches"""
    )
    cursor.execute(
        """UPDATE batches
              SET event=reviewevents.id
             FROM reviewevents
            WHERE temporary_batch=batches.id"""
    )

    schema_helper.alter_column("batches", "event", not_null=True)
    schema_helper.drop_column("reviewevents", "temporary_batch")
    schema_helper.drop_index("batches_review_uid")
    schema_helper.drop_column("batches", "review")
    schema_helper.drop_column("batches", "uid")
    schema_helper.drop_column("batches", "time")
    schema_helper.create_index(
        """

CREATE INDEX batches_event
          ON batches (event);

"""
    )

    schema_helper.add_column(
        "reviewupdates", "event", "INTEGER REFERENCES reviewevents ON DELETE CASCADE"
    )
    # Temporary column mapping from created rows in |reviewevents| back to the
    # row in |reviewupdates|.
    schema_helper.add_column("reviewevents", "temporary_reviewupdate", "INTEGER")

    cursor.execute(
        """INSERT
             INTO reviewevents (review, uid, type, processed, time,
                                temporary_reviewupdate)
           SELECT review, updater, 'branchupdate', TRUE, updated_at, id
             FROM reviewupdates
             JOIN branchupdates ON (id=branchupdate)"""
    )
    cursor.execute(
        """UPDATE reviewupdates
              SET event=reviewevents.id
             FROM reviewevents
            WHERE temporary_reviewupdate=branchupdate"""
    )

    schema_helper.alter_column("reviewupdates", "event", not_null=True)
    schema_helper.drop_column("reviewevents", "temporary_reviewupdate")
    schema_helper.drop_index("reviewupdates_review")
    schema_helper.drop_column("reviewupdates", "review")
    schema_helper.drop_column("reviewupdates", "output")
    schema_helper.create_index(
        """

CREATE INDEX reviewupdates_event
          ON reviewupdates (event);

"""
    )

    schema_helper.update(
        """

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

"""
    )

    # Add rows to |reviewcommits| for corresponding rows in |reviewchangesets|.
    # They effectively mirror each other; |reviewcommits| was added so that
    # commits could be added before having changesets for them, effectively.
    #
    # But notably don't add rows for equivalent merge commits or replayed
    # rebases, as those are not counted as "real" commits in the review. They
    # are only referenced from the |reviewrebases| table.
    schema_helper.execute(
        """INSERT
             INTO reviewcommits (review, branchupdate, commit)
           SELECT DISTINCT reviewchangesets.review,
                           reviewchangesets.branchupdate,
                           changesets.child
             FROM reviewchangesets
             JOIN changesets ON (changesets.id=reviewchangesets.changeset)
  LEFT OUTER JOIN reviewrebases ON (
                    reviewrebases.review=reviewchangesets.review AND (
                      reviewrebases.equivalent_merge=changesets.child OR
                      reviewrebases.replayed_rebase=changesets.parent
                    )
                  )
            WHERE reviewrebases.id IS NULL"""
    )

    schema_helper.create_index(
        """

CREATE INDEX reviewrebases_branchupdate
          ON reviewrebases (branchupdate);

"""
    )

    schema_helper.update(
        """

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

"""
    )


async def convert_legacy_configuration(critic, arguments, schema_helper):
    from .. import serialize_legacy_configuration
    from ...install import insert_systemsettings

    legacy_settings_dir = os.path.join(arguments.etc_dir, arguments.identity)
    legacy_configuration = serialize_legacy_configuration(arguments)

    smtp_username = smtp_password = None
    try:
        legacy_smtp_credentials = os.path.join(
            legacy_settings_dir, "configuration", "smtp-credentials.json"
        )
        with open(legacy_smtp_credentials, "r", encoding="utf-8") as file:
            smtp_credentials = json.load(file)
        smtp_username = smtp_credentials.get("username")
        smtp_password = smtp_credentials.get("password")
    except (OSError, ValueError):
        pass

    accepted_schemes = ["argon2"]
    accepted_schemes.extend(legacy_configuration["auth.password_hash_schemes"])

    legacy_databases = legacy_configuration["auth.databases"]
    databases_internal_enabled = databases_ldap_enabled = False
    if "internal" in legacy_databases:
        # Note: It never accepted any configuration, and doesn't now either. No
        #       point in converting any existing values.
        databases_internal_enabled = True
        del legacy_databases["internal"]
    if "ldap" in legacy_databases:
        databases_ldap_enabled = True
        ldap_database = legacy_databases.pop("ldap")
        ldap_database["fields"] = [
            {
                "identifier": field[1],
                "label": field[2],
                "is_password": field[0],
                "description": field[3] if len(field) > 3 else None,
            }
            for field in ldap_database["fields"]
        ]
    for name in legacy_databases.keys():
        logger.warning("%s: not importing unknown authentication database", name)

    legacy_providers = legacy_configuration["auth.providers"]
    external_providers = {}
    if "github" in legacy_providers:
        external_providers["github"] = legacy_providers.pop("github")
    if "google" in legacy_providers:
        external_providers["google"] = legacy_providers.pop("google")
    for name in legacy_providers.keys():
        logger.warning(
            "%s: not importing unknown external authentication provider", name
        )

    legacy_flavors = legacy_configuration["extensions.flavors"]
    extension_flavors = {}
    default_flavor = None
    if "js/v8" in legacy_flavors:
        legacy_v8 = legacy_flavors.pop("js/v8")
        if os.access(legacy_v8["executable"], os.X_OK):
            executable = legacy_v8["executable"]
        else:
            executable = None
        extension_flavors["js/v8"] = {
            "enabled": executable is not None,
            "executable": executable,
            "library": "js/v8",
        }
        if legacy_configuration["extensions.default_flavor"] == "js/v8":
            default_flavor = "js/v8"
    for name in legacy_flavors.keys():
        logger.warning("%s: not importing unknown extension flavor", name)

    insert_systemsettings(
        schema_helper.database,
        arguments,
        {
            "system.hostname": legacy_configuration["base.hostname"],
            "system.email": legacy_configuration["base.system_user_email"],
            "system.recipients": legacy_configuration["base.system_recipients"],
            "system.is_development": legacy_configuration["debug.is_development"],
            # Note: Whatever the legacy executables.PYTHON configuration was, it
            # will be wrong now.
            # "executables.python": sys.executable,
            # "executables.git": legacy_configuration["executables.git"],
            # "executables.git_environment":
            #     legacy_configuration["executables.git_env"],
            # "executables.tar": legacy_configuration["executables.tar"],
            "frontend.authentication_mode": legacy_configuration[
                "base.authentication_mode"
            ],
            "frontend.session_type": legacy_configuration["base.session_type"],
            "frontend.session_max_age": legacy_configuration["base.session_max_age"]
            or None,
            "frontend.access_scheme": legacy_configuration["base.access_scheme"],
            # Note: Skip auth.MINIMUM_ROUNDS, since we've most likely switched
            #       hashing scheme, and the old value thus might be wildly wrong.
            "authentication.databases.internal.enabled": databases_internal_enabled,
            "authentication.databases.internal.accepted_schemes": accepted_schemes,
            "authentication.databases.internal.used_scheme": "argon2",
            "authentication.databases.ldap.enabled": databases_ldap_enabled,
            "authentication.databases.ldap.settings.url": ldap_database["url"],
            "authentication.databases.ldap.settings.use_tls": ldap_database["use_tls"],
            "authentication.databases.ldap.settings.credentials_field": ldap_database[
                "credentials"
            ],
            "authentication.databases.ldap.settings.search_base": ldap_database[
                "search_base"
            ],
            "authentication.databases.ldap.settings.search_filter": ldap_database[
                "search_filter"
            ],
            "authentication.databases.ldap.settings.create_user": ldap_database[
                "create_user"
            ],
            "authentication.databases.ldap.settings.username_attribute": ldap_database[
                "username_attribute"
            ],
            "authentication.databases.ldap.settings.fullname_attribute": ldap_database[
                "fullname_attribute"
            ],
            "authentication.databases.ldap.settings.email_attribute": ldap_database[
                "email_attribute"
            ],
            "authentication.databases.ldap.settings.required_groups": ldap_database[
                "require_groups"
            ],
            "authentication.databases.ldap.settings.cache_max_age": ldap_database[
                "cache_max_age"
            ],
            "authentication.used_database": legacy_configuration["auth.database"],
            "authentication.enable_access_tokens": legacy_configuration[
                "auth.enable_access_tokens"
            ],
            # FIXME
            # "authentication.external_providers": external_providers,
            "users.allow_anonymous": legacy_configuration["base.allow_anonymous_user"],
            "users.allow_registration": legacy_configuration[
                "base.allow_user_registration"
            ],
            "users.name_pattern": legacy_configuration["base.user_name_pattern"],
            "users.name_pattern_description": legacy_configuration[
                "base.user_name_pattern_description"
            ],
            "users.verify_email_addresses": legacy_configuration[
                "base.verify_email_addresses"
            ],
            "repositories.archive_review_branches": legacy_configuration[
                "base.archive_review_branches"
            ],
            "repositories.url_types.git.display": "git"
            in legacy_configuration["base.repository_url_types"],
            "repositories.url_types.http.display": "http"
            in legacy_configuration["base.repository_url_types"],
            "repositories.url_types.ssh.display": "ssh"
            in legacy_configuration["base.repository_url_types"],
            "repositories.url_types.host.display": "host"
            in legacy_configuration["base.repository_url_types"],
            "content.default_encodings": legacy_configuration["base.default_encodings"],
            "smtp.configured": True,
            "smtp.address.host": legacy_configuration["smtp.host"],
            "smtp.address.port": legacy_configuration["smtp.port"],
            "smtp.use_smtps": legacy_configuration["smtp.use_ssl"],
            "smtp.use_starttls": legacy_configuration["smtp.use_starttls"],
            "smtp.credentials.username": smtp_username,
            "smtp.credentials.password": smtp_password,
            "limits.maximum_added_lines_recognized": legacy_configuration[
                "limits.maximum_added_lines_recognized"
            ],
            "limits.maximum_added_lines_unrecognized": legacy_configuration[
                "limits.maximum_added_lines_unrecognized"
            ],
            "extensions.enabled": legacy_configuration["extensions.enabled"],
            "extensions.system_dir": legacy_configuration[
                "extensions.system_extensions_dir"
            ],
            "extensions.user_dir": legacy_configuration[
                "extensions.user_extensions_dir"
            ],
            # FIXME
            # "extensions.flavors": extension_flavors,
            # "extensions.default_flavor": default_flavor,
            # "extensions.install_dir":
            #     legacy_configuration["extensions.install_dir"],
            # "extensions.workcopy_dir":
            #     legacy_configuration["extensions.workcopy_dir"],
            # "extensions.long_timeout":
            #     legacy_configuration["extensions.long_timeout"],
            # "extensions.short_timeout":
            #     legacy_configuration["extensions.short_timeout"],
            # Note: Intentionally not importing any services configuration. Too much
            #       has changed there for it to be trivial, and it was never very
            #       useful to change the configuration anyway.
        },
    )

    await critic._impl.loadSettings(critic)


async def perform(critic, arguments):
    from . import DatabaseSchemaHelper
    from .. import stop_services
    from ... import ensure_dir, write_configuration

    configuration = base.configuration()

    ensure_dir(
        base.settings_dir(),
        uid=pwd.getpwnam(configuration["system.username"]).pw_uid,
        gid=grp.getgrnam(configuration["system.groupname"]).gr_gid,
    )

    write_configuration(configuration)

    with DatabaseSchemaHelper(critic) as schema_helper:
        schema_helper.update(
            """

CREATE TABLE systemsettings (
  identity VARCHAR(32),
  key VARCHAR(256),
  value TEXT NOT NULL,
  privileged BOOLEAN NOT NULL,
  description TEXT NOT NULL,

  PRIMARY KEY (identity, key),
  FOREIGN KEY (identity) REFERENCES systemidentities (key)
);

CREATE TABLE systemevents (
  id SERIAL,
  identity VARCHAR(32) NOT NULL,
  category VARCHAR(32) NOT NULL,
  key VARCHAR(256) NOT NULL,
  title VARCHAR(256) NOT NULL,
  data TEXT NOT NULL DEFAULT 'null',
  handled BOOLEAN NOT NULL DEFAULT FALSE,

  PRIMARY KEY (id),
  FOREIGN KEY (identity) REFERENCES systemidentities (key)
);
CREATE INDEX systemevents_identity_category_key
          ON systemevents (identity, category, key);

"""
        )

        schema_helper.add_enum_value("userstatus", "disabled")
        schema_helper.add_column(
            "usersessions", "external_uid", "INTEGER REFERENCES externalusers"
        )
        schema_helper.add_constraint(
            "usersessions",
            "check_uid_or_external_uid",
            "CHECK (uid IS NOT NULL OR external_uid IS NOT NULL)",
        )

        update_git_sql(arguments, schema_helper)
        update_reviews_sql(schema_helper)

        await convert_legacy_configuration(critic, arguments, schema_helper)

    if await stop_services(critic):
        legacy_service_name = f"critic-{arguments.identity}"
        legacy_sysv_init_script = os.path.join("/etc/init.d", legacy_service_name)
        if os.path.isfile(legacy_sysv_init_script):
            os.unlink(legacy_sysv_init_script)
            subprocess.check_call(["update-rc.d", legacy_service_name, "remove"])
