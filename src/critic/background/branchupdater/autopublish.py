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
import re

logger = logging.getLogger(__name__)

from ...background.githook import emit_output
from critic import api


async def should_auto_publish(
    review: api.review.Review, *, pendingrefupdate_id: int = None
) -> bool:
    critic = review.critic
    repository = await review.repository
    branch = await review.branch
    owners = await review.owners

    assert review.state == "draft"
    assert len(owners) == 1

    (owner,) = owners

    if branch is None or not review.summary:
        # Review is incomplete and cannot be automatically published.
        return False

    with critic.asUser(owner):
        auto_publish_limit = await repository.getSetting("pushAutoPublishLimit", 0)
        auto_publish_pattern = await repository.getSetting("pushAutoPublishPattern", "")

    if not (0 < len(await review.commits) <= auto_publish_limit):
        # Too many commits. Could be that the limit is zero, meaning auto-
        # publish is disabled.
        return False

    if auto_publish_pattern:
        try:
            if not re.match(auto_publish_pattern, branch.name):
                return False
        except re.error as error:
            output = "WARNING: Invalid 'review.pushAutoPublishPattern': %s" % str(error)
            await emit_output(critic, pendingrefupdate_id, output)
            return False

    return True
