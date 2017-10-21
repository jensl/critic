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
import fnmatch

import configuration
import dbutils
import gitutils
import htmlutils
import textutils
import page.utils

def renderConfig(req, db, user):
    highlight = req.getParameter("highlight", None)
    repository = req.getParameter("repository", None, gitutils.Repository.FromParameter(db))
    filter_id = req.getParameter("filter", None, int)
    defaults = req.getParameter("defaults", "no") == "yes"

    if filter_id is not None:
        # There can't be system-wide defaults for one of a single user's
        # filters.
        defaults = False

    cursor = db.cursor()

    if filter_id is not None:
        cursor.execute("""SELECT filters.path, repositories.name
                            FROM filters
                            JOIN repositories ON (repositories.id=filters.repository)
                           WHERE filters.id=%s""",
                       (filter_id,))
        row = cursor.fetchone()
        if not row:
            raise page.utils.InvalidParameterValue(
                name="filter",
                value=str(filter_id),
                expected="valid filter id")
        title = "Filter preferences: %s in %s" % row
    elif repository is not None:
        title = "Repository preferences: %s" % repository.name
    else:
        title = "User preferences"

    document = htmlutils.Document(req)
    document.setTitle(title)

    html = document.html()
    head = html.head()
    body = html.body()

    if user.isAnonymous():
        disabled = "disabled"
    else:
        disabled = None

    def generate_right(target):
        if defaults:
            url = "/config"
            if repository is not None:
                url += "?repository=%d" % repository.id
            target.a("button", href=url).text("Edit Own")
        elif user.hasRole(db, "administrator"):
            url = "/config?defaults=yes"
            if repository is not None:
                url += "&repository=%d" % repository.id
                what = "Repository Defaults"
            else:
                what = "System Defaults"
            target.a("button", href=url).text("Edit " + what)

    injected = page.utils.generateHeader(body, db, user, current_page="config",
                                         generate_right=generate_right)

    document.addExternalStylesheet("resource/config.css")
    document.addExternalScript("resource/config.js")
    document.addInternalScript(user.getJS())
    document.addInternalScript("var repository_id = %s, filter_id = %s, defaults = %s;"
                               % (htmlutils.jsify(repository.id if repository else None),
                                  htmlutils.jsify(filter_id),
                                  htmlutils.jsify(defaults)))

    target = body.div("main")

    table = target.table('preferences paleyellow', align='center', cellspacing=0)
    h1 = table.tr().td('h1', colspan=3).h1()
    h1.text(title)

    if filter_id is None:
        page.utils.generateRepositorySelect(
            db, user, h1.span("right"), allow_selecting_none=True,
            selected=repository.name if repository else False)

    if filter_id is not None:
        conditional = "per_filter"
    elif repository is not None:
        conditional = "per_repository"
    elif defaults:
        conditional = "per_system"
    else:
        conditional = "per_user"

    cursor = db.cursor()
    cursor.execute("""SELECT item, type, description, per_repository, per_filter
                        FROM preferences
                       WHERE %(conditional)s"""
                   % { "conditional": conditional })

    preferences = dict((item, [preference_type, description, None, None, per_repository, per_filter])
                       for item, preference_type, description, per_repository, per_filter in cursor)

    def set_values(rows, is_overrides):
        index = 3 if is_overrides else 2
        for item, integer, string in rows:
            if preferences[item][0] == "boolean":
                preferences[item][index] = bool(integer)
            elif preferences[item][0] == "integer":
                preferences[item][index] = integer
            else:
                preferences[item][index] = string

    cursor.execute("""SELECT item, integer, string
                        FROM userpreferences
                       WHERE item=ANY (%s)
                         AND uid IS NULL
                         AND repository IS NULL""",
                   (list(preferences.keys()),))

    set_values(cursor, is_overrides=False)

    if repository is not None:
        cursor.execute("""SELECT item, integer, string
                            FROM userpreferences
                           WHERE item=ANY (%s)
                             AND uid IS NULL
                             AND repository=%s""",
                       (list(preferences.keys()), repository.id))

        # These are overrides if we're editing the defaults for a specific
        # repository.
        set_values(cursor, is_overrides=defaults)

    if not defaults:
        cursor.execute("""SELECT item, integer, string
                            FROM userpreferences
                           WHERE item=ANY (%s)
                             AND uid=%s
                             AND repository IS NULL
                             AND filter IS NULL""",
                       (list(preferences.keys()), user.id))

        if filter_id is not None or repository is not None:
            # We're looking at per-filter or per-repository settings, so the
            # user's global settings are defaults, not the overrides.  If a
            # per-filter or per-repository override is deleted, the user's
            # global setting kicks in instead.
            set_values(cursor, is_overrides=False)

            if filter_id is not None:
                cursor.execute("""SELECT item, integer, string
                                    FROM userpreferences
                                   WHERE item=ANY (%s)
                                     AND uid=%s
                                     AND filter=%s""",
                               (list(preferences.keys()), user.id, filter_id))
            else:
                cursor.execute("""SELECT item, integer, string
                                    FROM userpreferences
                                   WHERE item=ANY (%s)
                                     AND uid=%s
                                     AND repository=%s""",
                               (list(preferences.keys()), user.id, repository.id))

        # Set the overrides.  This is either the user's global settings, if
        # we're not looking at per-filter or per-repository settings, or the
        # user's per-filter or per-repository settings if we are.
        set_values(cursor, is_overrides=True)
    elif repository is None:
        # When editing global defaults, use the values from preferences.json
        # used when initially installing Critic as the default values.
        defaults_path = os.path.join(configuration.paths.INSTALL_DIR,
                                     "data/preferences.json")
        with open(defaults_path) as defaults_file:
            factory_defaults = textutils.json_decode(defaults_file.read())
        for item, data in preferences.items():
            data[3] = data[2]
            if item in factory_defaults:
                data[2] = factory_defaults[item]["default"]
                if data[2] == data[3]:
                    data[3] = None

    if req.getParameter("recalculate", "no") == "yes":
        for item, data in preferences.items():
            if data[2] == data[3]:
                user.setPreference(db, item, None, repository=repository, filter_id=filter_id)
                data[3] = None
        db.commit()

    debug_enabled = user.getPreference(db, "debug.enabled")

    for item, (preference_type, description, default_value, current_value, per_repository, per_filter) in sorted(preferences.items()):
        if item.startswith("debug.") and item != "debug.enabled" and not debug_enabled:
            continue

        line_class_name = "line"
        help_class_name = "help"

        if highlight is not None and not fnmatch.fnmatch(item, highlight):
            continue

        if current_value is None:
            current_value = default_value
        else:
            line_class_name += " customized"

        row = table.tr(line_class_name)
        heading = row.td("heading")
        heading.text("%s:" % item)
        value = row.td("value", colspan=2)
        value.preformatted()

        options = None
        optgroup = None
        def addOption(value, name, selected=lambda value: value==current_value, **attributes):
            (optgroup or options).option(
                value=value, selected="selected" if selected(value) else None,
                **attributes).text(name)

        if preference_type == "boolean":
            value.input(
                "setting", type="checkbox", name=item,
                checked="checked" if current_value else None, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))
        elif preference_type == "integer":
            value.input(
                "setting", type="number", min=0, max=2**31 - 1,
                name=item, value=current_value, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))
        elif item == "defaultRepository":
            page.utils.generateRepositorySelect(
                db, user, value, allow_selecting_none=True,
                placeholder_text="No default repository", selected=current_value,
                name=item, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))
        elif item == "defaultPage":
            options = value.select(
                "setting", name=item, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))

            addOption("home", "Home")
            addOption("dashboard", "Dashboard")
            addOption("branches", "Branches")
            addOption("config", "Config")
            addOption("tutorial", "Tutorial")
        elif item == "email.urlType":
            cursor2 = db.cursor()
            cursor2.execute("""SELECT key, description, authenticated_scheme, hostname
                                 FROM systemidentities
                             ORDER BY description ASC""")

            identities = cursor2.fetchall()
            selected = set(current_value.split(","))

            options = value.select(
                "setting", name=item, size=len(identities),
                multiple="multiple", disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))

            for key, label, authenticated_scheme, hostname in identities:
                prefix = "%s://%s/" % (authenticated_scheme, hostname)
                addOption(key, label, selected=lambda value: value in selected,
                          class_="url-type flex",
                          data_text=label,
                          data_html=("<span class=label>%s</span>"
                                     "<span class=prefix>%s</span>"
                                     % (htmlutils.htmlify(label),
                                        htmlutils.htmlify(prefix))))

        elif item == "email.updatedReview.quotedComments":
            options = value.select(
                "setting", name=item, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))

            addOption("all", "All")
            addOption("first", "First")
            addOption("last", "Last")
            addOption("firstlast", "First & Last")
        elif item == "timezone":
            options = value.select(
                "setting", name=item, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))

            for group, zones in dbutils.timezones.sortedTimezones(db):
                optgroup = options.optgroup(label=group)
                for name, abbrev, utc_offset in zones:
                    seconds = utc_offset.total_seconds()
                    offset = "%s%02d:%02d" % ("-" if seconds < 0 else "+", abs(seconds) / 3600, (abs(seconds) % 3600) / 60)
                    addOption("%s/%s" % (group, name), "%s (%s / UTC%s)" % (name, abbrev, offset))
        elif item == "repository.urlType":
            options = value.select(
                "setting", name=item, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))
            long_path = os.path.join(configuration.paths.GIT_DIR, "<path>.git")

            if "git" in configuration.base.REPOSITORY_URL_TYPES:
                addOption("git", "git://%s/<path>.git" % configuration.base.HOSTNAME)
            if "http" in configuration.base.REPOSITORY_URL_TYPES:
                scheme = configuration.base.ACCESS_SCHEME
                if scheme == "both":
                    if user.isAnonymous():
                        scheme = "http"
                    else:
                        scheme = "https"
                addOption("http", "%s://%s/<path>.git" % (scheme, configuration.base.HOSTNAME))
            if "ssh" in configuration.base.REPOSITORY_URL_TYPES:
                addOption("ssh", "ssh://%s%s" % (configuration.base.HOSTNAME, long_path))
            if "host" in configuration.base.REPOSITORY_URL_TYPES:
                addOption("host", "%s:%s" % (configuration.base.HOSTNAME, long_path))
        else:
            if item.startswith("email.subjectLine."):
                placeholder = "Email type disabled"
            else:
                placeholder = None
            value.input(
                "setting", type="text", size=80, name=item,
                placeholder=placeholder, value=current_value, disabled=disabled,
                critic_current=htmlutils.jsify(current_value),
                critic_default=htmlutils.jsify(default_value))

        also_configurable_per = []

        if per_repository and repository is None:
            also_configurable_per.append("repository")
        if per_filter and filter_id is None:
            also_configurable_per.append("filter")

        if also_configurable_per:
            value.span("also-configurable-per").text(
                "Also configurable per: %s" % ", ".join(also_configurable_per))

        reset = value.span("reset")
        reset.a(href="javascript:saveSettings(%s);" % htmlutils.jsify(item)).text("[reset to default]")

        cell = table.tr(help_class_name).td("help", colspan=3)

        magic_description_links = {
            "format string for subject line":
                "/tutorial?item=reconfigure#subject_line_formats",
            "phony recipients":
                "/tutorial?item=reconfigure#review_association_recipients"
            }

        for link_text, link_href in magic_description_links.items():
            prefix, link_text, suffix = description.partition(link_text)
            if link_text:
                cell.text(prefix)
                cell.a(href=link_href).text(link_text)
                cell.text(suffix)
                break
        else:
            cell.text(description)

    if injected and "preferences" in injected \
            and not defaults \
            and repository is None \
            and filter_id is None:
        for extension_name, author, preferences in injected["preferences"]:
            if highlight is not None:
                prefix = "%s/%s" % (author.name, extension_name)
                preferences = [
                    preference for preference in preferences
                    if fnmatch.fnmatch("%s/%s" % (prefix, preference["name"]),
                                       highlight)]

                if not preferences:
                    continue

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

                if preference_value != preference_default:
                    line_class_name += " customized"

                row = table.tr(line_class_name)
                heading = row.td("heading")
                heading.text("%s:" % preference_name)
                value = row.td("value", colspan=2)
                value.preformatted()

                if preference_type == "boolean":
                    value.input(
                        "setting", type="checkbox",
                        name=preference_name, disabled=disabled,
                        checked="checked" if preference_value else None,
                        critic_url=preference_url,
                        critic_default=htmlutils.jsify(bool(preference_value)),
                        critic_extension=extension_name)
                elif preference_type == "integer":
                    value.input(
                        "setting", type="number", min=0,
                        name=preference_name, value=preference_value,
                        disabled=disabled, critic_url=preference_url,
                        critic_default=htmlutils.jsify(preference_default),
                        critic_extension=extension_name)
                elif preference_type == "string":
                    value.input(
                        "setting", type="text",
                        name=preference_name, value=preference_value,
                        disabled=disabled, critic_url=preference_url,
                        critic_default=htmlutils.jsify(preference_default),
                        critic_extension=extension_name)
                else:
                    select = value.select(
                        "setting", name=preference_name,
                        disabled=disabled, critic_url=preference_url,
                        critic_value=preference_value,
                        critic_default=htmlutils.jsify(preference_default),
                        critic_extension=extension_name)

                    for choice in preference_type:
                        select.option(value=choice["value"], selected="selected" if preference_value == choice["value"] else None).text(choice["title"])

                cell = table.tr(help_class_name).td("help", colspan=3)
                cell.text(preference_description)

    critic_installed_sha1 = dbutils.getInstalledSHA1(db)
    div = body.div("installed_sha1")
    div.text("Critic version: ")
    div.a(href="https://critic-review.org/critic/%s" % critic_installed_sha1).text(critic_installed_sha1)

    return document
