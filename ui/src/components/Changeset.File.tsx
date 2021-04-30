import React, { FunctionComponent } from "react"
import { useHistory, useLocation } from "react-router"
import clsx from "clsx"

import Collapse from "@material-ui/core/Collapse"
import Paper, { PaperProps } from "@material-ui/core/Paper"
import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import ChangesetFileHeader from "./Changeset.File.Header"
import ChangesetFileChanges from "./Changeset.File.Changes"
import ChangesetFileFooter from "./Changeset.File.Footer"
import { setWith, setWithout, useChangeset, useResource } from "../utils"
import { pathWithExpandedFiles } from "../utils/Changeset"
import { ChunkComments } from "../selectors/fileDiff"
import ReviewableFileChange from "../resources/reviewablefilechange"

const useStyles = makeStyles((theme: Theme) => ({
  root: {
    paddingLeft: theme.spacing(2),
    paddingRight: theme.spacing(2),
  },
  collapsed: { margin: theme.spacing(0.5, 0) },
  expanded: { margin: theme.spacing(2, 0) },
}))

export type Props = {
  className?: string
  fileID: number
  variant: "unified" | "side-by-side"
  integrated: boolean
  mountOnExpand: boolean
  comments: readonly ChunkComments[] | null
  rfcs: ReadonlySet<ReviewableFileChange> | null
  PaperProps?: PaperProps
}

const ChangesetFile: FunctionComponent<Props> = ({
  className,
  fileID,
  variant,
  integrated,
  mountOnExpand,
  comments,
  rfcs,
  PaperProps = {},
}) => {
  const classes = useStyles()
  const history = useHistory()
  const location = useLocation()
  const { changeset, expandedFileIDs } = useChangeset()
  const files = useResource("files")
  const fileChanges = useResource("filechanges")
  const fileDiffs = useResource("filediffs")
  const file = files.byID.get(fileID)
  const fileChange = fileChanges.get(`${changeset.id}:${fileID}`)
  const fileDiff = fileDiffs.get(`${changeset.id}:${fileID}`)
  if (!file) return null
  const isExpanded = expandedFileIDs.has(fileID)
  const canCollapse = changeset.files?.length !== 1
  const expandFile = () =>
    history.replace(
      pathWithExpandedFiles(location, setWith(expandedFileIDs, fileID)),
    )
  const collapseFile = () =>
    history.replace(
      pathWithExpandedFiles(location, setWithout(expandedFileIDs, fileID)),
    )
  const commonProps = {
    file,
    fileChange,
    fileDiff,
    isExpanded,
    canCollapse,
    expandFile,
    collapseFile,
  }
  return (
    <Paper
      className={clsx(className, classes.root, {
        [classes.collapsed]: !integrated && !isExpanded,
        [classes.expanded]: !integrated && isExpanded,
      })}
      elevation={integrated ? 0 : undefined}
      {...PaperProps}
    >
      <ChangesetFileHeader {...commonProps} rfcs={rfcs} />
      <Collapse in={isExpanded}>
        <ChangesetFileChanges
          {...commonProps}
          comments={comments}
          variant={
            fileChange?.wasDeleted || fileChange?.wasAdded ? "unified" : variant
          }
          mountOnExpand={mountOnExpand}
        />
        <ChangesetFileFooter {...commonProps} />
      </Collapse>
    </Paper>
  )
}

// Note: The `as FunctionComponent<OwnProps>` at the end is a hack; type
// inference failed here due to the combination of compose() and withRouter()
// such that the end result wasn't a callable type.
export default Registry.add("Changeset.File", ChangesetFile)
