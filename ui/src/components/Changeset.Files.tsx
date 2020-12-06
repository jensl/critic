import React, { FunctionComponent } from "react"
import { Redirect, useLocation } from "react-router"
import clsx from "clsx"

import Divider from "@material-ui/core/Divider"
import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import LoaderBlock from "./Loader.Block"
import ChangesetFile, { Props as ChangesetFileProps } from "./Changeset.File"
import { sortedBy, useChangeset, useResource, useReview } from "../utils"
import { pathWithExpandedFiles } from "../utils/Changeset"
import { useSelector } from "../store"
import { getCommentsForChangeset } from "../selectors/fileDiff"
import { getReviewableFileChangesForChangeset } from "../selectors/reviewableFileChange"

const useStyles = makeStyles((theme: Theme) => ({
  ChangesetFiles: {
    margin: `${theme.spacing(1)}px 0`,
  },
}))

export type Props = {
  className?: string
  variant: "unified" | "side-by-side"
  integrated: boolean
  ChangesetFileProps?: Partial<Omit<ChangesetFileProps, "fileID" | "variant">>
}

const ChangesetFiles: FunctionComponent<Props> = ({
  className,
  variant,
  integrated,
  ChangesetFileProps = {},
}) => {
  const classes = useStyles()
  const location = useLocation()
  const { changeset, expandedFileIDs } = useChangeset()
  const review = useReview()
  const fileByID = useResource("files", ({ byID }) => byID)
  const commentsForChangeset = useSelector((state) =>
    getCommentsForChangeset(state, { review, changeset }),
  )
  const rfcsByFile = useSelector((state) =>
    getReviewableFileChangesForChangeset(state, { review, changeset }),
  )
  const { files } = changeset
  if (files === null) return <LoaderBlock />
  if (files.length === 1 && expandedFileIDs.size === 0)
    return <Redirect to={pathWithExpandedFiles(location, files)} />
  return (
    <div className={clsx(className, classes.ChangesetFiles)}>
      {sortedBy(files, (fileID) => fileByID.get(fileID)?.path ?? "").map(
        (fileID, index) => (
          <React.Fragment key={fileID}>
            <ChangesetFile
              fileID={fileID}
              variant={variant}
              integrated={integrated}
              comments={
                commentsForChangeset.byFile.get(fileID)?.byChunk ?? null
              }
              rfcs={rfcsByFile?.get(fileID) ?? null}
              {...ChangesetFileProps}
            />
            {integrated &&
              index < files.length - 1 &&
              expandedFileIDs.has(fileID) &&
              expandedFileIDs.has(files[index + 1]) && (
                <Divider variant="middle" />
              )}
          </React.Fragment>
        ),
      )}
    </div>
  )
}

export default Registry.add("Changeset.Files", ChangesetFiles)
