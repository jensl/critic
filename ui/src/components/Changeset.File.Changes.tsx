import React, { FunctionComponent, useEffect, useState } from "react"
import { useInView } from "react-intersection-observer"
import clsx from "clsx"

import Button from "@material-ui/core/Button"
import Menu from "@material-ui/core/Menu"
import MenuItem from "@material-ui/core/MenuItem"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ChangesetDiffChunk_Unified from "./Changeset.Diff.Unified.Chunk"
import ChangesetDiffChunk_SideBySide from "./Changeset.Diff.SideBySide.Chunk"
import FileDiff, { MacroChunk } from "../resources/filediff"
import { useDispatch, useSelector } from "../store"
import { ChunkComments, getCommentsForChangeset } from "../selectors/fileDiff"
import { useReview, useChangeset, useOptionalReview } from "../utils"
import Changeset from "../resources/changeset"
import { SelectionScope } from "../reducers/uiSelectionScope"
import { loadFileContent } from "../actions/filecontent"
import { assertNotNull } from "../debug"
import { DiffLine } from "../resources/diffcommon"
import LoaderBlock from "./Loader.Block"
import { loadFileDiff } from "../actions/filediff"

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

      //"& .line .code.selected": { outline: "1px solid red" },
      "& .line .code.unselected": { filter: "opacity(50%)" },
      "& .line .code:hover": { filter: "brightness(90%)" },
      "& .has-selection .line .code:hover": { filter: "none" },
      //"& .line .code.selected:hover": { filter: "brightness(90%)" },

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
  changeset: Changeset
  fileID: number
  previousChunkIndex: number | null
  nextChunkIndex: number | null
  oldOffset: number
  newOffset: number
  lineCount: number
}

const ChangesetDiffChunkSeparator: FunctionComponent<SeparatorProps> = ({
  className,
  changeset,
  fileID,
  previousChunkIndex,
  nextChunkIndex,
  oldOffset,
  newOffset,
  lineCount,
}) => {
  const dispatch = useDispatch()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)

  const fetch = (
    chunkIndex: number,
    count: number,
    where: "above" | "below",
  ) => {
    const offsetDelta = where === "below" ? lineCount - count : 0
    const first = newOffset + offsetDelta
    const last = first + count - 1
    dispatch(
      loadFileContent(
        changeset.repository,
        changeset.toCommit,
        fileID,
        first,
        last,
      ),
    ).then((fileContent) => {
      setAnchorEl(null)
      dispatch({
        type: "FILEDIFFS_UPDATE",
        changesetID: changeset.id,
        fileID,
        chunkIndex,
        operation: where === "above" ? "append" : "prepend",
        lines: fileContent.lines.map((line) =>
          line.translateOldOffset(oldOffset - newOffset),
        ),
      })
    })
  }

  const itemsAbove = []
  const itemsBelow = []

  if (lineCount > 10) {
    if (previousChunkIndex !== null)
      itemsAbove.push(
        <MenuItem
          key="10-more-above"
          onClick={() => fetch(previousChunkIndex, 10, "above")}
        >
          Show 10 more above
        </MenuItem>,
      )
    if (nextChunkIndex !== null)
      itemsBelow.push(
        <MenuItem
          key="10-more-below"
          onClick={() => fetch(nextChunkIndex, 10, "below")}
        >
          Show 10 more below
        </MenuItem>,
      )
  }

  if (lineCount > 25) {
    if (previousChunkIndex !== null)
      itemsAbove.push(
        <MenuItem
          key="25-more-above"
          onClick={() => fetch(previousChunkIndex, 25, "above")}
        >
          Show 25 more above
        </MenuItem>,
      )
    if (nextChunkIndex !== null)
      itemsBelow.push(
        <MenuItem
          key="25-more-below"
          onClick={() => fetch(nextChunkIndex, 25, "below")}
        >
          Show 25 more below
        </MenuItem>,
      )
  }

  const menuID = `chunk-separator-menu-${previousChunkIndex}-${nextChunkIndex}`

  return (
    <>
      <Button
        className={className}
        color="secondary"
        variant="contained"
        size="small"
        aria-controls={menuID}
        aria-haspopup="true"
        onClick={(ev) => setAnchorEl(ev.target as HTMLElement)}
      >
        {lineCount} lines omitted
      </Button>
      <Menu
        id={menuID}
        anchorEl={anchorEl}
        open={anchorEl !== null}
        onClose={() => setAnchorEl(null)}
      >
        {itemsAbove}
        <MenuItem
          onClick={() =>
            fetch(
              (previousChunkIndex ?? nextChunkIndex)!,
              lineCount,
              previousChunkIndex !== null ? "above" : "below",
            )
          }
        >
          Show all lines
        </MenuItem>
        {itemsBelow}
      </Menu>
    </>
  )
}

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

  const { macroChunks } = fileDiff
  if (!macroChunks) return <LoaderBlock size="small" />

  const chunks: JSX.Element[] = []
  let previousChunk: MacroChunk | null = null
  for (let index = 0; index < macroChunks.length; ++index) {
    const chunk = macroChunks[index]
    const scopeID = `chunk-${fileDiff.file}-${index}`
    const linesNotShown =
      chunk.oldOffset -
      (previousChunk !== null
        ? previousChunk.oldOffset + previousChunk.oldCount
        : 1)
    if (linesNotShown !== 0)
      chunks.push(
        <div key={index - 0.5} className={classes.linesNotShown}>
          <ChangesetDiffChunkSeparator
            changeset={changeset}
            fileID={fileDiff.file}
            previousChunkIndex={index > 0 ? index - 1 : null}
            nextChunkIndex={index}
            oldOffset={chunk.oldOffset - linesNotShown}
            newOffset={chunk.newOffset - linesNotShown}
            lineCount={linesNotShown}
          />
        </div>,
      )
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
  assertNotNull(previousChunk)

  if (fileDiff.oldLength !== null && fileDiff.newLength !== null) {
    const linesNotShown =
      previousChunk.oldEnd < fileDiff.oldLength
        ? fileDiff.oldLength - previousChunk.oldEnd
        : fileDiff.newLength - previousChunk.newEnd
    if (linesNotShown !== 0)
      chunks.push(
        <div key={macroChunks.length - 0.5} className={classes.linesNotShown}>
          <ChangesetDiffChunkSeparator
            changeset={changeset}
            fileID={fileDiff.file}
            previousChunkIndex={macroChunks.length - 1}
            nextChunkIndex={null}
            oldOffset={fileDiff.oldLength - linesNotShown}
            newOffset={fileDiff.newLength - linesNotShown}
            lineCount={linesNotShown}
          />
        </div>,
      )
  }

  return <>{chunks}</>
}

const PureChangesetFileChunks = React.memo(ChangesetFileChunks)

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
  const dispatch = useDispatch()
  const { changeset } = useChangeset()
  const review = useOptionalReview()
  const [ref, inView] = useInView()
  const selectionScope = useSelector((state) => state.ui.selectionScope)

  useEffect(() => {
    if (isExpanded && fileDiff && !fileDiff.macroChunks) {
      console.log("loading file diff chunks")
      dispatch(loadFileDiff(fileDiff.file, { changeset }))
    }
  }, [isExpanded, fileDiff])

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
