import { Immutable } from "immer"

import { any } from "../utils"
import { CommentsByFileValue } from "../selectors/fileDiff"
import { MacroChunk, kInsertedLine, kDeletedLine } from "../resources/filediff"
import Comment from "../resources/comment"

export type LineSideComments = {
  hasOpenIssues: boolean
  hasClosedIssues: boolean
  hasNotes: boolean
  comments: readonly Comment[]
}

export type LineComments = {
  oldSide: LineSideComments
  newSide: LineSideComments
}

export type ChunkComments = Map<string, LineComments>

const hasOpenIssues = (comments: readonly Comment[]) =>
  any(
    comments,
    (comment) => comment.type === "issue" && comment.state === "open"
  )
const hasClosedIssues = (comments: readonly Comment[]) =>
  any(
    comments,
    (comment) => comment.type === "issue" && comment.state !== "open"
  )
const hasNotes = (comments: readonly Comment[]) =>
  any(comments, (comment) => comment.type === "note")

export const lineCommentsPerChunk = (
  byFile: Immutable<CommentsByFileValue> | undefined,
  chunk: MacroChunk
): ChunkComments => {
  const result = new Map<string, LineComments>()
  for (const line of chunk.content) {
    const oldSide: LineSideComments = {
      hasOpenIssues: false,
      hasClosedIssues: false,
      hasNotes: false,
      comments: [],
    }
    const newSide: LineSideComments = {
      hasOpenIssues: false,
      hasClosedIssues: false,
      hasNotes: false,
      comments: [],
    }
    if (byFile) {
      const { byLine, byLinePrimary } = byFile
      if (line.type !== kInsertedLine) {
        const byLineOld = byLine.get(line.oldID) || []
        oldSide.hasOpenIssues = hasOpenIssues(byLineOld)
        oldSide.hasClosedIssues = hasClosedIssues(byLineOld)
        oldSide.hasNotes = hasNotes(byLineOld)
        oldSide.comments = byLinePrimary.get(line.oldID) || []
      }
      if (line.type !== kDeletedLine) {
        const byLineNew = byLine.get(line.newID) || []
        newSide.hasOpenIssues = hasOpenIssues(byLineNew)
        newSide.hasClosedIssues = hasClosedIssues(byLineNew)
        newSide.hasNotes = hasNotes(byLineNew)
        newSide.comments = byLinePrimary.get(line.newID) || []
      }
    }
    result.set(line.id, { oldSide, newSide })
  }
  return result
}
