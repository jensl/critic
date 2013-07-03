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

import os

import dbutils
import htmlutils
import page.utils
import configuration

def renderConfig(req, db, user):
    highlight = req.getParameter("highlight", None)

    cursor = db.cursor()

    document = htmlutils.Document(req)
    document.setTitle("User Preferences")

    html = document.html()
    head = html.head()
    body = html.body()

    def renderRight(target):
        if not user.isAnonymous():
            target.button(onclick='saveSettings();').text('Save Settings')

    injected = page.utils.generateHeader(body, db, user, generate_right=renderRight, current_page="config")

    document.addExternalStylesheet("resource/config.css")
    document.addExternalScript("resource/config.js")
    document.addInternalScript(user.getJS())

    target = body.div("main")

    table = target.table('preferences paleyellow', align='center', cellspacing=0)
    table.tr().td('h1', colspan=3).h1().text("User Preferences")

    cursor = db.cursor()
    cursor.execute("""SELECT preferences.item, type,
                             integer, default_integer,
                             string, default_string,
                             description
                        FROM preferences
             LEFT OUTER JOIN userpreferences
                          ON (preferences.item=userpreferences.item AND uid=%s)
                    ORDER BY preferences.item ASC""",
                   [user.id])

    debug_enabled = user.getPreference(db, "debug.enabled")

    if highlight:
        document.addInternalScript("$(document).ready(function () { location.hash = 'go'; $('#highlight').focus().select(); });")

    for item, type, integer, default_integer, string, default_string, description in cursor:
        if item.startswith("debug.") and item != "debug.enabled" and not debug_enabled:
            continue

        line_class_name = "line"
        help_class_name = "help"

        highlight_this = highlight == item
        if highlight_this:
            line_class_name += " highlight"
            help_class_name += " highlight"
            input_id = "highlight"
        else:
            input_id = None

        if (integer is None or integer == default_integer) and (string is None or string == default_string):
            line_class_name += " default"
            integer = default_integer
            string = default_string
        else:
            line_class_name += " customized"

        row = table.tr(line_class_name)
        heading = row.td("heading")
        if highlight_this: heading = heading.a(name="go")
        heading.text("%s:" % item)
        value = row.td("value", colspan=2)
        value.preformatted()

        options = None
        optgroup = None
        def addOption(value, name, selected=lambda value: string==value):
            (optgroup or options).option(value=value, selected="selected" if selected(value) else None).text(name)

        if type == "boolean":
            value.input("setting", id=input_id, type="checkbox", name=item, checked=integer and "checked" or None, critic_default=default_integer)
        elif type == "integer":
            value.input("setting", id=input_id, type="number", min=0, name=item, value=integer, critic_default=default_integer)
        elif item == "defaultRepository":
            options = value.select("setting", id=input_id, name=item, critic_default=default_string)

            cursor2 = db.cursor()
            cursor2.execute("SELECT name FROM repositories ORDER BY id ASC")
            for (name,) in cursor2:
                addOption(name, name)
        elif item == "defaultPage":
            options = value.select("setting", id=input_id, name=item, critic_default=default_string)

            addOption("home", "Home")
            addOption("dashboard", "Dashboard")
            addOption("branches", "Branches")
            addOption("config", "Config")
            addOption("tutorial", "Tutorial")
        elif item == "email.urlType":
            cursor2 = db.cursor()
            cursor2.execute("SELECT key, description FROM systemidentities")

            identities = cursor2.fetchall()
            selected = set(string.split(","))

            options = value.select("setting", id=input_id, name=item, size=len(identities), multiple="multiple", critic_default=default_string)

            for key, description in identities:
                addOption(key, description, selected=lambda value: value in selected)
        elif item == "email.updatedReview.quotedComments":
            options = value.select("setting", id=input_id, name=item, critic_default=default_string)

            addOption("all", "All")
            addOption("first", "First")
            addOption("last", "Last")
            addOption("firstlast", "First & Last")
        elif item == "timezone":
            options = value.select("setting", id=input_id, name=item, critic_default=default_string)

            for group, zones in dbutils.timezones.sortedTimezones(db):
                optgroup = options.optgroup(label=group)
                for name, abbrev, utc_offset in zones:
                    seconds = utc_offset.total_seconds()
                    offset = "%s%02d:%02d" % ("-" if seconds < 0 else "+", abs(seconds) / 3600, (abs(seconds) % 3600) / 60)
                    addOption("%s/%s" % (group, name), "%s (%s / UTC%s)" % (name, abbrev, offset))
        elif item == "repository.urlType":
            options = value.select("setting", id=input_id, name=item, critic_default=default_string)
            long_path = os.path.join(configuration.paths.GIT_DIR, "<path>.git")

            if "git" in configuration.base.REPOSITORY_URL_TYPES:
                addOption("git", "git://%s/<path>.git" % configuration.base.HOSTNAME)
            if "http" in configuration.base.REPOSITORY_URL_TYPES:
                addOption("http", "http://%s/<path>.git" % configuration.base.HOSTNAME)
            if "ssh" in configuration.base.REPOSITORY_URL_TYPES:
                addOption("ssh", "ssh://%s%s" % (configuration.base.HOSTNAME, long_path))
            if "host" in configuration.base.REPOSITORY_URL_TYPES:
                addOption("host", "%s:%s" % (configuration.base.HOSTNAME, long_path))
        else:
            value.input("setting", id=input_id, type="text", size=80, name=item, value=string, critic_default=default_string)

        cell = table.tr(help_class_name).td("help", colspan=3)

        index = description.find("format string for subject line")
        if index != -1:
            cell.text(description[:index])
            cell.a(href="/tutorial?item=reconfigure#subject_line_formats").text("format string for subject line")
            cell.text(description[index + len("format string for subject line"):])
        else:
            cell.text(description)

    if injected and injected.has_key("preferences"):
        for extension_name, author, preferences in injected["preferences"]:
            h2 = table.tr("extension").td("extension", colspan=3).h2()
            h2.span("name").text(extension_name)
            h2.text(" by ")
            h2.span("author").text(author.fullname)

            for preference in preferences:
                preference_url = preference["url"]
                preference_name = preference["name"]
                preference_type = preference["type"]
                preference_value = preference["value"]
                preference_default = preference["default"]
                preference_description = preference["description"]

                line_class_name = "line"
                help_class_name = "help"

                highlight_this = highlight == ("%s/%s/%s" % (author.name, extension_name, preference_name))
                if highlight_this:
                    line_class_name += " highlight"
                    help_class_name += " highlight"
                    input_id = "highlight"
                else:
                    input_id = None

                row = table.tr(line_class_name)
                heading = row.td("heading")
                if highlight_this: heading = heading.a(name="go")
                heading.text("%s:" % preference_name)
                value = row.td("value", colspan=2)
                value.preformatted()

                if preference_type == "boolean":
                    value.input("setting", id=input_id, critic_url=preference_url, type="checkbox", name=preference_name, checked="checked" if preference_value else None, critic_default=1 if preference_value else 0, critic_extension=extension_name)
                elif preference_type == "integer":
                    value.input("setting", id=input_id, critic_url=preference_url, type="number", min=0, name=preference_name, value=preference_value, critic_default=preference_default, critic_extension=extension_name)
                elif preference_type == "string":
                    value.input("setting", id=input_id, critic_url=preference_url, type="text", name=preference_name, value=preference_value, critic_default=preference_default, critic_extension=extension_name)
                else:
                    select = value.select("setting", id=input_id, critic_url=preference_url, name=preference_name, critic_value=preference_value, critic_extension=extension_name)
                    for choice in preference_type:
                        select.option(value=choice["value"], selected="selected" if preference_value == choice["value"] else None).text(choice["title"])

                cell = table.tr(help_class_name).td("help", colspan=3)
                cell.text(preference_description)

    cursor = db.cursor()
    cursor.execute("SELECT installed_sha1 FROM systemidentities WHERE name=%s", (configuration.base.SYSTEM_IDENTITY,))
    critic_installed_sha1 = cursor.fetchone()[0]
    div = document.div("installed_sha1")
    div.text("Critic version: ")
    div.a(href="http://critic-review.org/critic/%s" % critic_installed_sha1).text(critic_installed_sha1)

    return document
