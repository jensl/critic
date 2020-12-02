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

import argparse
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

from critic import api

name = "calibrate-pwhash"
description = "Calibrate password hashing."


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hash-time",
        type=float,
        default=0.25,
        help="The target amount of time in seconds that hashing should take.",
    )
    parser.set_defaults(need_session=True)


async def main(critic: api.critic.Critic, arguments: Any) -> int:
    import passlib.context

    authentication_mode = api.critic.settings().frontend.authentication_mode
    if authentication_mode != "critic":
        logger.error(
            'Not meaningful with frontend.authentication_mode=="%s"',
            authentication_mode,
        )
        return 1

    internal_authdb = api.critic.settings().authentication.databases.internal
    if not internal_authdb.enabled:
        logger.error("Only meaningful with internal authentication database")
        return 1

    hash_scheme = internal_authdb.used_scheme

    min_rounds_name = "%s__rounds" % hash_scheme
    min_rounds_value = 1

    while True:
        calibration_context = passlib.context.CryptContext(
            schemes=[hash_scheme],
            default=hash_scheme,
            **{min_rounds_name: min_rounds_value}
        )

        before = time.process_time()

        for _ in range(10):
            calibration_context.hash("password")

        # It's possible encryption was fast enough to measure as zero, or some
        # other ridiculously small number.  "Round" it up to at least one
        # millisecond for sanity.
        hash_time = max(0.001, (time.process_time() - before) / 10)

        if hash_time >= arguments.hash_time:
            break

        # Multiplication factor.  Make it at least 1.2, to ensure we actually
        # ever finish this loop, and at most 10, to ensure we don't over-shoot
        # by too much.
        factor = max(1.2, min(10.0, arguments.hash_time / hash_time))

        min_rounds_value = int(factor * min_rounds_value)

    logger.info(
        "Hashing with min_rounds=%d took %.2f seconds", min_rounds_value, hash_time
    )

    setting = await api.systemsetting.fetch(
        critic, key="authentication.databases.internal.minimum_rounds"
    )

    async with api.transaction.start(critic, accept_no_pubsub=True) as transaction:
        await transaction.modifySystemSetting(setting).setValue(min_rounds_value)

    return 0
