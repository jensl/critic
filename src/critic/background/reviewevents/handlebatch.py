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

# type: ignore

import logging

logger = logging.getLogger(__name__)

from . import ReviewMailGroup, changed_lines_per_file, wrapped


class SubmittedChangesGenerator:
    email_type = "updatedReview.submittedChanges"

    def setBatch(self, batch):
        self.batch = batch

    async def __call__(self, mail):
        # review = await mail.group.event.review
        from_user = mail.group.from_user
        # to_user = mail.to_user

        mail.add_section(f"{from_user.fullname} has updated the review.")

        comment = await self.batch.comment
        if comment:
            mail.add_section("Overall comment:", *wrapped(mail, comment.text))

        reviewed_rfcs = await self.batch.reviewed_file_changes
        if reviewed_rfcs:
            mail.add_section(
                "The following changes were marked as reviewed:",
                *await changed_lines_per_file(mail, reviewed_rfcs),
            )

        unreviewed_rfcs = await self.batch.unreviewed_file_changes
        if unreviewed_rfcs:
            mail.add_section(
                "The following changes were marked as NO LONGER reviewed:",
                *await changed_lines_per_file(mail, unreviewed_rfcs),
            )

        # FIXME: Should be more text here!


async def handle_batch(critic, event):
    batch = await event.batch
    review = await event.review

    if review.state == "draft":
        return

    generator = SubmittedChangesGenerator()
    generator.setBatch(batch)

    group = ReviewMailGroup(event, await event.user, generator.email_type)

    async with group:
        await group.ensure_parent_message_ids()
        await group.generate(generator)
