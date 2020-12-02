import React, { FunctionComponent, MouseEvent } from "react"
import clsx from "clsx"

import Registry from "."
import { ChunkProps } from "./Changeset.Diff.Chunk"
import Line from "./Changeset.Diff.Unified.Line"
import SelectionScope from "./Selection.Scope"
import {
  kContextLine,
  kDeletedLine,
  kInsertedLine,
} from "../resources/filediff"
import { pure } from "recompose"

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
  var deleted: null | JSX.Element[] = null
  var inserted: null | JSX.Element[] = null
  var keyCounter = 0

  const flush = () => {
    if (deleted !== null) lines.push(...deleted)
    if (inserted !== null) lines.push(...inserted)
    deleted = inserted = null
  }

  for (const line of chunk.content) {
    const { type } = line
    const commonProps = {
      changesetID,
      fileID,
      line,
      comments: comments?.get(line.id) ?? null,
      selectionScope,
      inView,
    }
    if (type === kContextLine) {
      flush()
      lines.push(<Line key={keyCounter++} {...commonProps} />)
    } else {
      if (type !== kInsertedLine)
        (deleted || (deleted = [])).push(
          <Line key={keyCounter++} {...commonProps} side="old" />,
        )
      if (type !== kDeletedLine)
        (inserted || (inserted = [])).push(
          <Line key={keyCounter++} {...commonProps} side="new" />,
        )
    }
  }

  flush()

  const selector = (event: MouseEvent) => {
    let target: HTMLElement | null = event.target as HTMLElement
    while (target) {
      const { classList } = target
      if (classList.contains("code")) {
        if (classList.contains("old")) return ".code:not(.new)"
        else if (classList.contains("new")) return ".code:not(.old)"
        else return ".code"
      } else if (classList.contains("unified")) break
      target = target.parentElement
    }
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

export default Registry.add("Changeset.Diff.Unified.Chunk", pure(UnifiedChunk))
