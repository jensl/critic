import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Line from "./Changeset.Diff.Line"
import ChangesetComment from "./Changeset.Comment"
import { DiffLine } from "../resources/filediff"
import { useSelector } from "../store"
import { LineComments } from "./Changeset.Diff.Chunk"
import { ChangesetID, FileID } from "../resources/types"

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
    paddingLeft: theme.spacing(0.5),
    paddingRight: theme.spacing(0.5),
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
  comments: LineComments
}

const UnifiedLine: FunctionComponent<OwnProps> = ({
  className,
  changesetID,
  fileID,
  line,
  side,
  comments,
}) => {
  let lineID = `f${fileID}`
  if (side !== "new") lineID += ":" + line.oldID
  if (side !== "old") lineID += ":" + line.newID

  const classes = useStyles()
  const {
    isSelected,
    firstSelectedID = null,
    lastSelectedID = null,
    isRangeSelecting = false,
  } = useSelector((state) => {
    const {
      selectedIDs,
      firstSelectedID,
      lastSelectedID,
      isRangeSelecting,
    } = state.ui.selectionScope
    const isSelected = selectedIDs.has(lineID)
    if (!isSelected) return { isSelected }
    return {
      isSelected,
      firstSelectedID,
      lastSelectedID,
      isRangeSelecting,
    }
  })

  const { oldSide, newSide } = comments
  const oldMarkerClass = clsx(
    classes.marker,
    side !== "new" && {
      [classes.markerOpenIssue]: oldSide.hasOpenIssues,
      [classes.markerClosedIssue]: oldSide.hasClosedIssues,
      [classes.markerNote]:
        oldSide.hasNotes && !oldSide.hasOpenIssues && !oldSide.hasClosedIssues,
    }
  )
  const newMarkerClass = clsx(
    classes.marker,
    side !== "old" && {
      [classes.markerOpenIssue]: newSide.hasOpenIssues,
      [classes.markerClosedIssue]: newSide.hasClosedIssues,
      [classes.markerNote]:
        newSide.hasNotes && !newSide.hasOpenIssues && !newSide.hasClosedIssues,
    }
  )
  let commentItems =
    side === "old"
      ? oldSide.comments.map((comment) => (
          <ChangesetComment
            key={comment.id}
            className={classes.comment}
            comment={comment}
          />
        ))
      : newSide.comments.map((comment) => (
          <ChangesetComment
            key={comment.id}
            className={classes.comment}
            comment={comment}
          />
        ))

  if (
    isSelected &&
    firstSelectedID !== null &&
    lastSelectedID === lineID &&
    !isRangeSelecting
  ) {
    const firstLine = parseInt(
      (/^f\d+:[on](\d+)$/.exec(firstSelectedID) || ["", "0"])[1],
      10
    )
    const lastLine = side === "old" ? line.old_offset : line.new_offset
    commentItems.push(
      <ChangesetComment
        key="new-comment"
        className={classes.comment}
        location={{
          changesetID,
          fileID,
          side: side || "new",
          firstLine,
          lastLine,
        }}
      />
    )
  }

  return (
    <>
      <div
        className={clsx(className, classes.changesetDiffUnifiedLine, "line", {
          context: side === undefined,
          deleted: side === "old",
          inserted: side === "new",
        })}
      >
        <span className={clsx(classes.lineNumber, classes.oldLineNumber)}>
          {side !== "new" ? line.old_offset : null}
        </span>
        <span className={oldMarkerClass} />
        <Line
          className={clsx(classes.code, side)}
          lineID={lineID}
          content={line.content}
          side={side}
          isSelected={isSelected}
        />
        <span className={newMarkerClass} />
        <span className={clsx(classes.lineNumber, classes.newLineNumber)}>
          {side !== "old" ? line.new_offset : null}
        </span>
      </div>
      {commentItems}
    </>
  )
}

export default Registry.add("Changeset.Diff.Unified.Line", UnifiedLine)
