import React, { FunctionComponent } from "react"
import { Redirect, useLocation } from "react-router"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import LoaderBlock from "./Loader.Block"
import ChangesetFile from "./Changeset.File"
import { useChangeset } from "../utils"
import { pathWithExpandedFiles } from "../utils/Changeset"

const useStyles = makeStyles((theme: Theme) => ({
  ChangesetFiles: {
    margin: `${theme.spacing(1)}px 0`,
  },
}))

type Props = {
  className?: string
  variant?: "unified" | "side-by-side"
}

const ChangesetFiles: FunctionComponent<Props> = ({ className, variant }) => {
  const classes = useStyles()
  const location = useLocation()
  const { changeset, expandedFileIDs } = useChangeset()
  if (changeset.files === null) return <LoaderBlock />
  if (changeset.files.length === 1 && expandedFileIDs.size === 0)
    return <Redirect to={pathWithExpandedFiles(location, changeset.files)} />
  console.log({ changeset })
  return (
    <div className={clsx(className, classes.ChangesetFiles)}>
      {changeset.files.map((fileID) => (
        <ChangesetFile key={fileID} fileID={fileID} variant={variant} />
      ))}
    </div>
  )
}

export default Registry.add("Changeset.Files", ChangesetFiles)
