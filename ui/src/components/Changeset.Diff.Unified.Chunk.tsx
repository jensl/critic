import React, { FunctionComponent, MouseEvent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { ChunkComments } from "./Changeset.Diff.Chunk"
import Line from "./Changeset.Diff.Unified.Line"
import SelectionScope from "./Selection.Scope"
import {
  kContextLine,
  kDeletedLine,
  kInsertedLine,
  MacroChunk,
} from "../resources/filediff"
import { FileID, ChangesetID } from "../resources/types"

const useStyles = makeStyles((theme) => ({
  changesetDiffUnifiedChunk: {},
}))

interface OwnProps {
  className?: string
  changesetID: ChangesetID
  fileID: FileID
  index: number
  chunk: MacroChunk
  comments: ChunkComments
}

const UnifiedChunk: FunctionComponent<OwnProps> = ({
  className,
  changesetID,
  fileID,
  index,
  chunk,
  comments,
}) => {
  const classes = useStyles()
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
      comments: comments.get(line.id)!,
    }
    if (type === kContextLine) {
      flush()
      lines.push(<Line key={keyCounter++} {...commonProps} />)
    } else {
      if (type !== kInsertedLine)
        (deleted || (deleted = [])).push(
          <Line key={keyCounter++} {...commonProps} side="old" />
        )
      if (type !== kDeletedLine)
        (inserted || (inserted = [])).push(
          <Line key={keyCounter++} {...commonProps} side="new" />
        )
    }
  }

  flush()

  const selector = (event: MouseEvent) => {
    let target: HTMLElement | null = event.target as HTMLElement
    while (target) {
      if (target.classList.contains("code")) return ".code"
      else if (target.classList.contains(classes.changesetDiffUnifiedChunk))
        break
      target = target.parentElement
    }
    return null
  }

  return (
    <SelectionScope
      scopeID={`chunk_${fileID}_${index}`}
      className={clsx(className, classes.changesetDiffUnifiedChunk)}
      selector={selector}
      elementToID={(element: HTMLElement) => element.dataset.lineId!}
    >
      {lines}
    </SelectionScope>
  )
}

export default Registry.add("Changeset.Diff.Unified.Chunk", UnifiedChunk)
