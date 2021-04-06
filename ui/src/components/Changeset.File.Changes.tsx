import React, { FunctionComponent } from "react"
import { useInView } from "react-intersection-observer"
import clsx from "clsx"

import Button from "@material-ui/core/Button"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ChangesetDiffChunk_Unified from "./Changeset.Diff.Unified.Chunk"
import ChangesetDiffChunk_SideBySide from "./Changeset.Diff.SideBySide.Chunk"
import FileDiff, { MacroChunk } from "../resources/filediff"
import { useSelector } from "../store"
import { ChunkComments, getCommentsForChangeset } from "../selectors/fileDiff"
import { useReview, useChangeset } from "../utils"
import Changeset from "../resources/changeset"
import { SelectionScope } from "../reducers/uiSelectionScope"
import { pure } from "recompose"

const useStyles = makeStyles((theme) => {
  const { diff, syntax, monospaceFont } = theme.critic
  return {
    changesetFileChanges: {
      ...diff.background,
      ...diff.border,
      ...monospaceFont,

      paddingTop: theme.spacing(1),
      paddingBottom: theme.spacing(1),

      "& .code span": { display: "inline-block" },
      "& .code span:first-child": { paddingLeft: theme.spacing(0.5) },

      "& .code": syntax.base,
      "& .code .operator": syntax.operator,
      "& .code .identifier": syntax.identifier,
      "& .code .keyword": syntax.keyword,
      "& .code .character": syntax.character,
      "& .code .string": syntax.string,
      "& .code .comment": syntax.comment,
      "& .code .integer": syntax.integer,
      "& .code .number": syntax.number,
      "& .code .ppDirective": syntax.ppDirective,

      "& .line .code.selected": { filter: "brightness(85%)" },
      "& .line .code:hover": { filter: "brightness(85%)" },
      "& .line .code.selected:hover": { filter: "brightness(75%)" },

      "& .line.context .code": diff.context,
      "& .line.deleted .code.old": diff.deletedLine,
      "& .line.deleted .code .deleted": diff.deletedCode,
      "& .line.inserted .code.new": diff.insertedLine,
      "& .line.inserted .code .inserted": diff.insertedCode,
      "& .side-by-side .line.modified .code.old": diff.modifiedLineOld,
      "& .side-by-side .line.modified .code.new": diff.modifiedLineNew,
      "& .unified .line.modified .code.old": diff.deletedLine,
      "& .unified .line.whitespace .code.old": diff.deletedLine,
      "& .unified .line.modified .code.new": diff.insertedLine,
      "& .unified .line.whitespace .code.new": diff.insertedLine,
      "& .side-by-side .line.modified .code.old .deleted": diff.deletedCode,
      "& .side-by-side .line.modified .code.new .inserted": diff.insertedCode,
      "& .unified .line.modified .code.old .deleted": diff.deletedCodeDark,
      "& .unified .line.whitespace .code.old .deleted": diff.deletedCodeDark,
      "& .unified .line.modified .code.new .inserted": diff.insertedCodeDark,
      "& .unified .line.whitespace .code.new .inserted": diff.insertedCodeDark,
      "& .line.replaced .code.old": diff.deletedLine,
      "& .line.replaced .code.new": diff.insertedLine,
      "& .line.whitespace .code": diff.context,
      "& .line.whitespace .code.old .deleted": diff.deletedCode,
      "& .line.whitespace .code.new .inserted": diff.insertedCode,
    },

    changesetFileChangesChunk: {
      margin: theme.spacing(1, 0),
    },

    linesNotShown: {
      display: "flex",
      justifyContent: "space-around",
      padding: theme.spacing(1, 0),
    },
  }
})

type SeparatorProps = {
  className?: string
  lineCount: number
}

const ChangesetDiffChunkSeparator: FunctionComponent<SeparatorProps> = ({
  className,
  lineCount,
}) => (
  <Button
    className={className}
    color="secondary"
    variant="contained"
    size="small"
  >
    {lineCount} lines omitted
  </Button>
)

type ChunksProps = {
  classes: ReturnType<typeof useStyles>
  changeset: Changeset
  fileDiff: FileDiff
  variant: "unified" | "side-by-side"
  comments: readonly ChunkComments[] | null
  selectionScope: SelectionScope | null
  inView: boolean
}

const ChangesetFileChunks: FunctionComponent<ChunksProps> = ({
  classes,
  changeset,
  fileDiff,
  variant,
  comments,
  selectionScope,
  inView,
}) => {
  const ChangesetDiffChunk =
    variant === "side-by-side"
      ? ChangesetDiffChunk_SideBySide
      : ChangesetDiffChunk_Unified

  const chunks: JSX.Element[] = []
  let previousChunk: MacroChunk | null = null
  for (let index = 0; index < fileDiff.macroChunks.length; ++index) {
    const chunk = fileDiff.macroChunks[index]
    const scopeID = `chunk-${fileDiff.file}-${index}`
    if (previousChunk !== null) {
      const linesNotShown =
        chunk.oldOffset - (previousChunk.oldOffset + previousChunk.oldCount)
      chunks.push(
        <div key={index - 0.5} className={classes.linesNotShown}>
          <ChangesetDiffChunkSeparator lineCount={linesNotShown} />
        </div>,
      )
    }
    chunks.push(
      <ChangesetDiffChunk
        className={classes.changesetFileChangesChunk}
        key={index}
        scopeID={scopeID}
        changesetID={changeset.id}
        fileID={fileDiff.file}
        chunk={chunk}
        comments={comments?.[index] || null}
        selectionScope={
          selectionScope?.scopeID === scopeID ? selectionScope : null
        }
        inView={inView}
      />,
    )
    previousChunk = chunk
  }

  return <>{chunks}</>
}

const PureChangesetFileChunks = pure(ChangesetFileChunks)

type Props = {
  className?: string
  fileDiff?: FileDiff
  variant: "unified" | "side-by-side"
  comments: readonly ChunkComments[] | null
  isExpanded: boolean
  mountOnExpand: boolean
}

const ChangesetFileChanges: FunctionComponent<Props> = ({
  className,
  fileDiff,
  variant,
  comments,
  isExpanded,
  mountOnExpand,
}) => {
  const classes = useStyles()
  const { changeset } = useChangeset()
  const [ref, inView] = useInView()
  const selectionScope = useSelector((state) => state.ui.selectionScope)

  if (!fileDiff || (mountOnExpand && !isExpanded)) return null

  const thisSelectionScope = selectionScope.scopeID?.startsWith(
    `chunk-${fileDiff.file}-`,
  )
    ? selectionScope
    : null

  return (
    <div ref={ref} className={clsx(className, classes.changesetFileChanges)}>
      <PureChangesetFileChunks
        classes={classes}
        changeset={changeset}
        fileDiff={fileDiff}
        variant={variant}
        comments={comments}
        selectionScope={thisSelectionScope}
        inView={isExpanded && inView}
      />
    </div>
  )
}

export default Registry.add("Changeset.File.Changes", ChangesetFileChanges)
