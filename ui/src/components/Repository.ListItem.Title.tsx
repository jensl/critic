import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Repository from "../resources/repository"

const useStyles = makeStyles({
  repositoryListItemTitle: {
    gridArea: "title",
  },
})

type OwnProps = {
  className?: string
  repository: Repository
}

const RepositoryListItemTitle: FunctionComponent<OwnProps> = ({
  className,
  repository,
}) => {
  const classes = useStyles()
  return (
    <Typography
      className={clsx(className, classes.repositoryListItemTitle)}
      variant="body1"
    >
      {repository.path}
    </Typography>
  )
}

export default Registry.add(
  "Repository.ListItem.Title",
  RepositoryListItemTitle
)
