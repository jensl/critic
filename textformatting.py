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

import re

import configuration
import dbutils
import gitutils

def renderFormatted(db, user, table, lines, toc=False):
    re_h1 = re.compile("^=+$")
    re_h2 = re.compile("^-+$")
    data = { "configuration.URL": dbutils.getURLPrefix(db),
             "configuration.base.HOSTNAME": configuration.base.HOSTNAME,
             "configuration.base.SYSTEM_USER_NAME": configuration.base.SYSTEM_USER_NAME,
             "configuration.base.SYSTEM_GROUP_NAME": configuration.base.SYSTEM_GROUP_NAME,
             "configuration.paths.CONFIG_DIR": configuration.paths.CONFIG_DIR,
             "configuration.paths.INSTALL_DIR": configuration.paths.INSTALL_DIR,
             "configuration.paths.GIT_DIR": configuration.paths.GIT_DIR }

    blocks = []
    block = []

    for line in lines:
        if line.strip():
            block.append(line % data)
        elif block:
            blocks.append(block)
            block = []
    else:
        if block:
            blocks.append(block)

    text = None

    for block in blocks:
        def textToId(text):
            return text.lower().replace(' ', '_')

        if len(block) == 2:
            if re_h1.match(block[1]):
                table.setTitle(block[0])
                table.tr("h1").td("h1").h1(id=textToId(block[0])).text(block[0])
                text = None
                if toc:
                    toc = table.tr("toc").td("toc").div().table("toc")
                    toc.tr("heading").th().text("Table of contents")
                continue
            elif re_h2.match(block[1]):
                if toc: toc.tr("h2").td().a(href="#" + textToId(block[0])).text(block[0])
                table.tr("h2").td("h2").div().h2(id=textToId(block[0])).text(block[0])
                text = None
                continue

        if len(block) == 1 and block[0] == "[repositories]":
            text = None

            repositories = table.tr("repositories").td("repositories").table("repositories", align="center", cellspacing=0)
            headings = repositories.tr("headings")
            headings.th("name").text("Short name")
            headings.th("path").text("Repository path")

            cursor = db.cursor()
            cursor.execute("SELECT name, path FROM repositories ORDER BY id ASC")

            first = " first"

            for name, path in cursor:
                row = repositories.tr("repository" + first)
                row.td("name").text(name)
                row.td("path").text(gitutils.Repository.constructURL(db, user, path))
                first = ""

            continue

        if not text:
            text = table.tr("text").td("text")

        def translateConfigLinks(text):
            def linkify(match):
                item = match.group(1)
                return "<a href='config?highlight=%s'>%s</a>" % (item, item)

            return re.sub("CONFIG\\(([^)]+)\\)", linkify, text)

        def processText(lines):
            for index, line in enumerate(lines):
                if line.startswith("  http"):
                    lines[index] = "<a href='%s'>%s</a>" % (line.strip(), line.strip())
            return translateConfigLinks("\n".join(lines)).replace("--", "&mdash;")

        if len(block) > 2 and re_h2.match(block[1]):
            if toc: toc.tr("h3").td().a(href="#" + textToId(block[0])).text(block[0])
            div = text.div()
            div.h3(id=textToId(block[0])).text(block[0])
            block = block[2:]

        if block[0].startswith("|"):
            pre = text.div().table("pre").tr().td().preformatted()
            pre.text("\n".join([line[2:] for line in block]))
        elif block[0].startswith("* ") or block[0].startswith("1 "):
            if block[0].startswith("* "):
                items = text.div().ul()
            else:
                items = text.div().ol()
            item = []
            for line in block:
                if line[:2] != '  ':
                    if item: items.li().text("\n".join(item), cdata=True)
                    item = []
                else:
                    assert line[:2] == "  "
                item.append(line[2:])
            if item: items.li().text("\n".join(item), cdata=True)
        elif block[0].startswith("? "):
            items = text.div().dl()
            term = []
            definition = None
            for line in block:
                if line[:2] == '? ':
                    if definition:
                        items.dt().text(" ".join(term))
                        items.dd().text(processText(definition))
                        definition = None
                    term = [line[2:]]
                elif line[:2] == '= ':
                    assert term
                    assert definition is None
                    definition = [line[2:]]
                elif definition is None:
                    term.append(line[2:])
                else:
                    definition.append(line[2:])
            items.dt().text(" ".join(term))
            items.dd().text(processText(definition), cdata=True)
        elif block[0].startswith("  "):
            text_data = translateConfigLinks("\n".join(block))
            if block[0].startswith("  <code>"):
                className = "example"
            else:
                className = "hint"
                text_data = text_data.replace("--", "&mdash;")
            text.div().div(className).text(text_data, cdata=True)
        else:
            text.div().text(processText(block), cdata=True)
