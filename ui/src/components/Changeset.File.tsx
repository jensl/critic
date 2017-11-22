import React, { FunctionComponent } from "react"
import { useHistory, useLocation } from "react-router"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import ChangesetFileHeader from "./Changeset.File.Header"
import ChangesetFileChanges from "./Changeset.File.Changes"
import ChangesetFileFooter from "./Changeset.File.Footer"
import { setWith, setWithout, useChangeset, useResource } from "../utils"
import { pathWithExpandedFiles } from "../utils/Changeset"

const useStyles = makeStyles((theme: Theme) => ({
  root: {
    ...theme.critic.diff.background,
  },
  expanded: {
    margin: `${theme.spacing(1)}px 0`,
  },
}))

type Props = {
  className?: string
  fileID: number
  variant?: "unified" | "side-by-side"
}

const ChangesetFile: FunctionComponent<Props> = ({
  className,
  fileID,
  variant,
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
  if (!file || !fileChange || !fileDiff) return null
  const isExpanded = expandedFileIDs.has(fileID)
  const expandFile = () =>
    history.replace(
      pathWithExpandedFiles(location, setWith(expandedFileIDs, fileID))
    )
  const collapseFile = () =>
    history.replace(
      pathWithExpandedFiles(location, setWithout(expandedFileIDs, fileID))
    )
  const commonProps = {
    file,
    fileChange,
    fileDiff,
    isExpanded,
    expandFile,
    collapseFile,
  }
  return (
    <div
      className={clsx(className, classes.root, {
        [classes.expanded]: isExpanded,
      })}
    >
      <ChangesetFileHeader {...commonProps} />
      {isExpanded && (
        <>
          <ChangesetFileChanges {...commonProps} variant={variant} />
          <ChangesetFileFooter {...commonProps} />
        </>
      )}
    </div>
  )
}

// Note: The `as FunctionComponent<OwnProps>` at the end is a hack; type
// inference failed here due to the combination of compose() and withRouter()
// such that the end result wasn't a callable type.
export default Registry.add("Changeset.File", ChangesetFile)
