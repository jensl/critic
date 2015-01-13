# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import jsonapi
import page.utils

def splitAndDeindentDocstring(item, level, default=None):
    if item.__doc__ is None:
        if default:
            return [default]
        return
    def inner():
        lines = item.__doc__.splitlines()
        yield lines[0]
        indentation_level = level * 4 + 3
        expected_indentation = " " * indentation_level
        for line in lines[1:]:
            assert not line or line.startswith(expected_indentation)
            yield line[indentation_level:]
    return list(inner())

def extractResourceSummary(resource_class):
    lines = list(splitAndDeindentDocstring(
        resource_class, level=1, default="Undocumented"))
    try:
        return " ".join(lines[:lines.index("")])
    except ValueError:
        return " ".join(lines)

def popParagraph(lines, include_empty=False):
    try:
        index = lines.index("")
    except ValueError:
        index = len(lines)
    paragraph = lines[:index]
    if len(paragraph) == 1 and " : " in paragraph[0]:
        return None
    if include_empty:
        paragraph.append("")
    del lines[:index + 1]
    return paragraph

def copyParagraph(destination, source, as_definition=False, include_empty=None):
    if include_empty is None:
        include_empty = not as_definition
    paragraph = popParagraph(source, include_empty=False)
    if paragraph is None:
        paragraph = ["Undocumented!"]
    if as_definition:
        paragraph = (["= " + paragraph[0]] +
                     ["  " + line for line in paragraph[1:]])
    if include_empty:
        paragraph.append("")
    destination.extend(paragraph)
    return True

def describeVersion():
    lines = ["Critic JSON API: Version 1",
             "==========================",
             "",
             "Path",
             "----",
             "<code>/api/v1</code>",
             "",
             "Top-level resources",
             "-------------------"]

    supported_resources = []

    for path, resource_class in jsonapi.HANDLERS.items():
        if path.startswith("v1/"):
            supported_resources.append(
                (path[3:], extractResourceSummary(resource_class)))

    supported_resources.sort()

    for path, summary in supported_resources:
        lines.extend(["? <code>/api/v1/[%s][%s]</code>" % (path, path),
                      "= " + summary])

    lines.append("")

    for path, _ in supported_resources:
        lines.append("[%s]: /api/v1?describe=%s" % (path, path))

    raise page.utils.DisplayFormattedText(lines)

def listAlternativePaths(resource_class):
    for context in getattr(resource_class, "contexts", (None,)):
        if context is None:
            yield resource_class.name
            continue
        for context_class in jsonapi.find(context):
            for context_path in listAlternativePaths(context_class):
                yield "%s/%s" % (context_path, resource_class.name)

def describeResource(resource_path):
    resource_class = jsonapi.lookup("v1/" + resource_path)

    # foo/bar/fie -> foo/A/bar/B/fie
    path_with_arguments = resource_path.split("/")
    placeholders = ("A", "B", "C", "D", "E", "F")
    for index in reversed(range(1, len(path_with_arguments))):
        path_with_arguments.insert(
            index, "<i>%s</i>" % placeholders[index - 1])
    path_with_arguments = "/".join(path_with_arguments)

    lines = [resource_class.name.capitalize(),
             "=" * len(resource_class.name),
             ""]

    lines.extend(["Description",
                  "-----------",
                  ""] +
                 splitAndDeindentDocstring(resource_class, level=1) +
                 [""])

    def search_and_filter_parameters(description, path=path_with_arguments):
        nparameters = 0
        while description:
            try:
                key, name, expected_type = description[0].split(" : ")
            except ValueError:
                break
            else:
                del description[0]
                if not nparameters:
                    lines.extend(["Search/filter parameters",
                                  "------------------------"])
                nparameters += 1
                if expected_type == "-":
                    expected_type = ""
                else:
                    expected_type = " (%s)" % expected_type
                lines.append("? <code>api/v1/%s?<b>%s=%s</b></code>%s"
                             % (path, key, name, expected_type))
                assert not description.pop(0)
                copyParagraph(lines, description, as_definition=True)
        if nparameters > 1:
            lines.extend(
                ["",
                 "Note: Unless noted otherwise, search/filter parameters",
                 "      can be combined."])
        if nparameters > 0:
            lines.append("")
            return True
        return False

    if resource_class.single:
        lines.extend(["Single-resource access",
                      "----------------------",
                      ""])

        description = splitAndDeindentDocstring(resource_class.single, 2)

        if description is None:
            lines.append("Undocumented!")
        else:
            lines.append("? <code>api/v1/%s/ARGUMENT[,ARGUMENT,...]</code>"
                         % path_with_arguments)
            copyParagraph(
                lines, description, as_definition=True, include_empty=True)

            first_variant = True
            while description:
                try:
                    name, expected_type = description[0].split(" : ")
                except ValueError:
                    break
                else:
                    del description[0]
                    if first_variant:
                        lines.extend(["Resource argument",
                                      "-----------------"])
                        first_variant = False
                    lines.append("? <code>api/v1/%s/<b>%s</b></code> (%s)"
                                 % (path_with_arguments, name, expected_type))
                    assert not description.pop(0)
                    copyParagraph(lines, description, as_definition=True)

            lines.append("")

            search_and_filter_parameters(
                description, path="%s/ARGUMENT" % path_with_arguments)

            lines.extend(description)

        lines.append("")

    if resource_class.multiple:
        lines.extend(["Multiple-resource access",
                      "------------------------",
                      ""])

        description = splitAndDeindentDocstring(resource_class.multiple, 2)

        if description is None:
            lines.extend(["Undocumented!",
                          ""])
        else:
            lines.append("? <code>api/v1/%s</code>" % path_with_arguments)
            copyParagraph(lines, description, as_definition=True)
            lines.append("")

            while description and not search_and_filter_parameters(description):
                copyParagraph(lines, description)

    lines.extend(["Resource structure",
                  "------------------",
                  ""])

    structure_lines = splitAndDeindentDocstring(resource_class.json, level=2)
    if structure_lines:
        def massage_line(line):
            if line.strip().startswith("// "):
                return "  // <b>" + line.strip()[3:] + "</b>"
            line, _, description = line.partition(" // ")
            if description:
                line += " <i style='float: right'>%s</i>" % description
            return line

        lines.extend("|| " + massage_line(line) for line in structure_lines)
        lines.append("")
    else:
        lines.extend(["Undocumented!",
                      ""])

    alternative_paths = sorted(
        set(listAlternativePaths(resource_class)) - set([resource_path]))

    if alternative_paths:
        lines.extend(["Alternative paths",
                      "-----------------",
                      "",
                      "This class of resources is also accessible as:",
                      ""])

        for alternative_path in alternative_paths:
            lines.extend(["* <code>api/v1/[%s][%s]</code>"
                          % (alternative_path, alternative_path),
                          ""])

        for alternative_path in alternative_paths:
            lines.append("[%s]: /api/v1?describe=%s"
                         % (alternative_path, alternative_path))
        lines.append("")

    subresources = []
    prefix = ".../" + resource_class.name + "/"

    for path, subresource_class in jsonapi.HANDLERS.items():
        if path.startswith(prefix):
            subresources.append(
                (path[len(prefix):], extractResourceSummary(subresource_class)))

    if subresources:
        lines.extend(["Sub-resources",
                      "-------------",
                      ""])

        for path, summary in sorted(subresources):
            lines.extend(["? <code>/api/v1/%s/[%s][%s]</code>"
                          % (path_with_arguments, path, path),
                          "= " + summary])

        lines.append("")

        for path, _ in subresources:
            lines.append("[%s]: /api/v1?describe=%s/%s"
                         % (path, resource_path, path))

    raise page.utils.DisplayFormattedText(lines)
