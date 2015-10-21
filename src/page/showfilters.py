# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import dbutils
import gitutils
import request
import reviewing.filters
import page.utils

def renderShowFilters(req, db, user):
    path = req.getParameter("path", "/")
    repo_name = req.getParameter(
        "repository", user.getPreference(db, "defaultRepository"))
    repository = gitutils.Repository.fromParameter(db, repo_name)

    show_path = path

    if path.endswith("/") or repository.getHead(db).isDirectory(path):
        path = path.rstrip("/") + "/dummy.txt"

    file_id = dbutils.find_file(db, path=path)

    filters = reviewing.filters.Filters()
    filters.setFiles(db, [file_id])
    filters.load(db, repository=repository, recursive=True)

    reviewers = []
    watchers = []

    for user_id, (filter_type, _delegate) in filters.listUsers(file_id).items():
        if filter_type == 'reviewer': reviewers.append(user_id)
        else: watchers.append(user_id)

    result = "Path: %s\n" % show_path

    reviewers_found = False
    watchers_found = False

    for reviewer_id in sorted(reviewers):
        if not reviewers_found:
            result += "\nReviewers:\n"
            reviewers_found = True

        reviewer = dbutils.User.fromId(db, reviewer_id)
        result += "  %s <%s>\n" % (reviewer.fullname, reviewer.email)

    for watcher_id in sorted(watchers):
        if not watchers_found:
            result += "\nWatchers:\n"
            watchers_found = True

        watcher = dbutils.User.fromId(db, watcher_id)
        result += "  %s <%s>\n" % (watcher.fullname, watcher.email)

    if not reviewers_found and not watchers_found:
        result += "\nNo matching filters found.\n"

    return page.utils.ResponseBody(result, content_type="text/plain")
