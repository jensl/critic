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

import dbutils
import htmlutils
import page.utils
import configuration

def renderEditResource(req, db, user):
    name = page.utils.getParameter(req, "name", None)

    document = htmlutils.Document(req)

    html = document.html()
    head = html.head()
    body = html.body()

    page.utils.generateHeader(body, db, user)

    document.addExternalStylesheet("resource/editresource.css")
    document.addExternalScript("resource/editresource.js")

    target = body.div("main")

    table = target.table('paleyellow', align='center')
    table.col(width='10%')
    table.col(width='60%')
    table.tr().td('h1', colspan=2).h1().text("Resource Editor")

    select_row = table.tr('select')
    select_row.td('heading').text('Resource:')
    select = select_row.td('value').select()
    if name is None: select.option(selected="selected").text("Select resource")
    select.option(value="diff.css", selected="selected" if name=="diff.css" else None).text("Diff coloring")
    select.option(value="syntax.css", selected="selected" if name=="syntax.css" else None).text("Syntax highlighting")

    help_row = table.tr('help')
    help_row.td('help', colspan=2).text("Select the resource to edit.")

    is_edited = False
    is_reset = False
    source = None

    if name is None:
        document.addInternalScript("var resource_name = null;");
        source = ""
    else:
        if name not in ("diff.css", "syntax.css"):
            raise page.utils.DisplayMessage("Invalid resource name", body="Must be one of 'diff.css' and 'syntax.css'.")

        document.addInternalScript("var resource_name = %s;" % htmlutils.jsify(name));

        cursor = db.cursor()
        cursor.execute("SELECT source FROM userresources WHERE uid=%s AND name=%s ORDER BY revision DESC FETCH FIRST ROW ONLY", (user.id, name))
        row = cursor.fetchone()

        if row:
            is_edited = True
            source = row[0]

        if source is None:
            is_reset = is_edited
            source = open(configuration.paths.INSTALL_DIR + "/resources/" + name).read()

        document.addInternalScript("var original_source = %s;" % htmlutils.jsify(source));

    table.tr('value').td('value', colspan=2).textarea(rows=source.count("\n") + 10).preformatted().text(source)

    buttons = table.tr('buttons').td('buttons', colspan=2)
    buttons.button('save').text("Save changes")

    if is_edited and not is_reset:
        buttons.button('reset').text("Reset to built-in version")

    if is_reset:
        buttons.button('restore').text("Restore last edited version")

    return document
