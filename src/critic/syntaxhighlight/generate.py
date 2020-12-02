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

import logging
from typing import Any, Sequence, Tuple

logger = logging.getLogger("syntaxhighlight.generate")

from .highlighter import Highlighter
from .outputter import Outputter


class LanguageNotSupported(Exception):
    pass


def createHighlighter(language: str) -> Highlighter:
    # from .cpp import HighlightCPP

    # highlighter = HighlightCPP.create(language)
    # if highlighter:
    #     return highlighter

    from .generic import HighlightGeneric

    highlighter = HighlightGeneric.create(language)
    if highlighter:
        return highlighter

    logger.debug("language not supported: %s", language)
    raise LanguageNotSupported()


def generate(source: str, language: str) -> Tuple[Sequence[bytes], Any]:
    highlighter = createHighlighter(language)

    outputter = Outputter()
    contexts = highlighter(source, outputter)

    return outputter.result, contexts
