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

import asyncio
import re
import unittest

from . import GitRepository, GitRawObject, GitCommit, GitTree

from critic import api


class TestGitRepository(unittest.TestCase):
    path = None

    @staticmethod
    def setUpClass():
        with api.critic.startSession(for_testing=True) as critic:
            TestGitRepository.path = api.repository.fetch(critic, name="critic").path

    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.subject = GitRepository(self.path)

    def now(self, coro):
        return self.loop.run_until_complete(coro)

    def test_attributes(self):
        self.assertEqual(self.subject.path, self.path)
        self.assertEqual(self.subject.loop, self.loop)

    def test_revparse(self):
        sha1 = self.now(self.subject.revparse("HEAD"))
        self.assertIsNotNone(re.match("^[0-9a-f]{40}$", sha1))

        same_sha1 = self.now(self.subject.revparse("HEAD", object_type="commit"))
        self.assertEqual(same_sha1, sha1)

        tree_sha1 = self.now(self.subject.revparse("HEAD", object_type="tree"))
        self.assertNotEqual(tree_sha1, sha1)

    def test_fetch(self):
        sha1 = self.now(self.subject.revparse("HEAD"))

        raw_object = self.now(self.subject.fetch(sha1))
        self.assertTrue(isinstance(raw_object, GitRawObject))
        self.assertEqual(raw_object.sha1, sha1)
        self.assertEqual(raw_object.object_type, "commit")
        self.assertTrue(isinstance(raw_object.data, bytes))

        same_raw_object = self.now(self.subject.fetch("HEAD"))
        self.assertTrue(isinstance(same_raw_object, GitRawObject))
        self.assertEqual(same_raw_object.sha1, sha1)
        self.assertEqual(same_raw_object.object_type, raw_object.object_type)
        self.assertEqual(same_raw_object.data, raw_object.data)

        commit_object = self.now(self.subject.fetch(sha1, wanted_object_type="commit"))
        self.assertTrue(isinstance(commit_object, GitCommit))
        self.assertEqual(commit_object.sha1, sha1)

        tree_object = self.now(self.subject.fetch(sha1, wanted_object_type="tree"))
        self.assertTrue(isinstance(tree_object, GitTree))
        self.assertNotEqual(tree_object.sha1, sha1)

        other_raw_object = self.now(
            self.subject.fetch(
                sha1, wanted_object_type="tree", object_factory=GitRawObject
            )
        )
        self.assertTrue(isinstance(other_raw_object, GitRawObject))
        self.assertNotEqual(other_raw_object.sha1, sha1)

    def tearDown(self):
        self.now(self.subject.close())

    @staticmethod
    def tearDownClass():
        asyncio.get_event_loop().close()
