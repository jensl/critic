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
from critic import api


class PingedGenerator:
    email_type = "pingedReview"

    def setPing(self, ping):
        self.ping = ping

    async def __call__(self, mail):
        review = await mail.group.event.review
        from_user = mail.group.from_user
        to_user = mail.to_user

        rfcs = await api.reviewablefilechange.fetchAll(
            review, assignee=to_user, is_reviewed=False
        )

        if not rfcs:
            return False

        mail.add_section(f"{from_user.fullname} has pinged the review!")

        if self.ping.message.strip():
            mail.add_section(f"Message:", *wrapped(mail, self.ping.message))

        mail.add_section(
            "The following still pending changes are assigned to you:",
            *await changed_lines_per_file(mail, rfcs),
        )

        mail.add_section(
            "To see all these changes:",
            *(
                f"  {url_prefix}/r/{review.id}/changeset/automatic/pending"
                for url_prefix in await to_user.url_prefixes
            ),
        )


async def handle_pinged(critic, event):
    generator = PingedGenerator()
    generator.setPing(await event.ping)

    group = ReviewMailGroup(event, await event.user, generator.email_type)

    async with group:
        await group.ensure_parent_message_ids()
        await group.generate(generator)
