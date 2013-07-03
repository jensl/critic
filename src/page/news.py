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
import textformatting
import dbutils
import htmlutils
import configuration
import re

def renderNewsItem(db, user, target, text, timestamp):
    table = target.table("paleyellow", align="center")
    textformatting.renderFormatted(db, user, table, text.splitlines(), toc=False,
                                   title_right=timestamp)
    table.tr("back").td("back").div().a("back", href="news").text("Back")

def renderNewsItems(db, user, target, display_unread, display_read):
    target.setTitle("News")

    table = target.table("paleyellow", align="center")
    table.tr("h1").td("h1", colspan=3).h1().text("News")

    cursor = db.cursor()
    cursor.execute("""SELECT id, date, text, uid IS NULL
                        FROM newsitems
             LEFT OUTER JOIN newsread ON (item=id AND uid=%s)
                    ORDER BY date DESC, id DESC""",
                   (user.id,))

    nothing = True

    for item_id, date, text, unread in cursor:
        if (unread and display_unread) or (not unread and display_read):
            row = table.tr("item", critic_item_id=item_id)
            row.td("date").text(date)
            row.td("title").text(text.split("\n", 1)[0])
            row.td("status").text("unread" if unread else None)
            nothing = False

    if nothing:
        row = table.tr("nothing")
        row.td("nothing", colspan=3).text("No %s news!" % "unread" if display_unread else "read")

    if not display_unread or not display_read:
        table.tr("show").td("show", colspan=3).div().a("show", href="news?display=all").text("Show All")

def renderNews(req, db, user):
    item_id = req.getParameter("item", None, filter=int)
    display = req.getParameter("display", "unread")

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    cursor = db.cursor()

    def renderButtons(target):
        if user.hasRole(db, "newswriter"):
            if item_id is not None:
                target.button("editnewsitem").text("Edit Item")
            target.button("addnewsitem").text("Add News Item")

    page.utils.generateHeader(body, db, user, current_page="news", generate_right=renderButtons)

    document.addExternalStylesheet("resource/tutorial.css")
    document.addExternalStylesheet("resource/news.css")
    document.addExternalScript("resource/news.js")
    document.addInternalStylesheet("div.main table td.text { %s }" % user.getPreference(db, "style.tutorialFont"))

    target = body.div("main")

    if item_id:
        cursor.execute("SELECT text, date FROM newsitems WHERE id=%s", (item_id,))

        text, date = cursor.fetchone()

        document.addInternalScript("var news_item_id = %d;" % item_id)
        document.addInternalScript("var news_text = %s;" % htmlutils.jsify(text))

        renderNewsItem(db, user, target, text, date.isoformat())

        if not user.isAnonymous() and user.name == req.user:
            cursor.execute("SELECT 1 FROM newsread WHERE item=%s AND uid=%s", (item_id, user.id))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO newsread (item, uid) VALUES (%s, %s)", (item_id, user.id))
                db.commit()
    else:
        renderNewsItems(db, user, target, display in ("unread", "all"), display in ("read", "all"))

    return document

def addNewsItem(req, db, user):
    text = req.read()

    if not user.hasRole(db, "newswriter"):
        return "Sorry, you're not allowed to add news items."
    else:
        cursor = db.cursor()
        cursor.execute("INSERT INTO newsitems (text) VALUES (%s)", (text,))
        db.commit()
        return "ok"

def editNewsItem(req, db, user):
    item = req.getParameter("item", filter=int)
    text = req.read()

    if not user.hasRole(db, "newswriter"):
        return "Sorry, you're not allowed to add news items."
    else:
        cursor = db.cursor()
        cursor.execute("UPDATE newsitems SET text=%s WHERE id=%s", (text, item))
        db.commit()
        return "ok"
