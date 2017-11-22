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

import logging

logger = logging.getLogger(__name__)

index = 2
title = "Convert user email tables structure."
scope = {"database"}


def convert_useremails_defintion(schema_helper):
    schema_helper.update(
        """

CREATE TYPE useremailstatus AS ENUM (
  'trusted',
  'verified',
  'unverified'
);

"""
    )

    schema_helper.add_column(
        "useremails", "status", "useremailstatus NOT NULL DEFAULT 'unverified'"
    )

    if schema_helper.column_exists("useremails", "verified"):
        schema_helper.execute(
            """UPDATE useremails
                  SET status='trusted'
                WHERE verified IS NULL"""
        )
        schema_helper.execute(
            """UPDATE useremails
                  SET status='verified'
                WHERE verified"""
        )
        schema_helper.commit()
        schema_helper.drop_column("useremails", "verified")

    schema_helper.rename_column("useremails", "verification_token", "token")

    schema_helper.add_constraint(
        "useremails", "useremails_id_uid_key", "UNIQUE (id, uid)"
    )


def create_selecteduseremails(schema_helper):
    schema_helper.update(
        """

CREATE TABLE selecteduseremails (
  uid INTEGER NOT NULL,
  email INTEGER NOT NULL,

  PRIMARY KEY (uid),
  FOREIGN KEY (uid) REFERENCES users ON DELETE CASCADE,
  FOREIGN KEY (email, uid) REFERENCES useremails (id, uid) ON DELETE CASCADE
);

CREATE INDEX selecteduseremails_email
          ON selecteduseremails (email);

"""
    )

    schema_helper.execute(
        """INSERT
             INTO selecteduseremails (uid, email)
           SELECT id, email
             FROM users
            WHERE email IS NOT NULL"""
    )
    schema_helper.commit()

    schema_helper.drop_column("users", "email")


def create_userswithemail(schema_helper):
    schema_helper.update(
        """

CREATE VIEW userswithemail (id, name, fullname, password, status, email) AS
          SELECT users.id, users.name, users.fullname, users.password,
                 users.status, useremails.email
            FROM users
 LEFT OUTER JOIN selecteduseremails ON (selecteduseremails.uid=users.id)
 LEFT OUTER JOIN useremails ON (
                   useremails.id=selecteduseremails.email AND
                   useremails.status!='unverified'
                 );

"""
    )


def create_useremailswithselected(schema_helper):
    schema_helper.update(
        """

CREATE VIEW useremailswithselected (id, uid, email, status, token,
                                    selected) AS
          SELECT useremails.id, useremails.uid, useremails.email,
                 useremails.status, useremails.token,
                 selecteduseremails.uid IS NOT NULL
            FROM useremails
 LEFT OUTER JOIN selecteduseremails ON (selecteduseremails.email=useremails.id);

"""
    )


async def perform(critic, arguments):
    from . import DatabaseSchemaHelper

    with DatabaseSchemaHelper(critic) as schema_helper:
        convert_useremails_defintion(schema_helper)
        create_selecteduseremails(schema_helper)
        create_userswithemail(schema_helper)
        create_useremailswithselected(schema_helper)
