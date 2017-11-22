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

import { primaryMap } from "../reducers/resource"

export const kContextLine = 1
export const kDeletedLine = 2
export const kModifiedLine = 3
export const kReplacedLine = 4
export const kInsertedLine = 5
export const kWhitespaceLine = 6
export const kConflictLine = 7

type DiffLineType =
  | typeof kContextLine
  | typeof kDeletedLine
  | typeof kModifiedLine
  | typeof kReplacedLine
  | typeof kInsertedLine
  | typeof kWhitespaceLine
  | typeof kConflictLine

export const kTokenTypes = [
  null,
  "operator",
  "identifier",
  "keyword",
  "character",
  "string",
  "comment",
  "integer",
  "number",
  "ppDirective",
]

type FileDiffData = {
  file: number
  changeset: number
  old_is_binary: boolean
  old_syntax: string
  old_length: number
  old_linebreak: boolean
  new_is_binary: boolean
  new_syntax: string
  new_length: number
  new_linebreak: boolean
  macro_chunks: MacroChunkData[]
}

type FileDiffProps = {
  file: number
  changeset: number
  old_is_binary: boolean
  old_syntax: string
  old_length: number
  old_linebreak: boolean
  new_is_binary: boolean
  new_syntax: string
  new_length: number
  new_linebreak: boolean
  macro_chunks: readonly MacroChunk[]
}

class FileDiff {
  constructor(
    readonly file: number,
    readonly changeset: number,
    readonly oldIsBinary: boolean,
    readonly oldSyntax: string,
    readonly oldLength: number,
    readonly oldLinebreak: boolean,
    readonly newIsBinary: boolean,
    readonly newSyntax: string,
    readonly newLength: number,
    readonly newLinebreak: boolean,
    readonly macroChunks: readonly MacroChunk[]
  ) {}

  static new(props: FileDiffProps) {
    return new FileDiff(
      props.file,
      props.changeset,
      props.old_is_binary,
      props.old_syntax,
      props.old_length,
      props.old_linebreak,
      props.new_is_binary,
      props.new_syntax,
      props.new_length,
      props.new_linebreak,
      props.macro_chunks
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
    (filediff) => `${filediff.changeset}:${filediff.file}`
  )

  get props(): FileDiffProps {
    return {
      ...this,
      old_is_binary: this.oldIsBinary,
      old_syntax: this.oldSyntax,
      old_length: this.oldLength,
      old_linebreak: this.oldLinebreak,
      new_is_binary: this.newIsBinary,
      new_syntax: this.newSyntax,
      new_length: this.newLength,
      new_linebreak: this.newLinebreak,
      macro_chunks: this.macroChunks,
    }
  }
}

export type MacroChunkData = [
  content: DiffLineData[],
  old_offset: number,
  old_count: number,
  new_offset: number,
  new_count: number
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
  constructor(
    readonly content: readonly DiffLine[],
    readonly oldOffset: number,
    readonly oldCount: number,
    readonly newOffset: number,
    readonly newCount: number
  ) {}

  static new(props: MacroChunkProps) {
    return new MacroChunk(
      props.content,
      props.old_offset,
      props.old_count,
      props.new_offset,
      props.new_count
    )
  }

  static make(macroChunks: MacroChunkData[]) {
    function* generate() {
      if (macroChunks !== null)
        for (const value of macroChunks) {
          const [content, old_offset, old_count, new_offset, new_count] = value
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
}

export const kNeutralPartType = 0
export const kOperatorPartType = 1
export const kIdentifierPartType = 2
export const kKeywordPartType = 3
export const kCharacterPartType = 4
export const kStringPartType = 5
export const kCommentPartType = 6
export const kIntegerPartType = 7
export const kFloatPartType = 8
export const kPreprocessingPartType = 9

export type PartType =
  | typeof kNeutralPartType
  | typeof kOperatorPartType
  | typeof kIdentifierPartType
  | typeof kKeywordPartType
  | typeof kCharacterPartType
  | typeof kStringPartType
  | typeof kCommentPartType
  | typeof kIntegerPartType
  | typeof kFloatPartType
  | typeof kPreprocessingPartType

export const kDeletedPartState = -2
export const kOldPartState = -1
export const kNeutralPartState = 0
export const kNewPartState = 1
export const kInsertedPartState = 2

export type PartState =
  | typeof kDeletedPartState
  | typeof kOldPartState
  | typeof kNeutralPartState
  | typeof kNewPartState
  | typeof kInsertedPartState

type PartData = string | [string, PartType, PartState]
type DiffLineData = [DiffLineType, PartData[]]

type DiffLineProps = {
  type: DiffLineType
  old_offset: number
  new_offset: number
  content: readonly Part[]
}

export class DiffLine {
  constructor(
    readonly type: DiffLineType,
    readonly old_offset: number,
    readonly new_offset: number,
    readonly content: readonly Part[]
  ) {}

  static new(props: DiffLineProps) {
    return new DiffLine(
      props.type,
      props.old_offset,
      props.new_offset,
      props.content
    )
  }

  static make(diffLines: DiffLineData[], oldOffset: number, newOffset: number) {
    function* generate() {
      for (const value of diffLines) {
        const [type, content] = value
        yield DiffLine.new({
          type,
          old_offset: oldOffset,
          new_offset: newOffset,
          content: Part.make(content),
        })
        if (type !== kDeletedLine) ++newOffset
        if (type !== kInsertedLine) ++oldOffset
      }
    }
    return Array.from(generate())
  }

  get id() {
    switch (this.type) {
      case kDeletedLine:
        return this.oldID
      case kInsertedLine:
        return this.newID
      default:
        return `${this.oldID}:${this.newID}`
    }
  }

  get oldID() {
    return this.type !== kInsertedLine ? `o${this.old_offset}` : ""
  }
  get newID() {
    return this.type !== kDeletedLine ? `n${this.new_offset}` : ""
  }

  get oldLineNumber() {
    return this.type !== kInsertedLine ? this.old_offset : null
  }
  get newLineNumber() {
    return this.type !== kDeletedLine ? this.new_offset : null
  }
}

export class Part {
  constructor(
    readonly content: string,
    readonly type: PartType = kNeutralPartType,
    readonly state: PartState = kNeutralPartState
  ) {}

  static make(parts: PartData[]) {
    return parts.map((part) =>
      Array.isArray(part) ? new Part(...part) : new Part(part)
    )
  }
}

export default FileDiff
