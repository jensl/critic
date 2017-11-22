import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"

import Registry from "."

const useStyles = makeStyles({
  changesetCommitRow: {
    display: "flex",
    flexDirection: "row",
    alignItems: "top",
    marginBottom: 10,
  },
  heading: {
    fontWeight: 500,
    maxWidth: "10em",
    flexGrow: 0,
    textAlign: "right",
    marginRight: "1rem",
  },
})

type Props = {
  className?: string
  heading: string
}

const ChangesetCommitRow: FunctionComponent<Props> = ({
  className,
  heading,
  children,
}) => {
  const classes = useStyles()
  return (
    <div className={clsx(className, classes.changesetCommitRow)}>
      <Typography className={classes.heading} variant="subtitle2">
        {heading}:
      </Typography>
      {children}
    </div>
  )
}

export default Registry.add("Changeset.Commit.Row", ChangesetCommitRow)
