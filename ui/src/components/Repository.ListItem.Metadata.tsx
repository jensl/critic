import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Repository from "../resources/repository"

const useStyles = makeStyles({
  repositoryListItemMetadata: {
    gridArea: "metadata",
    opacity: 0.5,
  },
})

type OwnProps = {
  className?: string
  repository: Repository
}

const RepositoryListItemMetadata: FunctionComponent<OwnProps> = ({
  className,
  repository,
}) => {
  const classes = useStyles()
  return (
    <Typography className={clsx(className, classes.repositoryListItemMetadata)}>
      {repository.statistics?.commits ?? "??"} commits
    </Typography>
  )
}

export default Registry.add(
  "Repository.ListItem.Metadata",
  RepositoryListItemMetadata,
)
