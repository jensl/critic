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

import page.utils
import htmlutils
import dbutils

def renderStatistics(req, db, user):
    document = htmlutils.Document(req)
    document.setTitle("Statistics")

    html = document.html()
    head = html.head()
    body = html.body()

    def flush(stop):
        return document.render(stop=stop)

    page.utils.generateHeader(body, db, user, current_page="statistics")

    document.addExternalStylesheet("resource/statistics.css")

    table = body.div("main").table("paleyellow", align="center", cellspacing=0)

    def commas(number):
        as_string = str(number)
        if number >= 1000000000:
            as_string = as_string[:-9] + "," + as_string[-9:]
        if number >= 1000000:
            as_string = as_string[:-6] + "," + as_string[-6:]
        if number >= 1000:
            as_string = as_string[:-3] + "," + as_string[-3:]
        return as_string

    table.tr("h1").td("h1", colspan=4).h1().text("Most Lines Reviewed")
    table.tr("space").td(colspan=4)

    cursor = db.cursor()

    cursor.execute("CREATE TEMPORARY TABLE reviewers (uid INTEGER, lines INTEGER)")
    cursor.execute("INSERT INTO reviewers (uid, lines) SELECT reviewer, SUM(deleted) + SUM(inserted) FROM reviewfiles WHERE state='reviewed' GROUP BY reviewer")

    cursor.execute("SELECT uid, lines FROM reviewers ORDER BY lines DESC LIMIT 10")

    self_included = False
    for user_id, lines in cursor:
        if user_id == user.id:
            row = table.tr("line self")
            self_included = True
        else:
            row = table.tr("line")

        row.td("left")
        row.td("user").text(dbutils.User.fromId(db, user_id).fullname)
        row.td("value").text("%s lines" % commas(lines))
        row.td("right")

    if not self_included:
        cursor.execute("SELECT lines FROM reviewers WHERE uid=%s", (user.id,))

        data = cursor.fetchone()
        if data and data[0]:
            lines = data[0]

            cursor.execute("SELECT COUNT(*) + 1 FROM reviewers WHERE lines > %s", (lines,))

            table.tr("space").td(colspan=4)

            row = table.tr("line self extra")
            row.td("left")
            row.td("user").text(user.fullname)
            row.td("value").innerHTML("%s lines" % commas(lines))
            row.td("right").text("(your position: %d)" % cursor.fetchone()[0])

    table.tr("space").td(colspan=4)
    table.tr("space").td(colspan=4)

    table.tr("h1").td("h1", colspan=4).h1().text("Most Lines in Owned Reviews")
    table.tr("space").td(colspan=4)

    cursor.execute("CREATE TEMPORARY TABLE owners (uid INTEGER, lines INTEGER)")
    cursor.execute("INSERT INTO owners (uid, lines) SELECT uid, SUM(deleted) + SUM(inserted) FROM reviewfiles JOIN reviewusers USING (review) JOIN reviews ON (reviewfiles.review=reviews.id) WHERE reviews.state IN ('open', 'closed') AND reviewusers.owner GROUP BY uid")

    cursor.execute("SELECT uid, lines FROM owners ORDER BY lines DESC LIMIT 10")

    self_included = False
    for user_id, lines in cursor:
        if user_id == user.id:
            row = table.tr("line self")
            self_included = True
        else:
            row = table.tr("line")

        row.td("left")
        row.td("user").text(dbutils.User.fromId(db, user_id).fullname)
        row.td("value").innerHTML("%s lines" % commas(lines))
        row.td("right")

    if not self_included:
        cursor.execute("SELECT lines FROM owners WHERE uid=%s", (user.id,))

        data = cursor.fetchone()
        if data and data[0]:
            lines = data[0]

            cursor.execute("SELECT COUNT(*) + 1 FROM owners WHERE lines > %s", (lines,))

            table.tr("space").td(colspan=4)

            row = table.tr("line self extra")
            row.td("left")
            row.td("user").text(user.fullname)
            row.td("value").innerHTML("%s lines" % commas(lines))
            row.td("right").text("(your position: %d)" % cursor.fetchone()[0])

    table.tr("space").td(colspan=4)
    table.tr("space").td(colspan=4)

    table.tr("h1").td("h1", colspan=4).h1().text("Most Issues Raised")
    table.tr("space").td(colspan=4)

    cursor.execute("""SELECT uid, COUNT(type) AS issues
                        FROM commentchains
                       WHERE state IN ('open', 'addressed', 'closed')
                         AND type='issue'
                    GROUP BY uid
                    ORDER BY issues DESC
                       LIMIT 10""")

    def calculateRatio(user_id, issues):
        cursor.execute("""SELECT lines FROM reviewers WHERE uid=%s""", (user_id,))

        row = cursor.fetchone()
        lines = row[0] if row else 0

        return float(issues * 1000) / float(lines) if lines else 0

    self_included = False
    for user_id, issues in cursor.fetchall():
        if user_id == user.id:
            row = table.tr("line self")
            self_included = True
        else:
            row = table.tr("line")

        row.td("left")
        row.td("user").text(dbutils.User.fromId(db, user_id).fullname)
        row.td("value").text("%s issues" % commas(issues))

        ratio = "%.2f" % calculateRatio(user_id, issues)

        if ratio != "0.00": row.td("right").text("(%s issues/kloc)" % ratio)
        else: row.td("right")

    if not self_included:
        cursor.execute("""SELECT COUNT(type)
                            FROM commentchains
                           WHERE state IN ('open', 'addressed', 'closed')
                             AND type='issue'
                             AND uid=%s""",
                       (user.id,))

        data = cursor.fetchone()
        if data and data[0]:
            issues = data[0]

            cursor.execute("""SELECT count(*) + 1
                                FROM (SELECT uid, COUNT(type) AS issues
                                        FROM commentchains
                                       WHERE state IN ('open', 'addressed', 'closed')
                                         AND type='issue'
                                    GROUP BY uid
                                    ORDER BY issues DESC) AS stats
                               WHERE stats.issues > %s""",
                           (issues,))

            table.tr("space").td(colspan=4)

            row = table.tr("line self extra")
            row.td("left")
            row.td("user").text(user.fullname)
            row.td("value").innerHTML("%s issues" % commas(issues))

            right = row.td("right")
            right.text("(your position: %d)" % cursor.fetchone()[0])

            ratio = "%.2f" % calculateRatio(user.id, issues)
            if ratio != "0.00": right.text(" (%s issues/kloc)" % ratio)

    table.tr("space").td(colspan=4)
    table.tr("space").td(colspan=4)

    table.tr("h1").td("h1", colspan=4).h1().text("Most Comments (and Replies) Written")
    table.tr("space").td(colspan=4)

    cursor.execute("""SELECT uid, COUNT(state) AS comments
                        FROM comments
                       WHERE state='current'
                    GROUP BY uid
                    ORDER BY comments DESC
                       LIMIT 10""")

    self_included = False
    for user_id, comments in cursor:
        if user_id == user.id:
            row = table.tr("line self")
            self_included = True
        else:
            row = table.tr("line")

        row.td("left")
        row.td("user").text(dbutils.User.fromId(db, user_id).fullname)
        row.td("value").innerHTML("%s comments" % commas(comments))
        row.td("right")

    if not self_included:
        cursor.execute("""SELECT COUNT(state)
                            FROM comments
                           WHERE state='current'
                             AND uid=%s""",
                       (user.id,))

        data = cursor.fetchone()
        if data and data[0]:
            issues = data[0]

            cursor.execute("""SELECT count(*) + 1
                                FROM (SELECT uid, COUNT(state) AS comments
                                        FROM comments
                                       WHERE state='current'
                                    GROUP BY uid
                                    ORDER BY comments DESC) AS stats
                               WHERE stats.comments > %s""",
                           (issues,))

            table.tr("space").td(colspan=4)

            row = table.tr("line self extra")
            row.td("left")
            row.td("user").text(user.fullname)
            row.td("value").innerHTML("%s comments" % commas(issues))
            row.td("right").text("(your position: %d)" % cursor.fetchone()[0])

    table.tr("space").td(colspan=4)
    table.tr("space").td(colspan=4)

    table.tr("h1").td("h1", colspan=4).h1().text("Most Characters Written")
    table.tr("space").td(colspan=4)

    cursor.execute("""SELECT uid, SUM(CHARACTER_LENGTH(comment)) AS characters
                        FROM comments
                       WHERE state='current'
                    GROUP BY uid
                    ORDER BY characters DESC
                       LIMIT 10""")

    self_included = False
    for user_id, characters in cursor:
        if user_id == user.id:
            row = table.tr("line self")
            self_included = True
        else:
            row = table.tr("line")

        row.td("left")
        row.td("user").text(dbutils.User.fromId(db, user_id).fullname)
        row.td("value").innerHTML("%s characters" % commas(characters))
        row.td("right")

    if not self_included:
        cursor.execute("""SELECT SUM(CHARACTER_LENGTH(comment))
                            FROM comments
                           WHERE state='current'
                             AND uid=%s""",
                       (user.id,))

        data = cursor.fetchone()
        if data and data[0]:
            characters = data[0]

            cursor.execute("""SELECT count(*) + 1
                                FROM (SELECT uid, SUM(CHARACTER_LENGTH(comment)) AS characters
                                        FROM comments
                                       WHERE state='current'
                                    GROUP BY uid
                                    ORDER BY characters DESC) AS stats
                               WHERE stats.characters > %s""",
                           (characters,))

            table.tr("space").td(colspan=4)

            row = table.tr("line self extra")
            row.td("left")
            row.td("user").text(user.fullname)
            row.td("value").innerHTML("%s characters" % commas(characters))
            row.td("right").text("(your position: %d)" % cursor.fetchone()[0])

    db.rollback()

    return document
