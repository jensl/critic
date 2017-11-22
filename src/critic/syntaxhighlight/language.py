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

import fnmatch
import itertools
import logging
import os
import re

logger = logging.getLogger(__name__)

from critic import api
from critic import diff

PER_FILENAME = None
PER_GLOB = None
PER_INTERPRETER = None
PER_EMACS_MODE = None
PER_VIM_FILETYPE = None

RE_INTERPRETER = re.compile(r"#!(?:/[^/]+)+/([^/]+?)(?:\s+(\S+))?(?:\s|$)")


def find_interpreter(lines):
    match = RE_INTERPRETER.match(lines[0])
    if match:
        interpreter, argument = match.groups()
        if interpreter == "env":
            return argument
        return interpreter


RE_EMACS_MODELINE = re.compile(
    r"\W*-\*-\s*([-\w]+\s*:\s*[^;]+(?:;\s*[-\w]+\s*:\s*[^;]+)*)\s*-\*-"
)


def parse_emacs_modeline(lines):
    for line in lines[:2]:
        if line.startswith("#!"):
            continue
        match = RE_EMACS_MODELINE.match(line)
        if match:
            assignments = match.group(1).split(";")
            return {
                name.strip(): value.strip()
                for name, _, value in [
                    assignment.partition(":") for assignment in assignments
                ]
            }
        break
    return {}


def find_emacs_mode(lines):
    return parse_emacs_modeline(lines).get("mode")


RE_VIM_MODELINE_SET = re.compile(
    r"\W*vim:\s+set(?:local)?\s+([^=]+=[^:]+(?::[^=]+=[^:]+)*)"
)
RE_VIM_MODELINE_NOSET = re.compile(r"\W*vim:((?:\s*[^=]+=\S+)+)\s*:")


def parse_vim_modeline(lines):
    for line in itertools.chain(lines[:5], reversed(lines[-5:])):
        match = RE_VIM_MODELINE_SET.match(line)
        if match:
            assignments = match.group(1).split(":")
        else:
            match = RE_VIM_MODELINE_NOSET.match(line)
            if match:
                assignments = match.group(1).split()
            else:
                continue
        return {
            name: value
            for name, _, value in (
                assignment.partition("=") for assignment in assignments
            )
        }
    return {}


def find_vim_filetype(lines):
    vim_modeline = parse_vim_modeline(lines)
    if "ft" in vim_modeline:
        return vim_modeline["ft"]
    return vim_modeline.get("filetype")


def setup():
    """Set up global data from configuration

       This must be called before identify_language() is called."""

    global PER_FILENAME, PER_GLOB, PER_INTERPRETER, PER_EMACS_MODE
    global PER_VIM_FILETYPE

    PER_FILENAME = {}
    PER_GLOB = []
    PER_INTERPRETER = []
    PER_EMACS_MODE = {}
    PER_VIM_FILETYPE = {}

    languages = api.critic.settings().syntax.languages

    for label, language in languages.items():
        if "filenames" in language:
            for filename in language.filenames:
                PER_FILENAME[filename] = label
        if "globs" in language:
            for glob in language.globs:
                PER_GLOB.append((glob, label))
        if "interpreters" in language:
            for interpreter in language.interpreters:
                PER_INTERPRETER.append((interpreter, label))
        if "emacs_modes" in language:
            for emacs_mode in language.emacs_modes:
                PER_EMACS_MODE[emacs_mode] = label
        if "vim_filetypes" in language:
            for vim_filetype in language.vim_filetypes:
                PER_VIM_FILETYPE[vim_filetype] = label


def identify_language_from_path(path):
    filename = os.path.basename(path)

    if filename in PER_FILENAME:
        return PER_FILENAME[filename]

    for glob, label in PER_GLOB:
        if fnmatch.fnmatch(filename, glob):
            return label


async def identify_language_from_source(repository, sha1):
    if PER_INTERPRETER or PER_EMACS_MODE or PER_VIM_FILETYPE:
        gitobject = await repository.fetchone(sha1, wanted_object_type="blob")
        lines = diff.parse.splitlines(gitobject.asBlob().data, limit=2)

        if PER_INTERPRETER:
            interpreter = find_interpreter(lines)
            if interpreter:
                for glob, label in PER_INTERPRETER:
                    if fnmatch.fnmatch(glob, interpreter):
                        return label

        if PER_EMACS_MODE:
            emacs_mode = find_emacs_mode(lines)
            if emacs_mode in PER_EMACS_MODE:
                return PER_EMACS_MODE[emacs_mode]

        if PER_VIM_FILETYPE:
            vim_filetype = find_vim_filetype(lines)
            if vim_filetype in PER_VIM_FILETYPE:
                return PER_VIM_FILETYPE[vim_filetype]
