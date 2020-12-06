import React, { FunctionComponent } from "react"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Button from "@material-ui/core/Button"

import Registry from "."
import { ActionProps } from "./Commit.List.Actions.types"

const useStyles = makeStyles({
  commitListActionsShowDiff: {},
})

type OwnProps = {
  className?: string
}

const ShowDiff: FunctionComponent<ActionProps & OwnProps> = ({
  className,
  pathPrefix,
  selectedCommits,
}) => {
  const classes = useStyles()
  var diffPath = pathPrefix

  if (selectedCommits.length === 0) return null
  else if (selectedCommits.length === 1)
    diffPath += `/commit/${selectedCommits[0].sha1}`
  else {
    const lastCommit = selectedCommits[0]
    const firstCommit = selectedCommits[selectedCommits.length - 1]
    diffPath += `/diff/${firstCommit.sha1}^..${lastCommit.sha1}`
  }

  return (
    <Button
      component={Link}
      to={diffPath}
      className={clsx(className, classes.commitListActionsShowDiff)}
    >
      Show diff
    </Button>
  )
}

export default Registry.add("Commit.List.Actions.Show.Diff", ShowDiff)
