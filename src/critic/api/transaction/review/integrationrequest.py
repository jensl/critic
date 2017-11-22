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
from typing import Optional

logger = logging.getLogger(__name__)

from . import CreatedReviewIntegrationRequest
from .. import Transaction, Insert

from critic import api


async def create_integration_request(
    transaction: Transaction,
    review: api.review.Review,
    do_squash: bool,
    squash_message: Optional[str],
    do_autosquash: bool,
    do_integrate: bool,
) -> CreatedReviewIntegrationRequest:
    integration = await review.integration
    assert integration
    target_branch = integration.target_branch
    review_branch = await review.branch
    assert review_branch
    branchupdate = (await review_branch.updates)[-1]

    return CreatedReviewIntegrationRequest(transaction, review).insert(
        review=review,
        target=target_branch,
        branchupdate=branchupdate,
        do_squash=do_squash,
        squash_message=squash_message,
        do_autosquash=do_autosquash,
        do_integrate=do_integrate,
    )
