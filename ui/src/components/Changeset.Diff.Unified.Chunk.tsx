import React, { FunctionComponent, MouseEvent } from "react"
import clsx from "clsx"

import Registry from "."
import { ChunkProps } from "./Changeset.Diff.Chunk"
import Line from "./Changeset.Diff.Unified.Line"
import SelectionScope from "./Selection.Scope"
import {
  DiffLine,
  kContextLine,
  kDeletedLine,
  kInsertedLine,
} from "../resources/diffcommon"
import { locationFromSelectionScope } from "../utils/Comment"
import { SelectorFunc } from "../actions/uiSelectionScope"

const UnifiedChunk: FunctionComponent<ChunkProps> = ({
  className,
  changesetID,
  fileID,
  scopeID,
  chunk,
  comments,
  selectionScope,
  inView,
}) => {
  const lines = []
  var deleted: JSX.Element[] = []
  var inserted: JSX.Element[] = []
  var keyCounter = 0

  const flush = () => {
    if (deleted.length !== 0) {
      lines.push(...deleted)
      deleted = []
    }
    if (inserted.length !== 0) {
      lines.push(...inserted)
      inserted = []
    }
  }

  const {
    lastSelectedID = null,
    selectedIDs = null,
    isRangeSelecting = false,
    isPending = false,
  } = selectionScope || {}

  const hasSelection = selectionScope !== null && !isPending

  const generateLine = (line: DiffLine, side?: "old" | "new") => {
    let lineID = `f${fileID}:`
    if (side !== "new") lineID += line.oldID
    if (side !== "old") lineID += line.newID
    const isSelected = selectedIDs?.has(lineID) ?? false
    const showCommentAt =
      selectionScope !== null && lastSelectedID === lineID && !isRangeSelecting
        ? {
            changesetID,
            ...locationFromSelectionScope(selectionScope),
          }
        : null
    return (
      <Line
        key={lineID}
        lineID={lineID}
        line={line}
        side={side}
        comments={comments?.get(line.id) ?? null}
        isSelected={isSelected}
        hasSelection={hasSelection}
        showCommentAt={showCommentAt}
        inView={inView}
      />
    )
  }

  for (const line of chunk.content) {
    const { type } = line
    if (type === kContextLine) {
      flush()
      lines.push(generateLine(line))
    } else {
      if (type !== kInsertedLine) deleted.push(generateLine(line, "old"))
      if (type !== kDeletedLine) inserted.push(generateLine(line, "new"))
    }
  }

  flush()

  const getLineType = (target: HTMLElement | null) => {
    while (target) {
      const { classList } = target
      if (classList.contains("code")) {
        if (classList.contains("old")) return "deleted"
        else if (classList.contains("new")) return "inserted"
        else return "context"
      } else if (classList.contains("unified")) break
      target = target.parentElement
    }
    return null
  }

  const selector: SelectorFunc = (anchor, focus) => {
    const anchorType = getLineType(anchor)
    if (anchorType === "deleted") return ".code:not(.new)"
    if (anchorType === "inserted") return ".code:not(.old)"
    const focusType = getLineType(focus)
    if (focusType === "deleted") return ".code:not(.new)"
    if (anchorType || focusType) return ".code:not(.old)"
    return null
  }

  return (
    <SelectionScope
      scopeID={scopeID}
      className={clsx(className, "unified")}
      selector={selector}
      elementToID={(element: HTMLElement) => element.dataset.lineId!}
    >
      {lines}
    </SelectionScope>
  )
}

// export default Registry.add(
//   "Changeset.Diff.Unified.Chunk",
//   React.memo(UnifiedChunk),
// )

export default React.memo(UnifiedChunk)
