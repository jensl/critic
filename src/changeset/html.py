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
import itertools
import urllib

from time import strftime
from bisect import bisect_right

import textutils
import dbutils
import diff
import diff.context
import changeset.utils as changeset_utils
import reviewing.comment as review_comment
import htmlutils
import configuration

from htmlutils import jsify, Generator, Text, HTML, stripStylesheet

re_tag = re.compile("<([bi]) class='?([a-z]+)'?>")
re_tailws = re.compile("^(.*?)(\s+)((?:<[^>]+>)*)$")

class CodeContexts:
    class Context:
        def __init__(self, first_line, last_line, description):
            self.first_line = first_line
            self.last_line = last_line
            self.description = description

        def __cmp__(self, index):
            return cmp(self.first_line, index)

    def __init__(self, db, sha1, first_line, last_line):
        cursor = db.cursor()
        cursor.execute("""SELECT first_line, last_line, context
                            FROM codecontexts
                           WHERE sha1=%s
                             AND first_line<=%s
                             AND last_line>=%s
                        ORDER BY first_line ASC, last_line DESC""",
                       (sha1, last_line, first_line))
        self.contexts = [CodeContexts.Context(first_line, last_line, description) for first_line, last_line, description in cursor]

    def find(self, linenr):
        index = bisect_right(self.contexts, linenr)
        if index:
            context = self.contexts[index - 1]
            if context.last_line >= linenr:
                return context.description
        return None

def expandHTML(db, file, old_offset, new_offset, lines, target):
    if old_offset == 1: where = 'top'
    elif old_offset + lines - 1 == file.oldCount(): where = 'bottom'
    else: where = 'middle'

    select = target.select(onchange=('expand(this, %d, %r, %r, %r, %d, %d, %d);' % (file.id, file.path, file.new_sha1, where, old_offset, new_offset, lines)))
    select.option(value='none').text("%s lines not shown" % lines)

    if where == 'middle': actualLines = lines
    else: actualLines = lines * 2

    if actualLines > 20: select.option(value=10).text("Show 10 more")
    if actualLines > 50: select.option(value=25).text("Show 25 more")
    if actualLines > 100: select.option(value=50).text("Show 50 more")

    select.option(value=lines).text("All")

def generateDataScript(db, user, changeset, review, file_id_format, compact, parent_index):
    data = { 'parent_id': changeset.parent.id if changeset.parent else None,
             'parent_sha1': htmlutils.jsify(changeset.parent.sha1) if changeset.parent else None,
             'child_id': changeset.child.id,
             'child_sha1': htmlutils.jsify(changeset.child.sha1),
             'changeset_id': jsify(changeset.id),
             'commit_ids': ", ".join([str(commit.getId(db)) for commit in reversed(changeset.commits(db))]),
             'parent_index': parent_index }

    if parent_index is None:
        commits = changeset.commits(db)

        if review and commits:
            if len(commits) > 1:
                cursor = db.cursor()
                cursor.execute("SELECT id FROM changesets JOIN reviewchangesets ON (changeset=id) WHERE review=%s AND child=ANY (%s)",
                               (review.id, [commit.getId(db) for commit in commits]))

                changeset_ids = [changeset_id for (changeset_id,) in cursor]
            else:
                changeset_ids = [changeset.id]
        else:
            changeset_ids = None

        if changeset_ids is None: changeset_ids = "null"
        else: changeset_ids = "[%s]" % ", ".join(map(str, changeset_ids))

        data["changeset_ids"] = changeset_ids

        if changeset.parent:
            data_script = """
var changeset = { parent: { id: %(parent_id)d, sha1: %(parent_sha1)s },
                  child: { id: %(child_id)d, sha1: %(child_sha1)s },
                  id: %(changeset_id)s,
                  ids: %(changeset_ids)s,
                  commits: [ %(commit_ids)s ] };
var useFiles = files;
""" % data
        else:
            data_script = """
var changeset = { parent: null,
                  child: { id: %(child_id)d, sha1: %(child_sha1)s },
                  id: %(changeset_id)s,
                  ids: %(changeset_ids)s,
                  commits: [ %(commit_ids)s ] };
var useFiles = files;
""" % data
    else:
        data_script = """
var changeset;
var parent_index = %(parent_index)d;

if (!changeset)
  changeset = { commits: [ %(child_id)d ] };

if (!changeset[parent_index])
  changeset[parent_index] = {};

if (!changeset.child)
  changeset.child = { id: %(child_id)d, sha1: %(child_sha1)s };

changeset[parent_index].parent = { id: %(parent_id)d, sha1: %(parent_sha1)s };
changeset[parent_index].child = { id: %(child_id)d, sha1: %(child_sha1)s };
changeset[parent_index].id = %(changeset_id)s;

var useFiles = files[parent_index] = {};
""" % data

    parent_index_property = "parent: %d, " % parent_index if parent_index is not None else ""

    all_files = set()

    for file in changeset.files:
        if file.move_source_file and file.move_target_file:
            all_files.add(file.move_source_file)
            all_files.add(file.move_target_file)
        elif file.hasChanges():
            all_files.add(file)

    for file in all_files:
        data_script += """
useFiles[%d] = { old_sha1: %r,
               %snew_sha1: %r,
               %spath: %s };
""" % (file.id, file.old_sha1, " " * len(str(file.id)), file.new_sha1, " " * len(str(file.id)), jsify(file.path))
        if file.old_sha1 != "0" * 40 and file.new_sha1 != "0" * 40:
            data_script += """files[%r] = { %sid: %d, side: 'o' };
""" % (file.old_sha1, parent_index_property, file.id)
            data_script += """files[%r] = { id: %d, side: 'n' };
""" % (file.new_sha1, file.id)
        elif file.new_sha1 != "0" * 40:
            data_script += """files[%r] = { id: %d, side: 'n' };
""" % (file.new_sha1, file.id)
        else:
            data_script += """files[%r] = { %sid: %d, side: 'o' };
""" % (file.old_sha1, parent_index_property, file.id)

    if review:
        data_script += """
%s
var commentChains;
""" % review.getJS()

        reviewable_files = ", ".join([("%d: %r" % (file_id, state)) for file_id, (is_reviewer, state, reviewers) in changeset.getReviewFiles(db, user, review).items() if is_reviewer])

        if parent_index is None:
            data_script += """
changeset.reviewableFiles = { %s };
""" % reviewable_files
        else:
            data_script += """
changeset[parent_index].reviewableFiles = { %s };
""" % reviewable_files

    if compact: return re.sub(r"\B\s+\B|\b\s+\B|\B\s+\b", "", data_script).strip()
    else: return data_script.strip()

def render(db, target, user, repository, changeset, review=None, review_mode=None,
           context_lines=3, style="horizontal", wrap=True, options={}, parent_index=None):
    addResources(db, user, repository, review, options.get("compact", False),
                 options.get("tabify", False), target)

    compact = options.get("compact", False)

    cursor = db.cursor()

    if options.get("merge"):
        local_comments_only = True
    else:
        local_comments_only = False

    target.script(type='text/javascript').text(generateDataScript(db, user, changeset, review, options.get("file_id_format", "f%d"), compact, parent_index), cdata=True)
    target.addInternalStylesheet("""
table.file > tbody.lines > tr > td.line {
    white-space: pre%s !important
}""" % (wrap and "-wrap" or ""))

    comment_chains_per_file = {}

    if review:
        comment_chain_script = ""

        for file in changeset.files:
            if file.hasChanges() and not file.wasRemoved():
                comment_chains = review_comment.loadCommentChains(db, review, user, file=file, changeset=changeset, local_comments_only=local_comments_only)
                if comment_chains:
                    comment_chains_per_file[file.path] = comment_chains

                    for chain in comment_chains:
                        if file.new_sha1 in chain.lines_by_sha1: sha1 = file.new_sha1
                        else: sha1 = file.old_sha1

                        comment_chain_script += "commentChains.push(%s);\n" % chain.getJSConstructor(sha1)

        if comment_chain_script:
            target.script(type='text/javascript').text(comment_chain_script, cdata=True)

    def join(a, b):
        if a and b: return itertools.chain(a, b)
        elif a: return a
        elif b: return b
        else: return []

    local_options = { "style": style, "count_chunks": True }
    for name, value in options.items():
        local_options[name] = value

    if local_options.get("expand"):
        limit = user.getPreference(db, "commit.expandFilesLimit")
        if limit != 0 and limit < len(changeset.files):
            del local_options["expand"]

    for index, file in enumerate(changeset.files):
        if file.hasChanges():
            if not file.wasRemoved() and not file.isBinaryChanges():
                file.loadOldLines(True, request_highlight=True)
                file.loadNewLines(True, request_highlight=True)

                if not file.isEmptyChanges():
                    lines = diff.context.ContextLines(
                        file, file.chunks, comment_chains_per_file.get(file.path, []),
                        merge=options.get("merge", False), conflicts=changeset.conflicts)
                    file.macro_chunks = lines.getMacroChunks(context_lines, highlight=True)
                else:
                    file.macro_chunks = []
            else:
                file.macro_chunks = []

            renderFile(db, target, user, review, file, first_file=index == 0, options=local_options, conflicts=changeset.conflicts, add_resources=False)

            file.clean()

            yield target

def renderFile(db, target, user, review, file, first_file=False, options={}, conflicts=False, add_resources=True):
    if add_resources:
        addResources(db, user, file.repository, review, options.get("compact", False), options.get("tabify"), target)

    if options.get("count_chunks"):
        deleted = 0
        inserted = 0
        if file.wasRemoved():
            file.loadOldLines(False)
            deleted = file.oldCount()
        else:
            for macro_chunk in file.macro_chunks:
                for chunk in macro_chunk.chunks:
                    deleted += chunk.delete_count
                    inserted += chunk.insert_count
        chunksText = "-%d/+%d lines" % (deleted, inserted)
    else:
        chunksText = ""

    compact = options.get("compact", False)

    file_table_class = "file sourcefont"
    compact = options.get("compact", False)

    if options.get("show"):
        file_table_class += " show"
    if options.get("expand"):
        file_table_class += " expanded"
        compact = False

    if first_file:
        file_table_class += " first"

    file_id = "f%d" % file.id
    customFileId = options.get("file_id")
    if customFileId:
        file_id = customFileId(file_id)

    if options.get("tabify"):
        target.script(type="text/javascript").text("calculateTabWidth();")

    table = target.table(file_table_class, width='100%', cellspacing=0, cellpadding=0, id=file_id, critic_file_id=file.id, critic_parent_index=options.get("parent_index"))

    if not compact:
        columns = table.colgroup()
        columns.col('edge')
        columns.col('linenr')
        columns.col('line')
        columns.col('middle')
        columns.col('middle')
        columns.col('line')
        columns.col('linenr')
        columns.col('edge')

    row = table.thead().tr()

    header_left = options.get("header_left")
    header_right = options.get("header_right")

    def make_url(url_path, path):
        params = { "sha1": commit.sha1, "path": path }
        if review is None:
            params["repository"] = str(file.repository.id)
        else:
            params["review"] = str(review.id)
        return "/%s?%s" % (url_path, urllib.urlencode(params))

    if header_left:
        header_left(db, row.td('left', colspan=4, align='left'), file)
    else:
        cell = row.td('left', colspan=4, align='left')

        commit = options.get("commit")
        if commit:
            cell.a("showtree root", href=make_url("showtree", "/")).text("root")
            cell.span("slash").text('/')

            components = file.path.split("/")
            for index, component in enumerate(components[:-1]):
                cell.a("showtree", href=make_url("showtree", "/".join(components[:index + 1]))).text(component, escape=True)
                cell.span("slash").text('/')

            if not file.wasRemoved():
                cell.a("showtree", href=make_url("showfile", "/".join(components))).text(components[-1], escape=True)
            else:
                cell.text(components[-1], escape=True)
        else:
            cell.text(file.path)

        if not compact:
            cell.comment("sha1: %s to %s" % (file.old_sha1, file.new_sha1))

    if header_right:
        header_right(db, row.td('right', colspan=4, align='right'), file)
    else:
        row.td('right', colspan=4, align='right').text(chunksText)

    next_old_offset = 1
    next_new_offset = 1

    display_type = options.get("display_type", "both")
    deleted_file = False
    added_file = False

    if not file.isBinaryChanges() and not file.isEmptyChanges():
        if file.old_sha1 == 40 * '0':
            display_type = "new"

            if file.getLanguage() is None:
                limit = configuration.limits.MAXIMUM_ADDED_LINES_UNRECOGNIZED
            else:
                limit = configuration.limits.MAXIMUM_ADDED_LINES_RECOGNIZED

            count = file.newCount()
            if count > limit and len(file.macro_chunks) == 1 and len(file.macro_chunks[0].lines) == count:
                added_file = True
        elif file.new_sha1 == 40 * '0':
            display_type = "old"
            deleted_file = not options.get("include_deleted", False)

    def baseFileId(file):
        if file.move_source_file and file.move_target_file:
            return "fm%d_%d" % (file.move_source_file.id, file.move_target_file.id)
        else:
            return "f%d" % file.id

    def baseLineId(file, line, index):
        file_id = fileId(file)
        if line.type == diff.Line.DELETED:
            return "%so%dn0" % (file_id, line.old_offset)
        elif line.type == diff.Line.INSERTED:
            return "%so0n%d" % (file_id, line.new_offset)
        else:
            return "%so%dn%d" % (file_id, line.old_offset, line.new_offset)

    def baseLineCellId(file, version, line):
        if file.move_source_file and file.move_target_file:
            if version == "o": file_id = file.move_source_file.id
            else: file_id = file.move_target_file.id
        else:
            file_id = file.id
        if line: return "f%d%s%d" % (file_id, version, line)
        else: return None

    fileId = baseFileId

    customLineId = options.get("line_id")
    if customLineId:
        lineId = lambda file, line, index: customLineId(baseLineId(file, line, index))
    else:
        lineId = baseLineId

    customLineCellId = options.get("line_cell_id")
    if customLineCellId:
        lineCellId = lambda file, version, line: customLineCellId(baseLineCellId(file, version, line))
    else:
        lineCellId = baseLineCellId

    def lineType(line, index):
        type = line.type
        if type == diff.Line.DELETED: return "deleted"
        elif type == diff.Line.INSERTED: return "inserted"
        elif type == diff.Line.MODIFIED: return "modified whitespace" if line.is_whitespace else "modified"
        elif type == diff.Line.REPLACED: return "replaced"
        else: return "context"

    support_expand = options.get("support_expand", True)
    style = options.get("style", "horizontal")
    collapse_simple_hunks = user.getPreference(db, 'commit.diff.collapseSimpleHunks')

    content_before = options.get("content_before")
    if content_before:
        content = table.tbody('content')

        row = content.tr('content')
        row.td(colspan=2).text()
        content_before(db, row.td(colspan=4))
        row.td(colspan=2).text()

    if added_file or deleted_file:
        table.tbody('spacer').tr('spacer').td(colspan=8).text()

        verb = "added" if added_file else "deleted"
        side = "new" if added_file else "old"

        if added_file: count = file.newCount()
        else: count = file.oldCount()

        tbody = table.tbody('deleted')

        row = tbody.tr('deleted')
        row.td(colspan=2).text()
        row.td(colspan=4).h2().text("File was %s." % verb)
        row.td(colspan=2).text()

        if not file.isEmptyChanges():
            row = tbody.tr('deleted')
            row.td(colspan=2).text()
            parent_index = options.get("parent_index", -1)
            if parent_index != -1:
                fileset = "files[%d]" % parent_index
            else:
                fileset = "files"
            row.td(colspan=4).button(onclick="fetchFile(%s, %d, '%s', event.currentTarget.parentNode.parentNode.parentNode);" % (fileset, file.id, side)).text("Fetch %d %s Lines" % (count, verb.capitalize()))
            row.td(colspan=2).text()

        table.tbody('spacer').tr('spacer').td(colspan=8).text()
    elif file.isBinaryChanges() or file.isEmptyChanges():
        table.tbody('spacer').tr('spacer').td(colspan=8).text()

        if file.isBinaryChanges():
            title = "Binary"
            class_name = "binary"
        else:
            title = "Empty"
            class_name = "empty"

        tbody = table.tbody(class_name)

        if file.wasAdded():
            title += " file added."
        elif file.wasRemoved():
            title += " file removed."
        else:
            title += " file modified."

        row = tbody.tr(class_name)
        row.td(colspan=2).text()
        row.td(colspan=4).h2().text(title)
        row.td(colspan=2).text()

        if file.isBinaryChanges():
            row = tbody.tr('download')
            row.td(colspan=2).text()
            cell = row.td(colspan=4)

            def linkToFile(target, file, sha1):
                is_image = False

                try:
                    base, extension = file.path.rsplit(".")
                    if configuration.mimetypes.MIMETYPES.get(extension, "").startswith("image/"):
                        is_image = True
                except:
                    pass

                url = "/download/%s?sha1=%s&repository=%d" % (file.path, sha1, file.repository.id)
                link = target.a(href=url)

                if is_image: link.img(src=url)
                else: link.text(sha1)

            if file.wasAdded():
                linkToFile(cell, file, file.new_sha1)
            elif file.wasRemoved():
                linkToFile(cell, file, file.old_sha1)
            else:
                linkToFile(cell, file, file.old_sha1)
                cell.innerHTML(" &#8594; ")
                linkToFile(cell, file, file.new_sha1)

            row.td(colspan=2).text()

        table.tbody('spacer').tr('spacer').td(colspan=8).text()
    else:
        if options.get("tabify"):
            tabwidth = file.getTabWidth()
            indenttabsmode = file.getIndentTabsMode()
            tabify = lambda line: htmlutils.tabify(line, tabwidth, indenttabsmode)
        else:
            tabify = lambda line: line

        code_contexts = CodeContexts(db, file.new_sha1,
                                     file.macro_chunks[0].lines[0].new_offset,
                                     file.macro_chunks[-1].lines[-1].new_offset)

        blocks = [("[%d,%d]" % (macro_chunk.lines[0].new_offset, macro_chunk.lines[-1].new_offset))
                  for macro_chunk in file.macro_chunks]

        target.script(type="text/javascript").text("blocks[%d] = [%s];" % (file.id, ",".join(blocks)))

        for index, macro_chunk in enumerate(file.macro_chunks):
            first_line = macro_chunk.lines[0]
            last_line = macro_chunk.lines[-1]

            spacer = table.tbody('spacer')

            if support_expand and next_old_offset < first_line.old_offset and next_new_offset < first_line.new_offset:
                row = spacer.tr('expand').td(colspan='8')
                expandHTML(db, file, next_old_offset, next_new_offset, first_line.old_offset - next_old_offset, row)

            code_context = code_contexts.find(first_line.new_offset)
            if code_context: spacer.tr('context').td(colspan='8').text(code_context)

            spacer.tr('spacer').td(colspan='8').text()

            lines = table.tbody('lines')

            local_display_type = display_type

            for line in macro_chunk.lines:
                if line.type != diff.Line.INSERTED:
                    match = re_tailws.match(line.old_value)
                    if match:
                        line.old_value = match.group(1) + "<i class='tailws'>" + match.group(2) + "</i>" + match.group(3)
                if line.type != diff.Line.DELETED:
                    match = re_tailws.match(line.new_value)
                    if match:
                        line.new_value = match.group(1) + "<i class='tailws'>" + match.group(2) + "</i>" + match.group(3)

                if line.old_value:
                    line.old_value = line.old_value.replace("\r", "<i class='cr'></i>")
                if line.new_value:
                    line.new_value = line.new_value.replace("\r", "<i class='cr'></i>")

            if collapse_simple_hunks:
                if local_display_type == "both":
                    deleted = False
                    inserted = False

                    for line in macro_chunk.lines:
                        if line.type == diff.Line.MODIFIED or line.type == diff.Line.REPLACED:
                            break
                        elif line.type == diff.Line.DELETED:
                            if inserted: break
                            deleted = True
                        elif line.type == diff.Line.INSERTED:
                            if deleted: break
                            inserted = True
                    else:
                        if deleted: local_display_type = "old"
                        if inserted: local_display_type = "new"

            if compact:
                def packSyntaxHighlighting(line):
                    return re_tag.sub(lambda m: "<%s%s>" % (m.group(1), m.group(2)), line)

                items = []
                for line in macro_chunk.lines:
                    if line.type == diff.Line.MODIFIED and line.is_whitespace:
                        line_type = diff.Line.WHITESPACE
                    elif conflicts and line.type == diff.Line.DELETED and line.isConflictMarker():
                        line_type = diff.Line.CONFLICT
                    else:
                        line_type = line.type
                    data = [str(line_type)]
                    if line.type != diff.Line.INSERTED:
                        data.append(jsify(packSyntaxHighlighting(tabify(line.old_value)),
                                          as_json=True))
                    if line.type != diff.Line.DELETED:
                        data.append(jsify(packSyntaxHighlighting(tabify(line.new_value)),
                                          as_json=True))
                    items.append("[%s]" % ",".join(data))
                data = "[%d,%d,%d,%d,%s]" % (file.id,
                                             2 if local_display_type == "both" else 1,
                                             macro_chunk.lines[0].old_offset,
                                             macro_chunk.lines[0].new_offset,
                                             "[%s]" % ",".join(items))
                lines.comment(data.replace("--", "-\u002d"))
            elif style == "vertical" or local_display_type != "both":
                linesIterator = iter(macro_chunk.lines)
                line = linesIterator.next()

                def lineHTML(what, file, line, is_whitespace, target):
                    line_class = what

                    if is_whitespace and line.type == diff.Line.MODIFIED:
                        line_class = "modified"

                    if what == "deleted":
                        linenr = line.old_offset
                    else:
                        linenr = line.new_offset

                    row = target.tr("line single " + line_class, id=lineId(file, line, 0))
                    row.td("edge").text()
                    row.td("linenr old").text(linenr)

                    if what == "deleted" or local_display_type == "old":
                        code = line.old_value
                        lineClass = "old"
                    else:
                        code = line.new_value
                        lineClass = "new"

                    if not code: code = "&nbsp;"

                    row.td('line single ' + lineClass, colspan=4, id=lineCellId(file, lineClass[0], linenr)).innerHTML(tabify(code))
                    row.td('linenr new').text(linenr)

                    row.td("edge").text()

                try:
                    while line:
                        while line.type == diff.Line.CONTEXT:
                            lineHTML("context", file, line, False, lines)
                            line = linesIterator.next()

                        deleted = []
                        inserted = []

                        while line.is_whitespace:
                            lineHTML("modified", file, line, True, lines)
                            line = linesIterator.next()

                        previous_type = diff.Line.DELETED

                        try:
                            while line.type >= previous_type and not line.is_whitespace:
                                if line.type != diff.Line.INSERTED: deleted.append(line)
                                if line.type != diff.Line.DELETED: inserted.append(line)
                                previous_type = line.type
                                line = None
                                line = linesIterator.next()
                        except StopIteration:
                            line = None

                        for deletedLine in deleted:
                            lineHTML("deleted", file, deletedLine, False, lines)
                        for insertedLine in inserted:
                            lineHTML("inserted", file, insertedLine, False, lines)
                except StopIteration:
                    pass
            elif style == "horizontal":
                for line in macro_chunk.lines:
                    old_offset = None
                    new_offset = None
                    old_line = None
                    new_line = None

                    if line.type != diff.Line.INSERTED:
                        old_offset = line.old_offset
                        old_line = tabify(line.old_value)

                    if line.type != diff.Line.DELETED:
                        new_offset = line.new_offset
                        new_line = tabify(line.new_value)

                    if not old_line: old_line = "&nbsp;"
                    if old_line is None: old_offset = None
                    if not new_line: new_line = "&nbsp;"
                    if new_line is None: new_offset = None

                    line_type = lineType(line, 0)

                    if conflicts and line.isConflictMarker():
                        line_type += " conflict"

                    row = ("<tr class='line %s' id='%s'>"
                             "<td class='edge'>&nbsp;</td>"
                             "<td class='linenr old'>%s</td>"
                             "<td class='line old'%s>%s</td>"
                             "<td class='middle' colspan=2>&nbsp;</td>"
                             "<td class='line new'%s>%s</td>"
                             "<td class='linenr new'>%s</td>"
                             "<td class='edge'>&nbsp;</td>"
                           "</tr>\n") % (line_type, lineId(file, line, 0),
                                         str(old_offset) if old_offset else "&nbsp;",
                                         " id='%s'" % lineCellId(file, "o", old_offset) if old_offset else "", old_line,
                                         " id='%s'" % lineCellId(file, "n", new_offset) if new_offset else "", new_line,
                                         str(new_offset) if new_offset else "&nbsp;")

                    lines.innerHTML(row)

            next_old_offset = last_line.old_offset + 1
            next_new_offset = last_line.new_offset + 1

        spacer = table.tbody('spacer')

        if support_expand and next_old_offset < file.oldCount() + 1 and next_new_offset < file.newCount() + 1:
            row = spacer.tr('expand').td(colspan='8')
            expandHTML(db, file, next_old_offset, next_new_offset, 1 + file.oldCount() - next_old_offset, row)

        spacer.tr('spacer').td(colspan='8').text()

    content_after = options.get("content_after")
    if content_after:
        content = table.tbody('content')

        row = content.tr('content')
        row.td(colspan=2).text()
        content_after(db, row.td(colspan=4), file=file)
        row.td(colspan=2).text()

        content.tr('spacer').td(colspan=8).text()

    row = table.tfoot().tr()
    cell = row.td('left', colspan=4)

    commit = options.get("commit")
    if commit:
        cell.a("showtree root", href=make_url("showtree", "/")).text("root")
        cell.span("slash").text('/')

        components = file.path.split("/")
        for index, component in enumerate(components[:-1]):
            cell.a("showtree", href=make_url("showtree", "/".join(components[:index + 1]))).text(component, escape=True)
            cell.span("slash").text('/')

        if not file.wasRemoved():
            cell.a("showtree", href=make_url("showfile", "/".join(components))).text(components[-1], escape=True)
        else:
            cell.text(components[-1], escape=True)
    else:
        cell.text(file.path)

    row.td('right', colspan=4).text(chunksText)

def addResources(db, user, repository, review, compact, tabify, target):
    target.addExternalStylesheet("resource/changeset.css")
    target.addExternalScript("resource/changeset.js")

    target.addInternalStylesheet(stripStylesheet(user.getResource(db, "syntax.css")[1], compact))
    target.addInternalStylesheet(stripStylesheet(user.getResource(db, "diff.css")[1], compact))

    if user.getPreference(db, "commit.diff.highlightIllegalWhitespace"):
        target.addInternalStylesheet(stripStylesheet(user.getResource(db, "whitespace.css")[1], compact))

    ruler_column = user.getPreference(db, "commit.diff.rulerColumn", repository=repository)

    if ruler_column > 0:
        target.addExternalScript("resource/ruler.js")

    # Injected unconditionally (for tests).
    target.addInternalScript("var rulerColumn = %d;" % ruler_column)

    if review:
        target.addExternalStylesheet("resource/comment.css")
        target.addExternalStylesheet("resource/review.css")
        target.addExternalScript("resource/comment.js")
        target.addExternalScript("resource/review.js")

    if tabify:
        target.addExternalScript("resource/tabify.js")
