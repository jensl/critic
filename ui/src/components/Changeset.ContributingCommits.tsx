import React, { FunctionComponent } from "react"
import clsx from "clsx"

import Accordion from "@material-ui/core/Accordion"
import AccordionSummary from "@material-ui/core/AccordionSummary"
import AccordionDetails from "@material-ui/core/AccordionDetails"
import Typography from "@material-ui/core/Typography"
import ExpandMoreIcon from "@material-ui/icons/ExpandMore"
import { makeStyles, Theme } from "@material-ui/core/styles"

import Registry from "."
import CommitList from "./Commit.List"
import { useChangeset } from "../utils"

const useStyles = makeStyles((theme: Theme) => ({
  changesetContributingCommits: {
    //padding: theme.spacing(1, 2),
  },
  heading: {
    marginLeft: theme.spacing(2),
  },
  divider: { margin: theme.spacing(1, 0) },
  commitList: {
    flexGrow: 1,
  },
}))

type Props = {
  className?: string
}

const ChangesetContributingCommits: FunctionComponent<Props> = ({
  className,
}) => {
  const classes = useStyles()
  const { changeset } = useChangeset()
  if (!changeset.contributingCommits) return null
  return (
    <Accordion
      className={clsx(className, classes.changesetContributingCommits)}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography className={classes.heading} variant="h6">
          Contributing commits
        </Typography>
      </AccordionSummary>
      <AccordionDetails>
        <CommitList
          className={classes.commitList}
          scopeID={`diff_${changeset.id}`}
          commitIDs={changeset.contributingCommits}
        />
      </AccordionDetails>
    </Accordion>
  )
}

export default Registry.add(
  "Changeset.ContributingCommits",
  ChangesetContributingCommits,
)
