import React, { MouseEvent, FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import SelectionScope from "./Selection.Scope"
import Line from "./Changeset.Diff.SideBySide.Line"
import { MacroChunk } from "../resources/filediff"
import { ChunkComments } from "./Changeset.Diff.Chunk"
import { ChangesetID, FileID } from "../resources/types"

const useStyles = makeStyles((theme: Theme) => ({
  changesetDiffSideBySideChunk: {
    margin: `${theme.spacing(0.5)}px 0`,
  },
}))

type Props = {
  className?: string
  changesetID: ChangesetID
  fileID: FileID
  index: number
  chunk: MacroChunk
  comments: ChunkComments
}

const SideBySideChunk: FunctionComponent<Props> = ({
  className,
  changesetID,
  fileID,
  index,
  chunk,
  comments,
}: Props) => {
  const classes = useStyles()
  const lines = chunk.content.map((line, index) => (
    <Line
      key={index}
      changesetID={changesetID}
      fileID={fileID}
      line={line}
      comments={comments.get(line.id)!}
    />
  ))
  const calculateSelector = (element: HTMLElement): string | null => {
    while (!element.dataset.lineId && !element.classList.contains("line")) {
      if (!element.parentElement) return null
      element = element.parentElement
    }
    if (!element.dataset.lineId) return null
    if (element.dataset.lineId.indexOf(":o") !== -1) return ".code.old"
    else return ".code.new"
  }
  return (
    <SelectionScope
      scopeID={`chunk_${fileID}_${index}`}
      className={clsx(className, classes.changesetDiffSideBySideChunk)}
      selector={(ev: MouseEvent) => calculateSelector(ev.target as HTMLElement)}
      elementToID={(element: HTMLElement) => element.dataset.lineId!}
    >
      {lines}
    </SelectionScope>
  )
}

export default Registry.add("Changeset.Diff.SideBySide.Chunk", SideBySideChunk)
