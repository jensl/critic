import { immerable } from "immer"

export const kContextLine = 1
export const kDeletedLine = 2
export const kModifiedLine = 3
export const kReplacedLine = 4
export const kInsertedLine = 5
export const kWhitespaceLine = 6
export const kConflictLine = 7

export type DiffLineType =
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

export type PartData = string | [string, PartType, PartState]
export type DiffLineData = [DiffLineType, PartData[]]

export type DiffLineProps = {
  type: DiffLineType
  oldOffset: number
  newOffset: number
  content: readonly Part[]
  oldPlain: string
  newPlain: string
}

const toOldPlain = (content: PartData[]) =>
  content
    .map((part) =>
      typeof part === "string" ? part : part[2] <= 0 ? part[0] : "",
    )
    .join("")
const toNewPlain = (content: PartData[]) =>
  content
    .map((part) =>
      typeof part === "string" ? part : part[2] >= 0 ? part[0] : "",
    )
    .join("")

export class DiffLine {
  [immerable] = true

  constructor(
    readonly type: DiffLineType,
    readonly oldOffset: number,
    readonly newOffset: number,
    readonly content: readonly Part[],
    readonly oldPlain: string,
    readonly newPlain: string,
  ) {}

  static new(props: DiffLineProps) {
    return new DiffLine(
      props.type,
      props.oldOffset,
      props.newOffset,
      props.content,
      props.oldPlain,
      props.newPlain,
    )
  }

  static make(
    diffLines: Iterable<DiffLineData>,
    oldOffset: number,
    newOffset: number,
  ) {
    function* generate() {
      for (const value of diffLines) {
        const [type, content] = value
        const oldPlain = toOldPlain(content)
        const newPlain = type === kContextLine ? oldPlain : toNewPlain(content)
        yield DiffLine.new({
          type,
          oldOffset,
          newOffset,
          content: Part.make(content),
          oldPlain,
          newPlain,
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
    return this.type !== kInsertedLine ? `o${this.oldOffset}` : ""
  }
  get newID() {
    return this.type !== kDeletedLine ? `n${this.newOffset}` : ""
  }

  get oldLineNumber() {
    return this.type !== kInsertedLine ? this.oldOffset : null
  }
  get newLineNumber() {
    return this.type !== kDeletedLine ? this.newOffset : null
  }

  translateOldOffset(delta: number) {
    return new DiffLine(
      this.type,
      this.oldOffset + delta,
      this.newOffset,
      this.content,
      this.oldPlain,
      this.newPlain,
    )
  }
}

export class Part {
  [immerable] = true

  constructor(
    readonly content: string,
    readonly type: PartType = kNeutralPartType,
    readonly state: PartState = kNeutralPartState,
  ) {}

  static make(parts: PartData[]) {
    return parts.map((part) =>
      Array.isArray(part) ? new Part(...part) : new Part(part),
    )
  }
}
