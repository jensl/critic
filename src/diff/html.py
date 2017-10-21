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

import textutils
from htmlutils import htmlify

re_tag = re.compile("(<[^>]*>)")
re_decimal_entity = re.compile("&#([0-9]+);")

class Tag:
    def __init__(self, value): self.value = value
    def __str__(self): return self.value
    def __nonzero__(self): return False
    def __repr__(self): return "Tag(%r)" % self.value

def splitTags(line):
    def process(token):
        if token[0] == '<':
            return Tag(token)
        else:
            def replace_decimal(match):
                return unichr(int(match.group(1)))

            token = textutils.decode(token)
            token = re_decimal_entity.sub(replace_decimal, token)
            token = token.encode("utf-8")

            return token.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    return list(map(process, filter(None, re_tag.split(line))))

def joinTags(tags):
    def process(token):
        if token: return htmlify(token)
        else: return str(token)

    return "".join(map(process, tags))

def insertTag(tags, offset, newTag):
    newTag = Tag(newTag)
    index = 0
    while index < len(tags):
        tag = tags[index]
        if tag:
            if len(tag) < offset: offset -= len(tag)
            else:
                if len(tag) == offset: tags.insert(index + 1, newTag)
                elif not offset: tags.insert(index, newTag)
                else: tags[index:index+1] = tag[:offset], newTag, tag[offset:]
                return
        index += 1
    tags.append(newTag)

def lineDiffHTML(ops, old, new):
    old = splitTags(old)
    new = splitTags(new)

    for op in ops:
        old_lines = None
        oldType = None
        new_lines = None
        newType = None

        if op[0] == 'r':
            old_lines, new_lines = op[1:].split('=')
            oldType = 'r'
            newType = 'r'
        elif op[0] == 'd':
            old_lines = op[1:]
            oldType = 'd'
        else:
            new_lines = op[1:]
            newType = 'i'

        if old_lines:
            start, end = old_lines.split('-')
            insertTag(old, int(start), "<i class='%s'>" % oldType)
            insertTag(old, int(end), "</i>")

        if new_lines:
            start, end = new_lines.split('-')
            insertTag(new, int(start), "<i class='%s'>" % newType)
            insertTag(new, int(end), "</i>")

    return joinTags(old), joinTags(new)
