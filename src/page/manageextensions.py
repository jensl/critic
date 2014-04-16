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
import configuration

from extensions.extension import Extension, ExtensionError
from extensions.manifest import (ManifestError, PageRole, InjectRole,
                                 ProcessCommitsRole, FilterHookRole,
                                 ScheduledRole)

def renderManageExtensions(req, db, user):
    if not configuration.extensions.ENABLED:
        administrators = dbutils.getAdministratorContacts(db, as_html=True)
        raise page.utils.DisplayMessage(
            title="Extension support not enabled",
            body=(("<p>This Critic system does not support extensions.</p>"
                   "<p>Contact %s to have it enabled, or see the "
                   "<a href='/tutorial?item=administration#extensions'>"
                   "section on extensions</a> in the system administration "
                   "tutorial for more information.</p>")
                  % administrators),
            html=True)

    cursor = db.cursor()

    what = page.utils.getParameter(req, "what", "available")
    selected_versions = page.utils.json_decode(page.utils.getParameter(req, "select", "{}"))
    focused = page.utils.getParameter(req, "focus", None)

    if what == "installed":
        title = "Installed Extensions"
        listed_extensions = []
        for extension_id, _, _, _ in Extension.getInstalls(db, user):
            try:
                listed_extensions.append(Extension.fromId(db, extension_id))
            except ExtensionError as error:
                listed_extensions.append(error)
    else:
        title = "Available Extensions"
        listed_extensions = Extension.find(db)

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

    def addTitleRightLink(url, label):
        if user.name != req.user:
            url += "&user=%s" % user.name
        table.titleRight.text(" ")
        table.titleRight.a(href=url).text("[" + label + " extensions]")

    if what != "installed" or focused:
        addTitleRightLink("/manageextensions?what=installed", "installed")
    if what != "available" or focused:
        addTitleRightLink("/manageextensions?what=available", "available")

    for item in listed_extensions:
        if isinstance(item, ExtensionError):
            extension_error = item
            extension = item.extension
        else:
            extension_error = None
            extension = item

        if focused and extension.getKey() != focused:
            continue

        extension_path = extension.getPath()

        if extension.isSystemExtension():
            hosting_user = None
        else:
            hosting_user = extension.getAuthor(db)

        selected_version = selected_versions.get(extension.getKey(), False)
        installed_sha1, installed_version = extension.getInstalledVersion(db, user)
        universal_sha1, universal_version = extension.getInstalledVersion(db, None)
        installed_upgradeable = universal_upgradeable = False

        if extension_error is None:
            if installed_sha1:
                current_sha1 = extension.getCurrentSHA1(installed_version)
                installed_upgradeable = installed_sha1 != current_sha1
            if universal_sha1:
                current_sha1 = extension.getCurrentSHA1(universal_version)
                universal_upgradeable = universal_sha1 != current_sha1

        def massage_version(version):
            if version is None:
                return "live"
            elif version:
                return "version/%s" % version
            else:
                return None

        if selected_version is False:
            selected_version = installed_version
        if selected_version is False:
            selected_version = universal_version

        install_version = massage_version(selected_version)
        installed_version = massage_version(installed_version)
        universal_version = massage_version(universal_version)

        manifest = None

        if extension_error is None:
            try:
                if selected_version is False:
                    manifest = extension.getManifest()
                else:
                    manifest = extension.getManifest(selected_version)
            except ManifestError as error:
                pass
        elif installed_sha1:
            manifest = extension.getManifest(installed_version, installed_sha1)
        elif universal_sha1:
            manifest = extension.getManifest(universal_version, universal_sha1)

        if manifest:
            if what == "available" and manifest.hidden:
                # Hide from view unless the user is hosting the extension, or is
                # an administrator and the extension is a system extension.
                if extension.isSystemExtension():
                    if not user.hasRole(db, "administrator"):
                        continue
                elif hosting_user != user:
                    continue
        else:
            if hosting_user != user:
                continue

        extension_id = extension.getExtensionID(db, create=False)

        if not user.isAnonymous():
            buttons = []

            if extension_id is not None:
                cursor.execute("""SELECT 1
                                    FROM extensionstorage
                                   WHERE extension=%s
                                     AND uid=%s""",
                               (extension_id, user.id))

                if cursor.fetchone():
                    buttons.append(("Clear storage",
                                    ("clearExtensionStorage(%s, %s)"
                                     % (htmlutils.jsify(extension.getAuthorName()),
                                        htmlutils.jsify(extension.getName())))))

            if not installed_version:
                if manifest and install_version and install_version != universal_version:
                    buttons.append(("Install",
                                    ("installExtension(%s, %s, %s)"
                                     % (htmlutils.jsify(extension.getAuthorName()),
                                        htmlutils.jsify(extension.getName()),
                                        htmlutils.jsify(install_version)))))
            else:
                buttons.append(("Uninstall",
                                ("uninstallExtension(%s, %s)"
                                 % (htmlutils.jsify(extension.getAuthorName()),
                                    htmlutils.jsify(extension.getName())))))

                if manifest and (install_version != installed_version
                                 or (installed_sha1 and installed_upgradeable)):
                    if install_version == installed_version:
                        label = "Upgrade"
                    else:
                        label = "Install"

                    buttons.append(("Upgrade",
                                    ("reinstallExtension(%s, %s, %s)"
                                     % (htmlutils.jsify(extension.getAuthorName()),
                                        htmlutils.jsify(extension.getName()),
                                        htmlutils.jsify(install_version)))))

            if user.hasRole(db, "administrator"):
                if not universal_version:
                    if manifest and install_version:
                        buttons.append(("Install (universal)",
                                        ("installExtension(%s, %s, %s, true)"
                                         % (htmlutils.jsify(extension.getAuthorName()),
                                            htmlutils.jsify(extension.getName()),
                                            htmlutils.jsify(install_version)))))
                else:
                    buttons.append(("Uninstall (universal)",
                                    ("uninstallExtension(%s, %s, true)"
                                     % (htmlutils.jsify(extension.getAuthorName()),
                                        htmlutils.jsify(extension.getName())))))

                    if manifest and (install_version != universal_version
                                     or (universal_sha1 and universal_upgradeable)):
                        if install_version == universal_version:
                            label = "Upgrade (universal)"
                        else:
                            label = "Install (universal)"

                        buttons.append((label,
                                        ("reinstallExtension(%s, %s, %s, true)"
                                         % (htmlutils.jsify(extension.getAuthorName()),
                                            htmlutils.jsify(extension.getName()),
                                            htmlutils.jsify(universal_version)))))
        else:
            buttons = None

        def renderItem(target):
            target.span("name").innerHTML(extension.getTitle(db, html=True))

            if hosting_user:
                is_author = manifest and manifest.isAuthor(db, hosting_user)
                is_sole_author = is_author and len(manifest.authors) == 1
            else:
                is_sole_author = False

            if extension_error is None:
                span = target.span("details")
                span.b().text("Details: ")
                select = span.select("details", critic_author=extension.getAuthorName(), critic_extension=extension.getName())
                select.option(value='', selected="selected" if selected_version is False else None).text("Select version")
                versions = extension.getVersions()
                if versions:
                    optgroup = select.optgroup(label="Official Versions")
                    for version in versions:
                        optgroup.option(value="version/%s" % version, selected="selected" if selected_version == version else None).text("%s" % version.upper())
                optgroup = select.optgroup(label="Development")
                optgroup.option(value='live', selected="selected" if selected_version is None else None).text("LIVE")

            if manifest:
                is_installed = bool(installed_version)

                if is_installed:
                    target.span("installed").text(" [installed]")
                else:
                    is_installed = bool(universal_version)

                    if is_installed:
                        target.span("installed").text(" [installed (universal)]")

                target.div("description").preformatted().text(manifest.description, linkify=True)

                if not is_sole_author:
                    authors = target.div("authors")
                    authors.b().text("Author%s:" % ("s" if len(manifest.authors) > 1 else ""))
                    authors.text(", ".join(author.name for author in manifest.getAuthors()))
            else:
                is_installed = False

                div = target.div("description broken").preformatted()

                if extension_error is None:
                    anchor = div.a(href="loadmanifest?key=%s" % extension.getKey())
                    anchor.text("[This extension has an invalid MANIFEST file]")
                else:
                    div.text("[This extension has been deleted or has become inaccessible]")

            if selected_version is False:
                return

            pages = []
            injects = []
            processcommits = []
            filterhooks = []
            scheduled = []

            if manifest:
                for role in manifest.roles:
                    if isinstance(role, PageRole):
                        pages.append(role)
                    elif isinstance(role, InjectRole):
                        injects.append(role)
                    elif isinstance(role, ProcessCommitsRole):
                        processcommits.append(role)
                    elif isinstance(role, FilterHookRole):
                        filterhooks.append(role)
                    elif isinstance(role, ScheduledRole):
                        scheduled.append(role)

            role_table = target.table("roles")

            if pages:
                role_table.tr().th(colspan=2).text("Pages")

                for role in pages:
                    row = role_table.tr()
                    url = "%s/%s" % (dbutils.getURLPrefix(db, user), role.pattern)
                    if is_installed and "*" not in url:
                        row.td("pattern").a(href=url).text(url)
                    else:
                        row.td("pattern").text(url)
                    td = row.td("description")
                    td.text(role.description)

            if injects:
                role_table.tr().th(colspan=2).text("Page Injections")

                for role in injects:
                    row = role_table.tr()
                    row.td("pattern").text("%s/%s" % (dbutils.getURLPrefix(db, user), role.pattern))
                    td = row.td("description")
                    td.text(role.description)

            if processcommits:
                role_table.tr().th(colspan=2).text("ProcessCommits hooks")
                ul = role_table.tr().td(colspan=2).ul()

                for role in processcommits:
                    li = ul.li()
                    li.text(role.description)

            if filterhooks:
                role_table.tr().th(colspan=2).text("FilterHook hooks")

                for role in filterhooks:
                    row = role_table.tr()
                    row.td("title").text(role.title)
                    row.td("description").text(role.description)

            if scheduled:
                role_table.tr().th(colspan=2).text("Scheduled hooks")

                for role in scheduled:
                    row = role_table.tr()
                    row.td("pattern").text("%s @ %s" % (role.frequency, role.at))
                    td = row.td("description")
                    td.text(role.description)

        installed_by = ""

        if extension_id is not None:
            cursor.execute("""SELECT uid
                                FROM extensioninstalls
                                JOIN extensions ON (extensions.id=extensioninstalls.extension)
                               WHERE extensions.id=%s""",
                           (extension.getExtensionID(db, create=False),))

            user_ids = set(user_id for user_id, in cursor.fetchall())
            if user_ids:
                installed_by = " (installed"
                if None in user_ids:
                    installed_by += " universally"
                    user_ids.remove(None)
                    if user_ids:
                        installed_by += " and"
                if user_ids:
                    installed_by += (" by %d user%s"
                                  % (len(user_ids),
                                     "s" if len(user_ids) > 1 else ""))
                installed_by += ")"

        table.addItem("Extension", renderItem, extension_path + "/" + installed_by, buttons)

    document.addInternalScript("var selected_versions = %s;" % page.utils.json_encode(selected_versions))

    return document
