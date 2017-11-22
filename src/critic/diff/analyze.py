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

import collections
import difflib
import re

from critic import textutils


def normalize_line(line):
    """Normalize leading and trailing white-space in line

       Leading white-space is normalized to a single space (if there was
       any) and trailing white-space is stripped."""

    rstripped = line.rstrip()
    stripped = rstripped.lstrip()
    if stripped != rstripped:
        return " " + stripped
    return rstripped


class Lines(list):
    def __init__(self, lines):
        super(Lines, self).__init__(lines)
        self.normalized = [normalize_line(line) for line in lines]
        self.counted = collections.Counter(self.normalized)

    def count(self, index):
        line = self.normalized[index]
        return self.counted[line]


re_ignore = re.compile("^\\s*(?:[{}*]|else|do|\\*/)?\\s*$")
re_words = re.compile("([0-9]+|[A-Z][a-z]+|[A-Z]+|[a-z]+|[\\[\\]{}()]|\\s+|.)")
re_ws = re.compile("\\s+")
re_conflict = re.compile("^<<<<<<< .*$|^=======$|^>>>>>>> .*$")


def analyzeChunk(deletedLines, insertedLines, moved=False):
    # Pure delete or pure insert, nothing to analyze.
    if not deletedLines or not insertedLines:
        return None

    deletedLines = list(map(textutils.decode, deletedLines))
    insertedLines = list(map(textutils.decode, insertedLines))

    # Large chunk, analysis would be expensive, so skip it.
    if len(deletedLines) * len(insertedLines) <= 10000 and not moved:
        analysis = analyzeChunk1(deletedLines, insertedLines)
    else:
        deletedLinesNoWS = [re_ws.sub(" ", line.strip()) for line in deletedLines]
        insertedLinesNoWS = [re_ws.sub(" ", line.strip()) for line in insertedLines]

        sm = difflib.SequenceMatcher(None, deletedLinesNoWS, insertedLinesNoWS)
        blocks = sm.get_matching_blocks()

        analysis = []

        pi = 0
        pj = 0

        for i, j, n in blocks:
            if not n:
                continue

            if i > pi and j > pj:
                analysis.append(
                    analyzeChunk1(
                        deletedLines[pi:i], insertedLines[pj:j], offsetA=pi, offsetB=pj
                    )
                )

            analysis.append(
                analyzeWhiteSpaceChanges(
                    deletedLines[i : i + n],
                    insertedLines[j : j + n],
                    offsetA=i,
                    offsetB=j,
                    full=moved,
                )
            )

            pi = i + n
            pj = j + n

        if pi < len(deletedLines) and pj < len(insertedLines):
            analysis.append(
                analyzeChunk1(
                    deletedLines[pi:], insertedLines[pj:], offsetA=pi, offsetB=pj
                )
            )

        analysis = ";".join(filter(None, analysis))

    if analysis:
        return analysis
    else:
        return ""


def analyzeChunk1(deletedLines, insertedLines, offsetA=0, offsetB=0):
    matches = []
    equals = []

    if len(deletedLines) * len(insertedLines) > 10000:
        return ""

    def ratio(sm, a, b, aLength, bLength):
        matching = 0
        for i, j, n in sm.get_matching_blocks():
            matching += sum(map(len, map(str.strip, a[i : i + n])))
        if aLength > 5 and len(sm.get_matching_blocks()) == 2:
            return float(matching) / aLength
        else:
            return 2.0 * matching / (aLength + bLength)

    for deletedIndex, deleted in enumerate(deletedLines):
        deletedStripped = deleted.strip()
        deletedNoWS = re_ws.sub("", deletedStripped)

        # Don't match conflict lines against anything.
        if re_conflict.match(deleted):
            continue

        if not re_ignore.match(deleted):
            deletedWords = re_words.findall(deleted)

            for insertedIndex, inserted in enumerate(insertedLines):
                insertedStripped = inserted.strip()
                insertedNoWS = re_ws.sub("", insertedStripped)

                if not re_ignore.match(inserted):
                    insertedWords = re_words.findall(inserted)
                    sm = difflib.SequenceMatcher(None, deletedWords, insertedWords)
                    r = ratio(
                        sm,
                        deletedWords,
                        insertedWords,
                        len(deletedNoWS),
                        len(insertedNoWS),
                    )
                    if r > 0.5:
                        matches.append(
                            (
                                r,
                                deletedIndex,
                                insertedIndex,
                                deletedWords,
                                insertedWords,
                                sm,
                            )
                        )
                elif deletedStripped == insertedStripped:
                    equals.append((deletedIndex, insertedIndex))
        else:
            for insertedIndex, inserted in enumerate(insertedLines):
                if deletedStripped == inserted.strip():
                    equals.append((deletedIndex, insertedIndex))

    if matches:
        matches.sort(key=lambda x: x[0], reverse=True)

        final = []

        while matches:
            (
                r,
                deletedIndex,
                insertedIndex,
                deletedWords,
                insertedWords,
                sm,
            ) = matches.pop(0)
            final.append((deletedIndex, insertedIndex, deletedWords, insertedWords, sm))
            matches = list(
                filter(
                    lambda data: data[1] != deletedIndex
                    and data[2] != insertedIndex
                    and (data[1] < deletedIndex) == (data[2] < insertedIndex),
                    matches,
                )
            )
            equals = list(
                filter(
                    lambda data: (data[0] < deletedIndex) == (data[1] < insertedIndex),
                    equals,
                )
            )

        final.sort()
        equals.sort()
        result = []

        previousDeletedIndex = -1
        previousInsertedIndex = -1

        final.append((len(deletedLines), len(insertedLines), None, None, None))

        for deletedIndex, insertedIndex, deletedWords, insertedWords, sm in final:
            while equals and (
                equals[0][0] < deletedIndex or equals[0][1] < insertedIndex
            ):
                di, ii = equals.pop(0)
                if (
                    previousDeletedIndex < di < deletedIndex
                    and previousInsertedIndex < ii < insertedIndex
                ):
                    deletedLine = deletedLines[di]
                    insertedLine = insertedLines[ii]
                    lineDiff = analyzeWhiteSpaceLine(deletedLine, insertedLine)
                    if lineDiff:
                        result.append(
                            "%d=%d:ws,%s" % (di + offsetA, ii + offsetB, lineDiff)
                        )
                    else:
                        result.append("%d=%d" % (di + offsetA, ii + offsetB))
                    previousDeletedIndex = di
                    previousInsertedIndex = ii
                while equals and (di == equals[0][0] or ii == equals[0][1]):
                    equals.pop(0)

            if sm is None:
                break

            lineDiff = []
            deletedLine = deletedLines[deletedIndex]
            insertedLine = insertedLines[insertedIndex]
            if (
                deletedLine != insertedLine
                and deletedLine.strip() == insertedLine.strip()
            ):
                lineDiff.append("ws")
                lineDiff.append(analyzeWhiteSpaceLine(deletedLine, insertedLine))
            else:
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "replace":
                        lineDiff.append(
                            "r%d-%d=%d-%d"
                            % (
                                offsetInLine(deletedWords, i1),
                                offsetInLine(deletedWords, i2),
                                offsetInLine(insertedWords, j1),
                                offsetInLine(insertedWords, j2),
                            )
                        )
                    elif tag == "delete":
                        lineDiff.append(
                            "d%d-%d"
                            % (
                                offsetInLine(deletedWords, i1),
                                offsetInLine(deletedWords, i2),
                            )
                        )
                    elif tag == "insert":
                        lineDiff.append(
                            "i%d-%d"
                            % (
                                offsetInLine(insertedWords, j1),
                                offsetInLine(insertedWords, j2),
                            )
                        )
            if lineDiff:
                result.append(
                    "%d=%d:%s"
                    % (
                        deletedIndex + offsetA,
                        insertedIndex + offsetB,
                        ",".join(lineDiff),
                    )
                )
            else:
                result.append(
                    "%d=%d" % (deletedIndex + offsetA, insertedIndex + offsetB)
                )

            previousDeletedIndex = deletedIndex
            previousInsertedIndex = insertedIndex

        return ";".join(result)
    elif deletedLines[-1] == insertedLines[-1]:
        ndeleted = len(deletedLines)
        ninserted = len(insertedLines)
        result = []
        index = 1

        while (
            index <= ndeleted
            and index <= ninserted
            and deletedLines[-index] == insertedLines[-index]
        ):
            result.append(
                "%d=%d" % (ndeleted - index + offsetA, ninserted - index + offsetB)
            )
            index += 1

        return ";".join(reversed(result))
    else:
        return ""


def offsetInLine(words, offset):
    return sum([len(word.encode()) for word in words[0:offset]])


re_ws_words = re.compile("( |\t|\\s+|\\S+)")


def analyzeWhiteSpaceLine(deletedLine, insertedLine):
    deletedLine = textutils.decode(deletedLine)
    insertedLine = textutils.decode(insertedLine)

    deletedWords = list(filter(None, re_ws_words.findall(deletedLine)))
    insertedWords = list(filter(None, re_ws_words.findall(insertedLine)))

    sm = difflib.SequenceMatcher(None, deletedWords, insertedWords)
    lineDiff = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            lineDiff.append(
                "r%d-%d=%d-%d"
                % (
                    offsetInLine(deletedWords, i1),
                    offsetInLine(deletedWords, i2),
                    offsetInLine(insertedWords, j1),
                    offsetInLine(insertedWords, j2),
                )
            )
        elif tag == "delete":
            lineDiff.append(
                "d%d-%d"
                % (offsetInLine(deletedWords, i1), offsetInLine(deletedWords, i2))
            )
        elif tag == "insert":
            lineDiff.append(
                "i%d-%d"
                % (offsetInLine(insertedWords, j1), offsetInLine(insertedWords, j2))
            )

    return ",".join(lineDiff)


def analyzeWhiteSpaceChanges(
    deletedLines, insertedLines, at_eof=False, offsetA=0, offsetB=0, full=False
):
    result = []

    for index, (deletedLine, insertedLine) in enumerate(
        zip(deletedLines, insertedLines)
    ):
        if deletedLine != insertedLine:
            result.append(
                "%d=%d:%s"
                % (
                    index + offsetA,
                    index + offsetB,
                    analyzeWhiteSpaceLine(deletedLine, insertedLine),
                )
            )
        elif index == len(deletedLines) - 1 and at_eof:
            result.append("%d=%d:eol" % (index + offsetA, index + offsetB))
        elif full:
            result.append("%d=%d" % (index + offsetA, index + offsetB))

    if not result and (offsetA or offsetB):
        result.append("%d=%d" % (offsetA, offsetB))

    return ";".join(result)
