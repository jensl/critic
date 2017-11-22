# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2020 the Critic contributors, Opera Software ASA
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

from typing import (
    Any,
    Optional,
    Sequence,
)


class GitError(Exception):
    pass


class GitRepositoryError(GitError):
    pass


class GitProcessError(GitError):
    argv: Sequence[str]
    cwd: Optional[str]
    returncode: int
    stdout: Optional[bytes]
    stderr: Optional[bytes]

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        _, self.argv, self.cwd, self.returncode, self.stdout, self.stderr = args

    @staticmethod
    def make(
        argv: Sequence[str],
        cwd: Optional[str],
        returncode: int,
        stdout: Optional[bytes],
        stderr: Optional[bytes],
    ) -> GitProcessError:
        return GitProcessError(
            f"`git {' '.join(argv)}` failed in {cwd}",
            argv,
            cwd,
            returncode,
            stdout,
            stderr,
        )


class GitReferenceError(GitError):
    ref: str
    path: str
    output: str

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        _, self.ref, self.path, self.output = args

    @staticmethod
    def make(ref: str, path: str, output: str) -> GitReferenceError:
        return GitReferenceError(
            f"failed to resolve {ref} in {path}: {output}", ref, path, output
        )


class GitFetchError(GitError):
    object_id: str
    path: str
    message: str

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        _, self.object_id, self.path, self.message = args

    @staticmethod
    def make(
        object_id: Optional[str], path: Optional[str], message: str
    ) -> GitFetchError:
        return GitFetchError(
            f"failed to fetch {object_id} in {path}: {message}",
            object_id,
            path,
            message,
        )
