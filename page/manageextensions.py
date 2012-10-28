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

import extensions
import page.utils
import htmlutils
import dbutils
import configuration

def renderManageExtensions(req, db, user):
    cursor = db.cursor()

    what = page.utils.getParameter(req, "what", "available")
    selected_versions = page.utils.json_decode(page.utils.getParameter(req, "select", "{}"))
    focused = page.utils.getParameter(req, "focus", None)

    if what == "available":
        title = "Available Extensions"
        other = ("installed extensions", "/manageextensions?what=installed" + ("&user=" + user.name if user.name != req.user else ""))
        listed_extensions = extensions.findExtensions()
    elif what == "installed":
        title = "Installed Extensions"
        other = ("available extensions", "/manageextensions?what=available" + ("&user=" + user.name if user.name != req.user else ""))
        cursor.execute("""SELECT DISTINCT users.name, extensions.name
                            FROM users
                            JOIN extensions ON (extensions.author=users.id)
                            JOIN extensionversions ON (extensionversions.extension=extensions.id)
                 LEFT OUTER JOIN extensionroles_page ON (extensionroles_page.version=extensionversions.id AND extensionroles_page.uid=%s)
                 LEFT OUTER JOIN extensionroles_processcommits ON (extensionroles_processcommits.version=extensionversions.id AND extensionroles_processcommits.uid=%s)
                           WHERE extensionroles_page.uid IS NOT NULL
                              OR extensionroles_processcommits.uid IS NOT NULL""",
                       (user.id, user.id))
        listed_extensions = [extensions.Extension(*row) for row in cursor]

    req.content_type = "text/html; charset=utf-8"

    document = htmlutils.Document(req)
    document.setTitle("Manage Extensions")

    html = document.html()
    head = html.head()
    body = html.body()

    def generateRight(target):
        target.a("button", href="tutorial?item=extensions").text("Tutorial")
        target.text(" ")
        target.a("button", href="tutorial?item=extensions-api").text("API Documentation")

    page.utils.generateHeader(body, db, user, current_page="extensions", generate_right=generateRight)

    document.addExternalStylesheet("resource/manageextensions.css")
    document.addExternalScript("resource/manageextensions.js")
    document.addInternalScript(user.getJS())

    table = page.utils.PaleYellowTable(body, title)
    table.titleRight.a(href=other[1]).text("[" + other[0] + "]")

    for extension in listed_extensions:
        extension_path = extension.getPath()
        author = dbutils.User.fromName(db, extension.getAuthorName())

        if focused and extension.getKey() != focused:
            continue

        selected_version = selected_versions.get(extension.getKey(), False)
        installed_sha1, installed_version = extension.getInstalledVersion(db, user)

        if selected_version is False:
            selected_version = installed_version

        if selected_version is None: install_version = "live"
        elif selected_version is not False: install_version = "version/%s" % selected_version
        else: install_version = None

        try:
            if selected_version is False:
                manifest = extension.readManifest()
            else:
                manifest = extension.getInstallationStatus(db, user, selected_version)
        except Exception, e:
            manifest = None

        if installed_sha1:
            current_sha1 = extension.getCurrentSHA1(installed_version)

        if manifest:
            if what == "available" and author != user and manifest.hidden: continue
        else:
            if author != user: continue

        if manifest:
            buttons = []

            if installed_version is False:
                if install_version:
                    buttons.append(("Install", "installExtension(%s, %s, %s)" % (htmlutils.jsify(extension.getAuthorName()), htmlutils.jsify(extension.getName()), htmlutils.jsify(install_version))))
            else:
                buttons.append(("Uninstall", "uninstallExtension(%s, %s)" % (htmlutils.jsify(extension.getAuthorName()), htmlutils.jsify(extension.getName()))))

                if installed_sha1 and installed_sha1 != current_sha1: label = "Update"
                elif manifest.status != "installed": label = "Reinstall"
                else: label = None

                if label: buttons.append((label, "reinstallExtension(%s, %s, %s)" % (htmlutils.jsify(extension.getAuthorName()), htmlutils.jsify(extension.getName()), htmlutils.jsify(install_version))))
        else:
            buttons = None

        def renderItem(target):
            span = target.span("name")
            span.b().text(extension.getName())
            span.text(" by %s" % author.fullname)

            span = target.span("details")
            span.b().text("Details: ")
            select = span.select("details", critic_author=extension.getAuthorName(), critic_extension=extension.getName())
            select.option(value='', selected="selected" if selected_version is False else None).text("Select version")
            versions = extension.getVersions()
            if versions:
                optgroup = select.optgroup(label="Official Versions")
                for version in extension.getVersions():
                    optgroup.option(value="version/%s" % version, selected="selected" if selected_version == version else None).text("%s" % version.upper())
            optgroup = select.optgroup(label="Development")
            optgroup.option(value='live', selected="selected" if selected_version is None else None).text("LIVE")

            if manifest:
                is_installed = manifest.status in ("partial", "installed") or installed_version is not False

                if is_installed:
                    target.span("installed").text(" [installed]")

                target.div("description").preformatted().text(manifest.description)
            else:
                is_installed = False

                target.div("description broken").preformatted().a(href="loadmanifest?author=%s&name=%s" % (extension.getAuthorName(), extension.getName())).text("[This extension has an invalid MANIFEST file]")

            if selected_version is False:
                return

            pages = []
            injects = []
            processcommits = []
            processchanges = []

            if manifest:
                for role in manifest.roles:
                    if isinstance(role, extensions.PageRole): pages.append(role)
                    elif isinstance(role, extensions.InjectRole): injects.append(role)
                    elif isinstance(role, extensions.ProcessCommitsRole): processcommits.append(role)
                    elif isinstance(role, extensions.ProcessChangesRole): processchanges.append(role)

            role_table = target.table("roles")

            if pages:
                role_table.tr().th(colspan=2).text("Pages")

                for role in pages:
                    row = role_table.tr()
                    row.td("pattern").text("%s/%s" % (dbutils.getURLPrefix(db), role.pattern))
                    td = row.td("description")
                    td.text(role.description)

                    if is_installed and not role.installed:
                        td.text(" ")
                        td.span("inactive").text("[Not active!]")

            if injects:
                role_table.tr().th(colspan=2).text("Page Injections")

                for role in injects:
                    row = role_table.tr()
                    row.td("pattern").text("%s/%s" % (dbutils.getURLPrefix(db), role.pattern))
                    td = row.td("description")
                    td.text(role.description)

                    if is_installed and not role.installed:
                        td.text(" ")
                        td.span("inactive").text("[Not active!]")

            if processcommits:
                role_table.tr().th(colspan=2).text("ProcessCommits hooks")
                ul = role_table.tr().td(colspan=2).ul()

                for role in processcommits:
                    li = ul.li()
                    li.text(role.description)

                    if is_installed and not role.installed:
                        li.text(" ")
                        li.span("inactive").text("[Not active!]")

            if processchanges:
                role_table.tr().th(colspan=2).text("ProcessChanges hooks")
                ul = role_table.tr().td(colspan=2).ul()

                for role in processchanges:
                    li = ul.li()
                    li.text(role.description)

                    if is_installed and not role.installed:
                        li.text(" ")
                        li.span("inactive").text("[Not active!]")

        cursor.execute("""SELECT DISTINCT uid
                            FROM extensionroles
                            JOIN extensionversions ON (extensionversions.id=extensionroles.version)
                            JOIN extensions ON (extensions.id=extensionversions.extension)
                           WHERE extensions.author=%s
                             AND extensions.name=%s""",
                       (author.id, extension.getName()))

        installed_count = len(cursor.fetchall())

        if installed_count: installed = " (installed by %d user%s)" % (installed_count, "s" if installed_count > 1 else "")
        else: installed = ""

        table.addItem("Extension", renderItem, extension_path + "/" + installed, buttons)

    document.addInternalScript("var selected_versions = %s;" % page.utils.json_encode(selected_versions))

    return document
