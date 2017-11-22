import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Commit from "../resources/commit"

const useStyles = makeStyles((theme) => ({
  changesetCommitMessage: {
    whiteSpace: "pre",
    backgroundColor: theme.palette.secondary.light,
    borderRadius: 3,
    padding: `${theme.spacing(0.5)}px ${theme.spacing(2)}px`,

    ...theme.critic.monospaceFont,

    "&:first-line": {
      fontWeight: 500,
    },
  },
}))

type Props = {
  className?: string
  commit: Commit
}

const ChangesetCommitMessage: FunctionComponent<Props> = ({
  className,
  commit,
}) => {
  const classes = useStyles()
  return (
    <div className={clsx(className, classes.changesetCommitMessage)}>
      {commit.message}
    </div>
  )
}

export default Registry.add("Changeset.Commit.Message", ChangesetCommitMessage)
