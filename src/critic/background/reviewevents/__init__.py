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

from __future__ import annotations

import logging
import textwrap
from typing import Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import mailutils


async def get_recipients(
    event: api.reviewevent.ReviewEvent, email_type: str
) -> Sequence[api.user.User]:
    critic = event.critic
    review = await event.review
    candidates = (
        await review.owners | await review.assigned_reviewers | await review.watchers
    )
    recipients = []

    for candidate in candidates:
        if not candidate.email:
            # User has no (or unverified) email address.
            continue
        with critic.asUser(candidate):
            if not await api.usersetting.get(
                critic, "email", "activated", default=False
            ):
                # User has disabled emails altogether.
                continue
            if not await api.usersetting.get(
                critic, "email", "subjectLine." + email_type, default="enabled"
            ):
                # User has disabled this specific type of email.
                continue
        recipients.append(candidate)

    return recipients


async def changed_lines_per_file(mail, rfcs, *, indent="  "):
    counts_per_file = {}

    for rfc in rfcs:
        file = await rfc.file
        deleted, inserted = counts_per_file.get(file, (0, 0))
        deleted += rfc.deleted_lines
        inserted += rfc.inserted_lines
        counts_per_file[file] = (deleted, inserted)

    max_path_length = max(len(file.path) for file in counts_per_file)
    max_deleted = max(deleted for deleted, _ in counts_per_file.values())
    deleted_width = len(str(max_deleted))
    max_inserted = max(inserted for _, inserted in counts_per_file.values())
    inserted_width = len(str(max_inserted))

    counts_fmt = f"  -%{deleted_width}d/+%{inserted_width}d"
    path_width = min(
        mail.line_length - (len(indent) + len(counts_fmt % (0, 0))), max_path_length
    )
    path_fmt = f"%-{path_width}s"

    def pad_path(path):
        padded = path_fmt % path
        if len(padded) > path_width:
            left = (path_width - 5) / 2
            right = (path_width - 5) - left
            return padded[:left] + " ... " + padded[-right:]
        return padded

    lines = []
    for file, counts in sorted(counts_per_file.items(), key=lambda item: item[0].path):
        lines.append(indent + (path_fmt % file.path) + (counts_fmt % counts))
    return lines


def indented(level, *lines):
    indent = " " * level
    return [indent + line for line in lines]


def wrapped(mail, text, *, indent=2):
    return indented(indent, *textwrap.wrap(text, mail.line_length - indent))


class ReviewMailGroup:
    def __init__(self, event, from_user, email_type):
        self.event = event
        self.from_user = from_user
        self.email_type = email_type
        self.mails = []
        self.parent_message_ids = {}  # { user => str }
        self.reviewmessageids_values = []
        self.cache = {}

    async def generate(self, generator, add_review_message_ids=False):
        recipients = await get_recipients(self.event, self.email_type)
        for to_user in recipients:
            mail = ReviewMail(self, to_user, self.email_type)
            await mail.initialize()
            mail.parent_message_id = self.parent_message_ids.get(to_user)
            logger.debug("generating %s", mail)
            if (await generator(mail)) is False:
                logger.debug("  - skipped by generator")
            else:
                queued_mail = mailutils.queueMail(
                    self.from_user,
                    to_user,
                    recipients,
                    await mail.subject,
                    await mail.body,
                    parent_message_id=mail.parent_message_id,
                )
                self.mails.append(queued_mail)
                if add_review_message_ids:
                    self.reviewmessageids_values.append(
                        dict(
                            review=(await self.event.review).id,
                            user=to_user.id,
                            message_id=queued_mail.message_id,
                        )
                    )

    async def ensure_parent_message_ids(self):
        from .handlepublished import generate

        review = await self.event.review

        async with self.event.critic.query(
            """SELECT uid, messageid
                 FROM reviewmessageids
                WHERE review={review}""",
            review=review,
        ) as result:
            message_ids = dict(await result.all())
            logger.debug("message_ids: %r", message_ids)

        needs_placeholder = set()
        recipients = await get_recipients(self.event, self.email_type)
        for to_user in recipients:
            if to_user.id in message_ids:
                self.parent_message_ids[to_user] = message_ids[to_user.id]
            else:
                needs_placeholder.add(to_user)
        for to_user in needs_placeholder:
            mail = ReviewMail(self, to_user, "newishReview")
            await mail.initialize()
            logger.debug("generating %s", mail)
            if (await generate(mail)) is False:
                logger.debug("  - skipped by generator")
            else:
                queued_mail = mailutils.queueMail(
                    self.from_user,
                    to_user,
                    recipients,
                    await mail.subject,
                    await mail.body,
                )
                self.mails.append(queued_mail)
                self.reviewmessageids_values.append(
                    dict(
                        review=review.id,
                        user=to_user.id,
                        message_id=queued_mail.message_id,
                    )
                )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            critic = self.event.critic
            async with critic.transaction() as cursor:
                await cursor.executemany(
                    """INSERT
                         INTO reviewmessageids (review, uid, messageid)
                       VALUES ({review}, {user}, {message_id})""",
                    self.reviewmessageids_values,
                )
            mailutils.sendPendingMails(self.mails)
        else:
            mailutils.cancelPendingMails(self.mails)


class ReviewMail:
    def __init__(self, group, to_user, email_type):
        self.group = group
        self.to_user = to_user
        self.type = email_type
        self.parent_message_id = None
        self.sections = []

    def __str__(self):
        return "%s mail to %s" % (self.type, self.to_user.email)

    async def initialize(self):
        self.line_length = int(await self.to_user.getPreference("email.lineLength"))
        self.separator = "-" * self.line_length

    @property
    async def header(self):
        lines = [
            self.separator,
            "This is an automatic message generated by the review at:",
        ]
        review = await self.group.event.review
        for url_prefix in await self.to_user.url_prefixes:
            lines.append(f"  {url_prefix}/r/{review.id}")
        lines.append(self.separator)
        return "\n".join(lines)

    @property
    async def subject(self):
        review = await self.group.event.review
        fmt = str(await self.to_user.getPreference("email.subjectLine." + self.type))
        return fmt % {
            "id": "r/%d" % review.id,
            "summary": review.summary,
            # "progress": str(review.getReviewState(db)),
            "branch": (await review.branch).name,
        }

    @property
    async def body(self):
        return "\n\n\n".join(
            [await self.header] + self.sections + [f"--{self.group.from_user.name}"]
        )

    def add_section(self, *lines, wrap_lines=True):
        actual_lines = []
        for line in lines:
            if not line or not line[0].isalpha():
                actual_lines.append(line)
            else:
                actual_lines.extend(textwrap.wrap(line, self.line_length))
        self.sections.append("\n".join(actual_lines))

    def add_separator(self):
        self.sections.append(self.separator)
