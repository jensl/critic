import React, { FunctionComponent } from "react"
import { Link, useHistory } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Button from "@material-ui/core/Button"

import Registry from "."
import { ActionProps } from "./Commit.List.Actions.types"
import { ShortcutScope } from "../utils/KeyboardShortcuts"
import { usePrefix } from "../utils"

const useStyles = makeStyles({
  commitListActionsShowDiff: {},
})

type OwnProps = {
  className?: string
}

const ShowDiff: FunctionComponent<ActionProps & OwnProps> = ({
  className,
  selectedCommits,
}) => {
  const classes = useStyles()
  const history = useHistory()
  const prefix = usePrefix()

  if (selectedCommits.length === 0) return null

  const lastCommit = () => selectedCommits[0]
  const firstCommit = () => selectedCommits[selectedCommits.length - 1]

  const diffPath =
    selectedCommits.length === 1
      ? `${prefix}/commit/${selectedCommits[0].sha1}`
      : `${prefix}/diff/${firstCommit().sha1}^..${lastCommit().sha1}`

  console.log({ diffPath })

  return (
    <ShortcutScope
      name="ShowDiff"
      handler={{ d: () => history.push(diffPath) }}
      component={Button}
      componentProps={{
        component: Link,
        to: diffPath,
        className: clsx(className, classes.commitListActionsShowDiff),
      }}
    >
      Show diff
    </ShortcutScope>
  )
}

export default Registry.add("Commit.List.Actions.Show.Diff", ShowDiff)
