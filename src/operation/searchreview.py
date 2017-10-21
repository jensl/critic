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

import re
import urllib

import configuration
import dbutils
import gitutils

from operation import Operation, OperationResult, OperationFailure

def globToSQLPattern(glob):
    pattern = glob.replace("\\", "\\\\").replace("%", "\\%").replace("?", "_").replace("*", "%")
    if "?" in glob or "*" in glob:
        return pattern
    return "%" + pattern + "%"

def pathToSQLRegExp(path):
    pattern = ""
    if path.startswith("/"):
        pattern += "^"
        path = path.lstrip("/")
    escaped = re.sub(r"[(){}\[\].\\+^$]", lambda match: "\\" + match.group(), path)
    replacements = { "**/": "(?:[^/]+/)*", "*": "[^/]*", "?": "." }
    pattern += re.sub("\*\*/|\*|\?", lambda match: replacements[match.group()], escaped)
    return pattern

class Query(object):
    def __init__(self, parent=None):
        if not parent:
            self.tables = { "reviews": set() }
            self.arguments = []
        else:
            self.tables = parent.tables
            self.arguments = parent.arguments
        self.conditions = []

    def addTable(self, table, *conditions):
        self.tables.setdefault(table, set()).update(conditions)

class Review(object):
    def __init__(self, review_id, summary):
        self.review_id = review_id
        self.summary = summary
    def json(self):
        return { "id": self.review_id, "summary": self.summary }

class InvalidFilter(Exception):
    def __init__(self, title, message):
        self.title = title
        self.message = message

class Filter(object):
    def __init__(self, db, value):
        self.db = db
        self.value = value
        self.check(db)
    def check(self, db):
        pass
    def filter(self, db, review):
        return True

class SummaryFilter(Filter):
    def contribute(self, query):
        query.conditions.append("reviews.summary LIKE %s")
        query.arguments.append(globToSQLPattern(self.value))

class DescriptionFilter(Filter):
    def contribute(self, query):
        query.conditions.append("reviews.description LIKE %s")
        query.arguments.append(globToSQLPattern(self.value))

class BranchFilter(Filter):
    def contribute(self, query):
        query.addTable("branches", "branches.id=reviews.branch")
        query.conditions.append("branches.name ~ %s")
        query.arguments.append(pathToSQLRegExp(self.value))

class PathFilter(Filter):
    def contribute(self, query):
        query.addTable("reviewfiles", "reviewfiles.review=reviews.id")
        query.addTable("files", "files.id=reviewfiles.file")

        if configuration.database.DRIVER == "postgresql":
            # This is just an optimization; with PostgreSQL we have an index
            # that avoids matching the pattern against most paths.

            static_components = []
            for component in self.value.split("/"):
                if component and not ("*" in component or "?" in component):
                    static_components.append(component)

            if static_components:
                query.conditions.append("%s <@ STRING_TO_ARRAY(path, '/')")
                query.arguments.append(static_components)

        query.conditions.append("files.path ~ %s")
        query.arguments.append(pathToSQLRegExp(self.value))

class UserFilter(Filter):
    def check(self, db):
        self.user = dbutils.User.fromName(db, self.value)
    def contribute(self, query):
        query.addTable("reviewusers", "reviewusers.review=reviews.id")
        query.conditions.append("reviewusers.uid=%s")
        query.arguments.append(self.user.id)

class OwnerFilter(UserFilter):
    def contribute(self, query):
        super(OwnerFilter, self).contribute(query)
        query.conditions.append("reviewusers.owner")

class ReviewerFilter(UserFilter):
    def contribute(self, query):
        query.addTable("reviewfiles", "reviewfiles.review=reviews.id")
        query.addTable("reviewuserfiles", "reviewuserfiles.file=reviewfiles.id")
        query.conditions.append("reviewuserfiles.uid=%s")
        query.arguments.append(self.user.id)

class StateFilter(Filter):
    def check(self, db):
        if self.value not in ("open", "pending", "accepted", "closed", "dropped"):
            raise InvalidFilter(
                title="Invalid review state: %r" % self.value,
                message=("Supported review states are open, pending, accepted, "
                         "closed and dropped."))
    def contribute(self, query):
        state = "open" if self.value in ("pending", "accepted") else self.value
        query.conditions.append("reviews.state=%s")
        query.arguments.append(state)
    def filter(self, db, review):
        if self.value == "pending":
            return not dbutils.Review.isAccepted(db, review.review_id)
        elif self.value == "accepted":
            return dbutils.Review.isAccepted(db, review.review_id)
        return True

class RepositoryFilter(Filter):
    def check(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT id FROM repositories WHERE name=%s", (self.value,))
        row = cursor.fetchone()
        if not row:
            raise gitutils.NoSuchRepository(self.value)
        self.repository_id = row[0]
    def contribute(self, query):
        query.addTable("branches", "branches.id=reviews.branch")
        query.conditions.append("branches.repository=%s")
        query.arguments.append(self.repository_id)

class OrFilter(Filter):
    def __init__(self, filters):
        self.filters = filters
    def contribute(self, query):
        conditions = []
        for search_filter in self.filters:
            subquery = Query(query)
            search_filter.contribute(subquery)
            conditions.append("(%s)" % " AND ".join(subquery.conditions))
        query.conditions.append("(%s)" % " OR ".join(conditions))

class SearchReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "query": str }, accept_anonymous_user=True)

    def process(req, db, user, query):
        terms = re.findall("""((?:"[^"]*"|'[^']*'|[^ "']+)+)""", query)
        url_terms = []
        filters = []

        for term in terms:
            if re.match("[a-z\-]+:", term):
                keyword, _, value = term.partition(":")

                url_terms.append(("q" + keyword, value))

                if keyword == "summary":
                    filter_classes = [SummaryFilter]
                elif keyword == "description":
                    filter_classes = [DescriptionFilter]
                elif keyword == "text":
                    filter_classes = [SummaryFilter, DescriptionFilter]
                elif keyword in ("branch", "b"):
                    filter_classes = [BranchFilter]
                elif keyword in ("path", "p"):
                    filter_classes = [PathFilter]
                elif keyword in ("user", "u"):
                    filter_classes = [UserFilter]
                elif keyword in ("owner", "o"):
                    filter_classes = [OwnerFilter]
                elif keyword == "reviewer":
                    filter_classes = [ReviewerFilter]
                elif keyword == "owner-or-reviewer":
                    filter_classes = [OwnerFilter, ReviewerFilter]
                elif keyword in ("state", "s"):
                    filter_classes = [StateFilter]
                elif keyword in ("repository", "repo", "r"):
                    filter_classes = [RepositoryFilter]
                else:
                    raise OperationFailure(
                        code="invalidkeyword",
                        title="Invalid keyword: %r" % keyword,
                        message=("Supported keywords are summary, description, "
                                 "text, branch, path, user, owner and reviewer."))

                if re.match("([\"']).*\\1$", value):
                    value = value[1:-1]

                try:
                    if len(filter_classes) > 1:
                        keyword_filters = [filter_class(db, value)
                                           for filter_class in filter_classes]
                        filters.append(OrFilter(keyword_filters))
                    else:
                        filters.append(filter_classes[0](db, value))

                except InvalidFilter as error:
                    raise OperationFailure(
                        code="invalidterm",
                        title=error.title,
                        message=error.message)
                except dbutils.NoSuchUser as error:
                    raise OperationFailure(
                        code="invalidterm",
                        title="No such user: %r" % error.name,
                        message=("The search term following %r must be a valid user name."
                                 % (keyword + ":")))
                except gitutils.NoSuchRepository as error:
                    raise OperationFailure(
                        code="invalidterm",
                        title="No such repository: %r" % error.name,
                        message=("The search term following %r must be a valid repository name."
                                 % (keyword + ":")))
            else:
                url_terms.append(("q", term))

                if re.match("([\"']).*\\1$", term):
                    term = term[1:-1]

                auto_filters = []
                auto_filters.append(SummaryFilter(db, term))
                auto_filters.append(DescriptionFilter(db, term))
                if not re.search(r"\s", term):
                    auto_filters.append(BranchFilter(db, term))
                    if re.search(r"\w/\w|\w\.\w+$", term):
                        auto_filters.append(PathFilter(db, term))

                filters.append(OrFilter(auto_filters))

        if not filters:
            raise OperationFailure(
                code="nofilters",
                title="No search filter specified",
                message="Your search would find all reviews.  Please restrict it a bit.")

        query_params = Query()

        for search_filter in filters:
            search_filter.contribute(query_params)

        query_string = """SELECT DISTINCT reviews.id, reviews.summary
                            FROM %s
                           WHERE %s
                        ORDER BY reviews.id DESC"""

        for conditions in query_params.tables.values():
            query_params.conditions[0:0] = conditions

        query = query_string % (", ".join(query_params.tables.keys()),
                                " AND ".join(query_params.conditions))

        cursor = db.cursor()
        cursor.execute(query, query_params.arguments)

        reviews = [Review(review_id, summary) for review_id, summary in cursor]

        for search_filter in filters:
            reviews = filter(lambda review: search_filter.filter(db, review), reviews)

        return OperationResult(
            reviews=list(map(Review.json, reviews)),
            query_string=urllib.parse.urlencode(url_terms))
