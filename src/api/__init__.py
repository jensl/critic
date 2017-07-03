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

"""Critic API"""

from apiobject import APIObject
from apierror import APIError, PermissionDenied, TransactionError

import config
import critic
import user
import review
import repository
import filters
import branch
import commit
import commitset
import changeset
import filechange
import filediff
import log
import preference
import accesstoken
import accesscontrolprofile
import labeledaccesscontrolprofile
import extension
import file
import comment
import reply
import batch
import reviewablefilechange

import transaction
