# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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


class Error(Exception):
    pass


from .archiveversion import archive_version
from .cloneexternal import clone_external
from .deleteextension import delete_extension
from .fetchfromexternal import fetch_from_external
from .fetchresource import fetch_resource
from .readmanifest import read_manifest
from .scanexternal import scan_external

__all__ = [
    "archive_version",
    "clone_external",
    "delete_extension",
    "fetch_from_external",
    "fetch_resource",
    "read_manifest",
    "scan_external",
]
