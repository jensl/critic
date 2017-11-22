import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."

import { useRepository } from "../utils"

const useStyles = makeStyles({
  repositoryTitle: {},
})

type OwnProps = {
  className?: string
}

const RepositoryTitle: FunctionComponent<OwnProps> = () => {
  const classes = useStyles()
  const repository = useRepository()
  if (!repository) return null
  return (
    <Typography className={classes.repositoryTitle} variant="h4" gutterBottom>
      {repository.name}
    </Typography>
  )
}

export default Registry.add("Repository.Title", RepositoryTitle)
