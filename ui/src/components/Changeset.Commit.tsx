import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, useTheme, Theme } from "@material-ui/core/styles"
import Paper from "@material-ui/core/Paper"
import Typography from "@material-ui/core/Typography"
import useMediaQuery from "@material-ui/core/useMediaQuery"

import Registry from "."
import Row from "./Changeset.Commit.Row"
import Message from "./Changeset.Commit.Message"
import Commit from "../resources/commit"

const useStyles = makeStyles((theme: Theme) => ({
  changesetCommit: {
    padding: `${theme.spacing(1)}px ${theme.spacing(2)}px`,
  },
  sha1: {
    ...theme.critic.monospaceFont,
  },
}))

type Props = {
  className?: string
  commit: Commit
}

const ChangesetCommit: FunctionComponent<Props> = ({ className, commit }) => {
  const classes = useStyles()
  const theme = useTheme()
  const trimSHA1 = useMediaQuery(theme.breakpoints.down("xs"))
  return (
    <Paper className={clsx(className, classes.changesetCommit)}>
      <Row heading="SHA-1">
        <Typography className={classes.sha1} noWrap>
          {commit.sha1.substring(0, trimSHA1 ? 10 : 40)}
        </Typography>
      </Row>
      <Row heading="Author">
        {commit.author.name} {`<${commit.author.email}>`}
      </Row>
      <Row heading="Message">
        <Message commit={commit} />
      </Row>
    </Paper>
  )
}

export default Registry.add("Changeset.Commit", ChangesetCommit)
