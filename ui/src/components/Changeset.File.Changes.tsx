import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, useTheme, Theme } from "@material-ui/core/styles"
import useMediaQuery from "@material-ui/core/useMediaQuery"

import Registry from "."
import { lineCommentsPerChunk } from "./Changeset.Diff.Chunk"
import ChangesetDiffChunk_Unified from "./Changeset.Diff.Unified.Chunk"
import ChangesetDiffChunk_SideBySide from "./Changeset.Diff.SideBySide.Chunk"
import FileDiff, { MacroChunk } from "../resources/filediff"
import { useSelector } from "../store"
import { getCommentsForChangeset } from "../selectors/fileDiff"
import { useReview, useChangeset } from "../utils"

const useStyles = makeStyles((theme: Theme) => ({
  changesetFileChanges: {
    ...theme.critic.monospaceFont,

    "& .code span": { display: "inline-block" },
    "& .code span:first-child": { paddingLeft: theme.spacing(0.5) },

    "& .code": theme.critic.syntax.base,
    "& .code .operator": theme.critic.syntax.operator,
    "& .code .identifier": theme.critic.syntax.identifier,
    "& .code .keyword": theme.critic.syntax.keyword,
    "& .code .character": theme.critic.syntax.character,
    "& .code .string": theme.critic.syntax.string,
    "& .code .comment": theme.critic.syntax.comment,
    "& .code .integer": theme.critic.syntax.integer,
    "& .code .number": theme.critic.syntax.number,
    "& .code .ppDirective": theme.critic.syntax.ppDirective,

    "& .line .code.selected": { filter: "brightness(85%)" },
    "& .line .code:hover": { filter: "brightness(85%)" },
    "& .line .code.selected:hover": { filter: "brightness(75%)" },

    "& .line.context .code": theme.critic.diff.context,
    "& .line.deleted .code.old": theme.critic.diff.deletedLine,
    "& .line.deleted .code .deleted": theme.critic.diff.deletedCodeDark,
    "& .line.inserted .code.new": theme.critic.diff.insertedLine,
    "& .line.inserted .code .inserted": theme.critic.diff.insertedCodeDark,
    "& .line.modified .code": theme.critic.diff.modifiedLine,
    "& .line.modified .code.old .deleted": theme.critic.diff.deletedCode,
    "& .line.modified .code.new .inserted": theme.critic.diff.insertedCode,
    "& .line.replaced .code.old": theme.critic.diff.deletedLine,
    "& .line.replaced .code.new": theme.critic.diff.insertedLine,
    "& .line.whitespace .code": theme.critic.diff.context,
    "& .line.whitespace .code.old .deleted": theme.critic.diff.deletedCode,
    "& .line.whitespace .code.new .inserted": theme.critic.diff.insertedCode,
  },

  changesetFileChangesChunk: {
    margin: `${theme.spacing(1)}px 0`,
  },

  linesNotShown: {
    textAlign: "center",
  },
}))

type Props = {
  className?: string
  fileDiff: FileDiff
  variant?: "unified" | "side-by-side"
}

const ChangesetFileChanges: FunctionComponent<Props> = ({
  className,
  fileDiff,
  variant,
}) => {
  const classes = useStyles()
  const theme = useTheme()
  const useSideBySide = useMediaQuery(theme.breakpoints.up("lg"))
  const review = useReview()
  const { changeset } = useChangeset()
  const commentsForChangeset = useSelector((state) =>
    getCommentsForChangeset(state, { review, changeset })
  )

  if (fileDiff === null) return null
  const ChangesetDiffChunk =
    variant === "side-by-side" || (!variant && useSideBySide)
      ? ChangesetDiffChunk_SideBySide
      : ChangesetDiffChunk_Unified

  const byFile = commentsForChangeset.byFile.get(fileDiff.file)

  const chunks: JSX.Element[] = []
  let previousChunk: MacroChunk | null = null
  for (let index = 0; index < fileDiff.macroChunks.length; ++index) {
    const chunk = fileDiff.macroChunks[index]
    if (previousChunk !== null) {
      const linesNotShown =
        chunk.oldOffset - (previousChunk.oldOffset + previousChunk.oldCount)
      chunks.push(
        <div className={classes.linesNotShown} key={index - 0.5}>
          {linesNotShown} lines not shown
        </div>
      )
    }
    chunks.push(
      <ChangesetDiffChunk
        className={classes.changesetFileChangesChunk}
        key={index}
        index={index}
        changesetID={changeset.id}
        fileID={fileDiff.file}
        chunk={chunk}
        comments={lineCommentsPerChunk(byFile, chunk)}
      />
    )
    previousChunk = chunk
  }
  return (
    <div className={clsx(className, classes.changesetFileChanges)}>
      {chunks}
    </div>
  )
}

export default Registry.add("Changeset.File.Changes", ChangesetFileChanges)
