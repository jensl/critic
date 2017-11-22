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

# mypy: ignore-errors

import unittest

from .gitusertime import GitUserTime

SPECIMEN = "Jens Widell <git@jenswidell.se> 1511781617 +0100"


class TestGitUserTime(unittest.TestCase):
    def test_constructor(self):
        subject = GitUserTime(SPECIMEN)

        self.assertEqual(subject.name, "Jens Widell")
        self.assertEqual(subject.email, "git@jenswidell.se")
        self.assertEqual(subject.time.isoformat(), "2017-11-27T12:20:17+01:00")
        self.assertEqual(str(subject), SPECIMEN)
