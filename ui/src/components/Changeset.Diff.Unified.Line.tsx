import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Line from "./Changeset.Diff.Line"
import ChangesetComment from "./Changeset.Comment"
import {
  kContextLine,
  kDeletedLine,
  kInsertedLine,
  kModifiedLine,
  kReplacedLine,
  kWhitespaceLine,
  DiffLine,
} from "../resources/filediff"
import { ChangesetID, FileID } from "../resources/types"
import { SelectionScope } from "../reducers/uiSelectionScope"
import { pure } from "recompose"
import { LineComments } from "../selectors/fileDiff"
import { locationFromSelectionScope } from "../utils/Comment"

const useStyles = makeStyles((theme) => ({
  changesetDiffUnifiedLine: {
    display: "flex",
    flexDirection: "row",
    lineHeight: "1.3",
  },

  lineNumber: {
    minWidth: "5rem",
    flexGrow: 0,

    [theme.breakpoints.down("sm")]: {
      minWidth: "2rem",
    },
  },

  oldLineNumber: {
    textAlign: "right",
    paddingRight: theme.spacing(1),
  },
  marker: {
    minWidth: theme.spacing(1),
  },
  markerOpenIssue: {
    backgroundColor: theme.palette.issue.open,
  },
  markerClosedIssue: {
    backgroundColor: theme.palette.issue.closed,
  },
  markerNote: {
    backgroundColor: theme.palette.note,
  },
  code: {
    whiteSpace: "pre-wrap",
    flexGrow: 1,
  },
  newLineNumber: {
    textAlign: "left",
    paddingLeft: theme.spacing(1),
  },

  comment: {
    marginLeft: "10rem",
    marginRight: "10rem",
    marginBottom: theme.spacing(1),
    background: "rgba(0,0,0,5%)",
    borderBottomLeftRadius: 4,
    borderBottomRightRadius: 4,
  },
}))

type OwnProps = {
  className?: string
  changesetID: ChangesetID
  fileID: FileID
  line: DiffLine
  side?: "old" | "new"
  comments: LineComments | null
  selectionScope: SelectionScope | null
  inView: boolean
}

const LINE_ID_PATTERN = {
  old: "fd+:o(d+)(?::nd+)?",
  new: "fd+(?::od+)?:n(d+)",
}

const UnifiedLine: FunctionComponent<OwnProps> = ({
  className,
  changesetID,
  fileID,
  line,
  side,
  comments,
  selectionScope,
  inView,
}) => {
  const { type, oldID, oldOffset, newID, newOffset } = line

  let lineID = `f${fileID}`
  if (side !== "new") lineID += ":" + oldID
  if (side !== "old") lineID += ":" + newID

  const classes = useStyles()

  const {
    lastSelectedID = null,
    selectedIDs = null,
    isRangeSelecting = false,
  } = selectionScope || {}

  const isSelected = selectedIDs?.has(lineID) ?? false

  const { oldSide = null, newSide = null } = comments ?? {}
  const oldMarkerClass = clsx(
    classes.marker,
    side !== "new" && {
      [classes.markerOpenIssue]: oldSide?.hasOpenIssues,
      [classes.markerClosedIssue]: oldSide?.hasClosedIssues,
      [classes.markerNote]:
        oldSide?.hasNotes &&
        !oldSide?.hasOpenIssues &&
        !oldSide?.hasClosedIssues,
    },
  )
  const newMarkerClass = clsx(
    classes.marker,
    side !== "old" && {
      [classes.markerOpenIssue]: newSide?.hasOpenIssues,
      [classes.markerClosedIssue]: newSide?.hasClosedIssues,
      [classes.markerNote]:
        newSide?.hasNotes &&
        !newSide?.hasOpenIssues &&
        !newSide?.hasClosedIssues,
    },
  )
  let commentItems =
    (side === "old"
      ? oldSide?.comments.map((comment) => (
          <ChangesetComment
            key={comment.id}
            className={classes.comment}
            comment={comment}
          />
        ))
      : newSide?.comments.map((comment) => (
          <ChangesetComment
            key={comment.id}
            className={classes.comment}
            comment={comment}
          />
        ))) ?? []

  if (selectionScope && lastSelectedID === lineID && !isRangeSelecting) {
    commentItems.push(
      <ChangesetComment
        key="new-comment"
        className={classes.comment}
        location={{
          changesetID,
          ...locationFromSelectionScope(selectionScope),
        }}
      />,
    )
  }

  return (
    <>
      <div
        className={clsx(className, classes.changesetDiffUnifiedLine, "line", {
          context: type === kContextLine,
          deleted: type === kDeletedLine,
          inserted: type === kInsertedLine,
          modified: type === kModifiedLine,
          replaced: type === kReplacedLine,
          whitespace: type === kWhitespaceLine,
        })}
      >
        <span className={clsx(classes.lineNumber, classes.oldLineNumber)}>
          {side !== "new" ? oldOffset : null}
        </span>
        <span className={oldMarkerClass} />
        <Line
          className={clsx(classes.code, side)}
          lineID={lineID}
          line={line}
          side={side}
          isSelected={isSelected}
          inView={inView}
        />
        <span className={newMarkerClass} />
        <span className={clsx(classes.lineNumber, classes.newLineNumber)}>
          {side !== "old" ? newOffset : null}
        </span>
      </div>
      {commentItems}
    </>
  )
}

export default Registry.add("Changeset.Diff.Unified.Line", pure(UnifiedLine))
