# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

"""Critic API implementation"""

from . import critic

from . import accesscontrolprofile
from . import accesstoken
from . import batch
from . import branch
from . import branchsetting
from . import branchupdate
from . import changeset
from . import comment
from . import commit
from . import commitset
from . import extension
from . import extensioninstallation
from . import extensionversion
from . import externalaccount
from . import file
from . import filechange
from . import filecontent
from . import filediff
from . import labeledaccesscontrolprofile
from . import mergeanalysis
from . import partition
from . import rebase
from . import reply
from . import repository
from . import repositoryfilter
from . import repositorysetting
from . import review
from . import reviewablefilechange
from . import reviewevent
from . import reviewfilter
from . import reviewintegrationrequest
from . import reviewping
from . import reviewscope
from . import reviewscopefilter
from . import reviewtag
from . import systemevent
from . import systemsetting
from . import trackedbranch
from . import tree
from . import tutorial
from . import user
from . import useremail
from . import usersetting
from . import usersshkey


__all__ = [
    "accesscontrolprofile",
    "accesstoken",
    "batch",
    "branch",
    "branchsetting",
    "branchupdate",
    "changeset",
    "comment",
    "commit",
    "commitset",
    "critic",
    "extension",
    "extensioninstallation",
    "extensionversion",
    "externalaccount",
    "file",
    "filechange",
    "filecontent",
    "filediff",
    "labeledaccesscontrolprofile",
    "mergeanalysis",
    "partition",
    "rebase",
    "reply",
    "repository",
    "repositoryfilter",
    "repositorysetting",
    "review",
    "reviewablefilechange",
    "reviewevent",
    "reviewfilter",
    "reviewintegrationrequest",
    "reviewping",
    "reviewscope",
    "reviewscopefilter",
    "reviewtag",
    "systemevent",
    "systemsetting",
    "trackedbranch",
    "tree",
    "tutorial",
    "user",
    "useremail",
    "usersetting",
    "usersshkey",
]
