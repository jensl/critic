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

from .gitobject import GitObject, GitRawObject, GitBlob, GitCommit, GitTag, GitTree

SHA1 = "0123456789" * 4

COMMIT_SHA1 = "62362e42d098b2cd654766bbd7902afe8eaf1990"
COMMIT_RAW = b"""\
tree ddc97e1a6237dfa1a74e196136dde2245d99b716
parent 8889ad2b49b6954175aa3e4d9430dd76f4bbea34
author Jens Widell <jl@opera.com> 1504861985 +0200
committer Jens Widell <jl@critic-review.org> 1505379555 +0200

API / JSON API: Allow empty draft comments

It may be useful for the UI to be able to create a comment before the user
has actually written anything. So allow this.

Skip (and delete) these empty comments when submitting changes instead.
"""
PARENT_SHA1 = "8889ad2b49b6954175aa3e4d9430dd76f4bbea34"

TREE_SHA1 = "ddc97e1a6237dfa1a74e196136dde2245d99b716"
TREE_RAW = (
    b"100644 .gitignore"
    b"\x00O8\xd8\xec\r\xfb8\x1b\x9d\x1a\xc3B`\x14\xe1u\xf4S4}"
    b"100644 .gitmodules"
    b"\x00\xa0Fw1\xde}\xf9\xb4/A?>\x06\x90f\xce\x8e\xf0\x12\t"
    b"100644 CONTRIBUTORS"
    b"\x00z+\x91\x86\x8c+\xd2\xb6U`\x1b7)\xe8C\xe1\xfd\x05\xa5\xd9"
    b"100644 COPYING"
    b"\x00\xc1\t0\xa9\xca\xe8\x06?W\xaf)\xd9\xc9\xcc<6\xd7<\x8f\xbf"
    b"100644 INSTALL"
    b"\x00\xc7\x0e\x9av\x85\xbaC\x1f_#T5e\xb0\x07G\x81\x04_\x80"
    b"100644 README.md"
    b"\x00\xc6BN\xd8\xb3N\xc4\xab\x81\xacYsh\x94\x8eR\x06\xfcQ\r"
    b"40000 documentation"
    b"\x00h\x8b\xcd\xa8G\xe8\x1b\xae\xe3T\xd2u\n\xed\xab#\x1e\xa3I\x14"
    b"100644 extend.py"
    b"\x00\x10\xb6\xc2K\xa2\xb2\xfc\x14\x8b\x91\xcd\x96\xbb\xd4\xf6Eg\xd4\x97"
    b"\xbd"
    b"100644 install.py"
    b"\x00AV\x8a\x9a\x8d\x11\xc3\\\xa5\xefv\xd1\xed\x80\x9b0R\xb9\\d"
    b"40000 installation"
    b"\x00S\xc5\x14\xdf\x88\x10\xb8\xc2Jj\xac\xdf\xc5\xa16\x9d\xad\x034^"
    b"100644 pylint.rc"
    b"\x00\xf3\t\xe0^\xe6\xbb\xa4\x7f8\xba\x08}\xc2s[\xe8\x04\xb5l\x08"
    b"100644 pythonversion.py"
    b'\x00\r\xcc8\x9e1\xdf\x11mf$\xc7\xd1\xa5I\x13\x03@"\xe4\xac'
    b"100755 quickstart.py"
    b"\x00\x0e\xd0L~gd)\x99y\xf7\xb1\xce\x9c\xa5\xfc\xca\xe2\xdd6\xd0"
    b"40000 src"
    b"\x00\xb4\xef\x9f/\xb2\xc4\x1eb\x8c\x92\xe2\xea6\x19*\x878\xdd\x04I"
    b"40000 testing"
    b"\x00\x03\xa4\xdf\x9d|\xe2M\xf7[*\x83\x94L5\xe3\xda\xbd\xc4\x95P"
    b"100644 uninstall.py"
    b"\x00)\x87[\xbeu\x92Lj\xa7\xb9d\xf4\x8a\xe8G\x19\xc4S\x87\xc2"
    b"100644 upgrade.py"
    b"\x00\xde\xe4\xd1\xa9:\xb6c\x0e\x11\xaa\xdf\xab\n\xb0=\xde\xbf\xf5\xdc\x11"
)

TAG_SHA1 = "be7fae6d8b9c1f5d516e257ec3bffdd246408391"
TAG_RAW = b"""\
object 60115f54bda3a127ed3cc8ffc6ab6c771cbceb1b
type commit
tag v2.8.2
tagger Junio C Hamano <gitster@pobox.com> 1461964775 -0700

Git 2.8.2
-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQIcBAABAgAGBQJXI8/nAAoJELC16IaWr+bLZikP/jd+ML1D5eSnLp5vJ7s1rUsa
CONLoAdNQEgTVIpLV2kWLxHfDyPE5XqJh03mNNwoqFA93L5IYwnMalH5p/w+Sg3Z
WtxpI1+yliUrMTmrDCUEUusMy6ntLzL9gMGAFaLrDI7yyrHRI/Qa6T+SWhqcYsI/
c5r/bVKhWhlqZ0krExHCgdPWYUG6G06FZV/FUi2hr0jEwhxCTAZE0Y+Y2NyizUEj
RmiicD7GQ/PBS7hcZOw2+WPIT9lklUjn6o8Qu/5V8q5UANw0JGjmkqZYN/BlMu9l
z9Foyw5Lz5TD9NKGR2dS1TeDF/3MDdX2qRZqoHOcjdeVZf1skQSuSujDL6Mm6Vsf
fFKGBpuKTjhElKzD+Pv9qM3a/SvIKTR0efbG8G4PVOved3vyGk64dhFn7EPBdLUm
bAaX6j6Xm2aiYwCago5VHRgCrt9S5+eEn/PrzJe1WOtLoDzRLIQfT7/b67g0HdAC
3Ng6nFjWiihL5QH7Ehbz9zxjbzFXUW4W4ICYLZEo8qQoEu9XKTnSNopxrJQ5UlGu
ndzOQGXf1upKMkTVjfzLq/UHV0Xti7Ljkc3vtKChkN/SSp7kELmL/ZWC/3AYI6di
jnNgFtWr6xKCBIqt28nneWSIA6xo4I9SaWbxMFP8e1o/q8xeejs5YfrsmR2r/DRe
duHeO2pyqHUKXNtrR64z
=Umdr
-----END PGP SIGNATURE-----
"""
OBJECT_SHA1 = "60115f54bda3a127ed3cc8ffc6ab6c771cbceb1b"


class TestGitObject(unittest.TestCase):
    def test_constructor(self):
        subject = GitObject(SHA1)
        self.assertEqual(subject.sha1, SHA1)

    def test_factory_for(self):
        self.assertIs(GitObject.factory_for["blob"], GitBlob)
        self.assertIs(GitObject.factory_for["commit"], GitCommit)
        self.assertIs(GitObject.factory_for["tag"], GitTag)
        self.assertIs(GitObject.factory_for["tree"], GitTree)


class TestGitRawObject(unittest.TestCase):
    def test_constructor(self):
        subject = GitRawObject(SHA1, "blob", b"this is some data")
        self.assertEqual(subject.sha1, SHA1)
        self.assertEqual(subject.object_type, "blob")
        self.assertEqual(subject.data, b"this is some data")


class TestGitBlob(unittest.TestCase):
    def test_constructor(self):
        subject = GitBlob(SHA1, "blob", b"this is some data")
        self.assertEqual(subject.sha1, SHA1)
        self.assertEqual(subject.object_type, "blob")
        self.assertEqual(subject.data, b"this is some data")


class TestGitCommit(unittest.TestCase):
    def test_constructor(self):
        subject = GitCommit(COMMIT_SHA1, "commit", COMMIT_RAW)
        self.assertEqual(subject.sha1, COMMIT_SHA1)
        self.assertEqual(subject.object_type, "commit")
        self.assertEqual(subject.tree, TREE_SHA1)
        self.assertEqual(subject.parents, [PARENT_SHA1])
        self.assertEqual(subject.author.name, "Jens Widell")
        self.assertEqual(subject.author.email, "jl@opera.com")
        self.assertEqual(subject.author.time.isoformat(), "2017-09-08T11:13:05+02:00")
        self.assertEqual(subject.committer.name, "Jens Widell")
        self.assertEqual(subject.committer.email, "jl@critic-review.org")
        self.assertEqual(
            subject.committer.time.isoformat(), "2017-09-14T10:59:15+02:00"
        )


class TestGitTag(unittest.TestCase):
    def test_constructor(self):
        subject = GitTag(TAG_SHA1, "tag", TAG_RAW)
        self.assertEqual(subject.sha1, TAG_SHA1)
        self.assertEqual(subject.object_type, "tag")
        self.assertEqual(subject.object, OBJECT_SHA1)
        self.assertEqual(subject.type, "commit")
        self.assertEqual(subject.tag, "v2.8.2")
        self.assertEqual(subject.tagger.name, "Junio C Hamano")
        self.assertEqual(subject.tagger.email, "gitster@pobox.com")
        self.assertEqual(subject.tagger.time.isoformat(), "2016-04-29T14:19:35-07:00")


class TestGitTree(unittest.TestCase):
    def test_constructor(self):
        subject = GitTree(TREE_SHA1, "tree", TREE_RAW)
        self.assertEqual(subject.sha1, TREE_SHA1)
        self.assertEqual(subject.object_type, "tree")
        self.assertEqual(len(subject.entries), 17)
