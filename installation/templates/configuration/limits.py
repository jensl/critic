# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

# When a file is added, and it has more lines than these limits,
# output a "File was added." placeholder instead of the entire file,
# with an option to fetch all the lines.  The _RECOGNIZED option is
# for a file in a recognized (and syntax highlighted) language, the
# _UNRECOGNIZED option is for other files.
MAXIMUM_ADDED_LINES_RECOGNIZED = 8000
MAXIMUM_ADDED_LINES_UNRECOGNIZED = 2000

# Reject any single ref update that causes more than this many new
# commits to be added to the repository.  The likely cause for hitting
# this limit is pushing a branch to the wrong repository, which just
# causes bloat in the receiving repository.
PUSH_COMMIT_LIMIT = 10000

# For branches containing more commits than this, fall back to simpler
# branch log rendering for performance reasons.
MAXIMUM_REACHABLE_COMMITS = 4000

# Maximum number of commits when /createreview is loaded with the
# 'branch' URI parameter to create a review of all commits on a branch.
MAXIMUM_REVIEW_COMMITS = 2000
