# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2018 the Critic contributors, Opera Software ASA
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

index = 3
title = "Fix branchupdates.id sequence."
scope = {"database"}


class Reference:
    def __init__(
        self, table_name, column_name, *, flags=set(), target=("branchupdates", "id")
    ):
        self.table_name = table_name
        self.column_name = column_name
        self.flags = flags
        self.target = target


references = [
    Reference("commentchains", "addressed_by_update"),
    Reference("branchmerges", "branchupdate", flags={"not_null", "on_delete_cascade"}),
    Reference(
        "branchupdatecommits", "branchupdate", flags={"not_null", "on_delete_cascade"}
    ),
    Reference("pendingrefupdates", "branchupdate", flags={"on_delete_set_null"}),
    Reference(
        "reviewupdates", "branchupdate", flags={"primary_key", "on_delete_cascade"}
    ),
    Reference(
        "reviewcommits",
        "branchupdate",
        flags={"on_delete_cascade"},
        target=("reviewupdates", "branchupdate"),
    ),
    Reference(
        "reviewchangesets",
        "branchupdate",
        flags={"on_delete_cascade"},
        target=("reviewupdates", "branchupdate"),
    ),
    Reference(
        "reviewrebases",
        "branchupdate",
        flags={"on_delete_cascade"},
        target=("reviewupdates", "branchupdate"),
    ),
    Reference("rebasereplayrequests", "branchupdate", flags={"on_delete_cascade"}),
]


def prepare(schema_helper):
    schema_helper.add_column("branchupdates", "fixed_id", "INTEGER")

    for reference in references:
        schema_helper.drop_constraint(
            f"{reference.table_name}_{reference.column_name}_fkey"
        )

    schema_helper.drop_constraint("branchupdates_pkey")
    schema_helper.drop_constraint("branchupdatecommits_pkey")
    schema_helper.drop_constraint("reviewupdates_pkey")
    schema_helper.drop_index("pendingrefupdates_branchupdate")
    schema_helper.commit()


# def convert_changeset_column(schema_helper, table_name,
#                              column_name="branchupdate", *, not_null=False,
#                              on_delete=None):
#     schema_helper.rename_column(
#         table_name, column_name, f"legacy_{column_name}")
#     schema_helper.add_column(table_name, column_name, "INTEGER")
#     schema_helper.execute(
#         f"""UPDATE {table_name}
#                SET {column_name}=branchupdates.fixed_id
#               FROM branchupdates
#              WHERE {table_name}.legacy_{column_name}=branchupdates.id""")
#     if not_null:
#         schema_helper.alter_column(table_name, column_name, not_null=True)
#     schema_helper.drop_column(table_name, f"legacy_{column_name}")
#     schema_helper.commit()


def calculate(schema_helper):
    cursor = schema_helper.database.cursor()

    cursor.execute(
        """SELECT DISTINCT reviews.branch
             FROM reviews
             JOIN reviewrebases ON (reviewrebases.review=reviews.id)"""
    )

    translated_ids = []

    for (branch_id,) in cursor.fetchall():
        cursor.execute(
            """SELECT id, updated_at
                 FROM branchupdates
                WHERE branch=%s
             ORDER BY id ASC""",
            (branch_id,),
        )
        branchupdates = cursor.fetchall()

        if len(branchupdates) < 2:
            continue

        # Find an initial segment of branch updates with identical timestamps.
        # This, we assume, is the segment that the migration script inserted.
        # The segment will be exact reversed, so we should just remap the ids
        # of the updates with the segment.
        migrated_ids = [branchupdates[0][0]]
        migrated_timestamp = branchupdates[0][1]

        for branchupdate_id, timestamp in branchupdates[1:]:
            if timestamp == migrated_timestamp:
                migrated_ids.append(branchupdate_id)

        if len(migrated_ids) < 2:
            continue

        for index, branchupdate_id in enumerate(migrated_ids):
            translated_ids.append((migrated_ids[-(index + 1)], branchupdate_id))

    if translated_ids:
        cursor.executemany(
            """UPDATE branchupdates
                  SET fixed_id=%s
                WHERE id=%s""",
            translated_ids,
        )

    cursor.execute(
        """
        UPDATE branchupdates
           SET fixed_id=id
         WHERE fixed_id IS NULL"""
    )

    schema_helper.commit()


def update_references(schema_helper):
    for reference in references:
        schema_helper.execute(
            f"""UPDATE {reference.table_name}
                   SET {reference.column_name}=branchupdates.fixed_id
                  FROM branchupdates
                 WHERE {reference.column_name}=branchupdates.id"""
        )

    schema_helper.commit()


def finish(schema_helper):
    schema_helper.execute(
        """ALTER SEQUENCE branchupdates_id_seq
                 OWNED BY NONE"""
    )
    schema_helper.drop_column("branchupdates", "id")
    schema_helper.rename_column("branchupdates", "fixed_id", "id")
    schema_helper.execute(
        """SELECT setval('branchupdates_id_seq', MAX(id) + 1)
             FROM branchupdates"""
    )
    schema_helper.alter_column(
        "branchupdates", "id", not_null=True, default="NEXTVAL('branchupdates_id_seq')"
    )
    schema_helper.execute(
        """ALTER SEQUENCE branchupdates_id_seq
                 OWNED BY branchupdates.id"""
    )
    schema_helper.update(
        """

CREATE INDEX pendingrefupdates_branchupdate
          ON pendingrefupdates (branchupdate);

    """
    )

    schema_helper.add_constraint(
        "branchupdates", "branchupdates_pkey", "PRIMARY KEY (id)"
    )

    for reference in references:
        constraint = (
            f"FOREIGN KEY ({reference.column_name})"
            f" REFERENCES {reference.target[0]}"
            f" ({reference.target[1]})"
        )
        if "on_delete_cascade" in reference.flags:
            constraint += " ON DELETE CASCADE"
        if "on_delete_set_null" in reference.flags:
            constraint += " ON DELETE SET NULL"
        schema_helper.add_constraint(
            reference.table_name,
            f"{reference.table_name}_{reference.column_name}_fkey",
            constraint,
        )
        if reference.table_name == "branchupdatecommits":
            schema_helper.add_constraint(
                "branchupdatecommits",
                "branchupdatecommits_pkey",
                "PRIMARY KEY (branchupdate, commit)",
            )
        if reference.table_name == "reviewupdates":
            schema_helper.add_constraint(
                "reviewupdates", "reviewupdates_pkey", "PRIMARY KEY (branchupdate)"
            )

    schema_helper.commit()


async def perform(critic, arguments):
    from . import DatabaseSchemaHelper

    with DatabaseSchemaHelper(critic) as schema_helper:
        prepare(schema_helper)
        calculate(schema_helper)
        update_references(schema_helper)
        finish(schema_helper)
