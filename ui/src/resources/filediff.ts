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

import { Draft, immerable } from "immer"
import { assertNotNull, assertTrue } from "../debug"

import { primaryMap } from "../reducers/resource"
import { DiffLine, DiffLineData } from "./diffcommon"

type FileDiffData = {
  file: number
  changeset: number
  old_is_binary: boolean
  old_syntax: string
  old_length: number
  old_linebreak: boolean
  delete_count: number
  new_is_binary: boolean
  new_syntax: string
  new_length: number
  new_linebreak: boolean
  insert_count: number
  macro_chunks?: MacroChunkData[]
}

type FileDiffProps = {
  file: number
  changeset: number
  old_is_binary: boolean
  old_syntax: string
  old_length: number
  old_linebreak: boolean
  delete_count: number
  new_is_binary: boolean
  new_syntax: string
  new_length: number
  new_linebreak: boolean
  insert_count: number
  macro_chunks: readonly MacroChunk[] | null
}

class FileDiff {
  [immerable] = true

  constructor(
    readonly file: number,
    readonly changeset: number,
    readonly oldIsBinary: boolean,
    readonly oldSyntax: string,
    readonly oldLength: number,
    readonly oldLinebreak: boolean,
    readonly deleteCount: number,
    readonly newIsBinary: boolean,
    readonly newSyntax: string,
    readonly newLength: number,
    readonly newLinebreak: boolean,
    readonly insertCount: number,
    readonly macroChunks: readonly MacroChunk[] | null,
  ) {}

  static new(props: FileDiffProps) {
    return new FileDiff(
      props.file,
      props.changeset,
      props.old_is_binary,
      props.old_syntax,
      props.old_length,
      props.old_linebreak,
      props.delete_count,
      props.new_is_binary,
      props.new_syntax,
      props.new_length,
      props.new_linebreak,
      props.insert_count,
      props.macro_chunks,
    )
  }

  static prepare(value: FileDiffData) {
    return {
      ...value,
      macro_chunks: MacroChunk.make(value.macro_chunks),
    }
  }

  static reducer = primaryMap<FileDiff, string>(
    "filediffs",
    (filediff) => `${filediff.changeset}:${filediff.file}`,
    (draft, action) => {
      if (action.type !== "FILEDIFFS_UPDATE") return
      const { changesetID, fileID, chunkIndex, operation } = action
      const filediffID = `${changesetID}:${fileID}`
      const filediff = draft.get(filediffID)
      if (!filediff || !filediff.macroChunks) return
      const macroChunk = filediff.macroChunks[chunkIndex]
      const lines = action.lines as readonly DiffLine[]
      draft.set(
        filediffID,
        filediff.replaceChunk(
          Math.max(0, chunkIndex),
          operation === "append"
            ? macroChunk.append(lines)
            : macroChunk.prepend(lines),
        ),
      )
    },
  )

  get props(): FileDiffProps {
    return {
      ...this,
      old_is_binary: this.oldIsBinary,
      old_syntax: this.oldSyntax,
      old_length: this.oldLength,
      old_linebreak: this.oldLinebreak,
      delete_count: this.deleteCount,
      new_is_binary: this.newIsBinary,
      new_syntax: this.newSyntax,
      new_length: this.newLength,
      new_linebreak: this.newLinebreak,
      insert_count: this.insertCount,
      macro_chunks: this.macroChunks,
    }
  }

  replaceChunk(index: number, chunk: MacroChunk) {
    assertNotNull(this.macroChunks)
    let nextIndex = index + 1
    if (nextIndex < this.macroChunks.length) {
      const nextChunk = this.macroChunks[nextIndex]
      if (chunk.newOffset + chunk.newCount === nextChunk.newOffset) {
        assertTrue(chunk.oldOffset + chunk.oldCount === nextChunk.oldOffset)
        chunk = chunk.append(nextChunk.content)
        ++nextIndex
      }
    }
    return new FileDiff(
      this.file,
      this.changeset,
      this.oldIsBinary,
      this.oldSyntax,
      this.oldLength,
      this.oldLinebreak,
      this.deleteCount,
      this.newIsBinary,
      this.newSyntax,
      this.newLength,
      this.newLinebreak,
      this.insertCount,
      [
        ...this.macroChunks.slice(0, index),
        chunk,
        ...this.macroChunks.slice(nextIndex),
      ],
    ) as Draft<FileDiff>
  }
}

export type MacroChunkData = [
  content: DiffLineData[],
  old_offset: number,
  old_count: number,
  new_offset: number,
  new_count: number,
]

type MacroChunkProps = {
  content: readonly DiffLine[]
  old_offset: number
  old_count: number
  new_offset: number
  new_count: number
}

export type MacroChunkInput = [DiffLineData[], number, number, number, number]

export class MacroChunk {
  [immerable] = true

  constructor(
    readonly content: readonly DiffLine[],
    readonly oldOffset: number,
    readonly oldCount: number,
    readonly newOffset: number,
    readonly newCount: number,
  ) {}

  static new(props: MacroChunkProps) {
    return new MacroChunk(
      props.content,
      props.old_offset,
      props.old_count,
      props.new_offset,
      props.new_count,
    )
  }

  static make(macroChunks?: MacroChunkData[]) {
    if (!macroChunks) return null
    function* generate() {
      assertNotNull(macroChunks)
      for (const value of macroChunks) {
        const [content, old_offset, new_offset, old_count, new_count] = value
        yield MacroChunk.new({
          content: DiffLine.make(content, old_offset, new_offset),
          old_offset,
          old_count,
          new_offset,
          new_count,
        })
      }
    }
    return Array.from(generate())
  }

  get oldEnd() {
    return this.oldOffset + this.oldCount
  }

  get newEnd() {
    return this.newOffset + this.newCount
  }

  append(lines: readonly DiffLine[]) {
    return new MacroChunk(
      [...this.content, ...lines],
      this.oldOffset,
      this.oldCount + lines.length,
      this.newOffset,
      this.newCount + lines.length,
    )
  }

  prepend(lines: readonly DiffLine[]) {
    return new MacroChunk(
      [...lines, ...this.content],
      this.oldOffset - lines.length,
      this.oldCount + lines.length,
      this.newOffset - lines.length,
      this.newCount + lines.length,
    )
  }
}

export default FileDiff
