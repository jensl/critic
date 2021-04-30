import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import ChevronRightIcon from "@material-ui/icons/ChevronRight"

import Registry from "."
import ReviewState from "./Changeset.File.Header.ReviewState"
import { countChangedLines } from "../utils/FileDiff"
import File from "../resources/file"
import FileChange from "../resources/filechange"
import FileDiff from "../resources/filediff"
import ReviewableFileChange from "../resources/reviewablefilechange"

const useStyles = makeStyles((theme) => ({
  changesetFileHeader: {
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    padding: theme.spacing(0.5, 1),
    cursor: "pointer",
    ...theme.critic.monospaceFont,
  },

  chevronContainer: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    flexGrow: 0,
    paddingRight: "1rem",
  },
  chevron: {
    transform: "rotate(0deg)",
    transition: "transform 0.5s",
  },
  chevronExpanded: {
    transform: "rotate(90deg)",
    transition: "transform 0.5s",
  },

  deletedLines: {
    flexGrow: 1,
    minWidth: "3rem",
    maxWidth: "5rem",
    padding: "0 1rem",
    paddingRight: theme.spacing(1),
    textAlign: "right",
  },
  insertedLines: {
    flexGrow: 1,
    minWidth: "3rem",
    maxWidth: "5rem",
    paddingLeft: theme.spacing(1),
    textAlign: "left",
  },
  separator: {
    flexGrow: 0,
  },
  invisible: {
    visibility: "hidden",
  },
  path: {
    fontWeight: 500,
    flexGrow: 3,
  },
  state: {
    flexGrow: 0,
  },
}))

type Props = {
  className?: string
  file: File
  fileChange?: FileChange
  fileDiff?: FileDiff
  rfcs: ReadonlySet<ReviewableFileChange> | null
  isExpanded: boolean
  canCollapse: boolean
  expandFile: () => void
  collapseFile: () => void
}

const ChangesetFileHeader: FunctionComponent<Props> = ({
  className,
  file,
  fileChange,
  fileDiff,
  rfcs,
  isExpanded,
  canCollapse,
  expandFile,
  collapseFile,
}) => {
  const classes = useStyles()
  let deleted = false
  let added = false
  if (fileChange) {
    deleted = fileChange.wasDeleted
    added = fileChange.wasAdded
  }
  let deletedLines = null
  let insertedLines = null
  if (fileDiff) {
    deletedLines = `-${fileDiff.deleteCount}`
    insertedLines = `+${fileDiff.insertCount}`
  }
  const toggleExpanded = isExpanded
    ? canCollapse
      ? collapseFile
      : () => null
    : expandFile

  return (
    <div
      className={clsx(className, classes.changesetFileHeader)}
      onMouseDown={(ev) => {
        toggleExpanded()
        ev.preventDefault()
      }}
    >
      <span className={clsx(classes.chevronContainer)}>
        <ChevronRightIcon
          className={clsx(classes.chevron, {
            [classes.chevronExpanded]: isExpanded,
          })}
        />
      </span>
      <span className={classes.deletedLines}>{!added && deletedLines}</span>
      <span
        className={clsx(
          classes.separator,
          (deleted || added) && classes.invisible,
        )}
      >
        /
      </span>
      <span className={classes.insertedLines}>{!deleted && insertedLines}</span>
      <span className={classes.path}>{file.path}</span>
      <ReviewState className={classes.state} file={file} rfcs={rfcs} />
    </div>
  )
}

export default Registry.add("Changeset.File.Header", ChangesetFileHeader)
