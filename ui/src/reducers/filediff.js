/*
 * Copyright 2017 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import Immutable from "immutable"

import { assertEqual } from "../debug"
import { FILECONTENT_UPDATE } from "../actions/filecontent"
import { FileDiff, MacroChunk, DiffLine } from "../resources/filediff"

const expandContextLine = (line, offsetDifference) =>
  new DiffLine({
    type: line.type,
    content: new Immutable.List(line.content),
    old_offset: line.offset + offsetDifference,
    new_offset: line.offset,
  })

const mergedChunks = (chunks) => {
  const result = []
  var prevChunk = null
  var mergedAny = false
  for (const nextChunk of chunks) {
    if (prevChunk !== null) {
      if (prevChunk.old_offset + prevChunk.old_count === nextChunk.old_offset) {
        assertEqual(
          prevChunk.new_offset + prevChunk.new_count,
          nextChunk.new_offset
        )
        prevChunk = prevChunk.merge({
          old_count: prevChunk.old_count + nextChunk.old_count,
          new_count: prevChunk.new_count + nextChunk.new_count,
          content: prevChunk.content.concat(nextChunk.content),
        })
        mergedAny = true
        continue
      }
      result.push(prevChunk)
    }
    prevChunk = nextChunk
  }
  if (!mergedAny) return chunks
  result.push(prevChunk)
  return new Immutable.List(result)
}

const filediff = (state = {}, action) => {
  switch (action.type) {
    case FILECONTENT_UPDATE:
      if (action.changesetID !== null && action.fileID !== null) {
        const fileDiffKey = `${action.changesetID}_${action.fileID}`
        const fileDiff = state.get(fileDiffKey)
        const chunks = fileDiff.macro_chunks
        const chunk = chunks.get(action.chunkIndex)

        const offsetDifferenceStart = chunk.old_offset - chunk.new_offset
        const offsetDifferenceEnd =
          chunk.old_offset +
          chunk.old_count -
          (chunk.new_offset + chunk.new_count)
        const newLinesCount = action.lines.length
        const newContextLines = action.lines.map((line) =>
          expandContextLine(line, offsetDifferenceStart)
        )
        var newChunk
        if (chunk.content.first().new_offset > action.lines[0].offset) {
          newChunk = new MacroChunk({
            content: new Immutable.List().concat(
              newContextLines,
              chunk.content
            ),
            old_offset: chunk.old_offset - newLinesCount,
            new_offset: chunk.new_offset - newLinesCount,
            old_count: chunk.old_count + newLinesCount,
            new_count: chunk.new_count + newLinesCount,
          })
        } else {
          newChunk = chunk.merge({
            content: chunk.content.concat(newContextLines),
            old_count: chunk.old_count + newLinesCount,
            new_count: chunk.new_count + newLinesCount,
          })
        }
        const newFileDiff = fileDiff.set(
          "macro_chunks",
          mergedChunks(chunks.set(action.chunkIndex, newChunk))
        )
        state = state.set(fileDiffKey, newFileDiff)
      }
      return state

    default:
      return state
  }
}

export default filediff
