import React, { FunctionComponent } from "react"
import { Redirect, useLocation } from "react-router"
import clsx from "clsx"

import Divider from "@material-ui/core/Divider"
import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import LoaderBlock from "./Loader.Block"
import ChangesetFile, { Props as ChangesetFileProps } from "./Changeset.File"
import {
  sortedBy,
  useChangeset,
  useResource,
  useOptionalReview,
} from "../utils"
import { pathWithExpandedFiles } from "../utils/Changeset"
import { useSelector } from "../store"
import { getCommentsForChangeset } from "../selectors/fileDiff"
import { getReviewableFileChangesForChangeset } from "../selectors/reviewableFileChange"
import { AutomaticMode } from "../actions"

const kMountOnExpandLimit = 25

const useStyles = makeStyles((theme: Theme) => ({
  ChangesetFiles: {
    margin: theme.spacing(1, 0),
  },

  divider: {
    margin: theme.spacing(1, 0),
  },
}))

export type Props = {
  className?: string
  variant: "unified" | "side-by-side"
  integrated: boolean
  automaticMode?: AutomaticMode
  ChangesetFileProps?: Partial<Omit<ChangesetFileProps, "fileID" | "variant">>
}

const ChangesetFiles: FunctionComponent<Props> = ({
  className,
  variant,
  integrated,
  automaticMode,
  ChangesetFileProps = {},
}) => {
  const classes = useStyles()
  const location = useLocation()
  const { changeset, expandedFileIDs } = useChangeset()
  const review = useOptionalReview()
  const fileByID = useResource("files", ({ byID }) => byID)
  const commentsForChangeset = useSelector((state) =>
    getCommentsForChangeset(state, { review, changeset }),
  )
  const rfcsByFile = useSelector((state) =>
    getReviewableFileChangesForChangeset(state, {
      review,
      changeset,
      automaticMode,
    }),
  )
  const { files: fileIDs } = changeset

  if (fileIDs === null) return <LoaderBlock />
  if (fileIDs.length === 1 && expandedFileIDs.size === 0)
    return <Redirect to={pathWithExpandedFiles(location, fileIDs)} />

  const sortedFileIDs = sortedBy(
    fileIDs,
    (fileID) => fileByID.get(fileID)?.path ?? "",
  )

  return (
    <div className={clsx(className, classes.ChangesetFiles)}>
      {sortedFileIDs.map((fileID, index) => (
        <React.Fragment key={fileID}>
          <ChangesetFile
            fileID={fileID}
            variant={variant}
            integrated={integrated}
            mountOnExpand={fileIDs.length > kMountOnExpandLimit}
            comments={commentsForChangeset.byFile.get(fileID)?.byChunk ?? null}
            rfcs={rfcsByFile?.get(fileID) ?? null}
            {...ChangesetFileProps}
          />
          {integrated &&
            index < fileIDs.length - 1 &&
            expandedFileIDs.has(fileID) &&
            expandedFileIDs.has(sortedFileIDs[index + 1]) && (
              <Divider className={classes.divider} variant="middle" />
            )}
        </React.Fragment>
      ))}
    </div>
  )
}

export default Registry.add("Changeset.Files", ChangesetFiles)
