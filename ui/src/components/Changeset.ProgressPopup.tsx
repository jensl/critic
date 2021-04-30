import React, { useEffect, useState } from "react"

import Chip from "@material-ui/core/Chip"
import Dialog from "@material-ui/core/Dialog"
import DialogTitle from "@material-ui/core/DialogTitle"
import DialogContent from "@material-ui/core/DialogContent"
import LinearProgress from "@material-ui/core/LinearProgress"
import Typography from "@material-ui/core/Typography"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { useChangeset } from "../utils"
import { useChangesetState } from "../utils/Changeset"

const useStyles = makeStyles((theme) => ({
  levels: {},
  header: {
    fontWeight: "bold",
  },
  progress: {},
  completionLevel: { marginLeft: theme.spacing(1) },
  linearProgress: {
    width: "100%",
    marginBottom: theme.spacing(3),
  },
  linearProgressLabel: {
    marginTop: theme.spacing(2),
  },
}))

const CompletionLevel: React.FunctionComponent<{
  className: string
  label: string
}> = ({ className, label }) => (
  <Chip className={className} label={label} size="small" color="secondary" />
)

const ProgressPopup = () => {
  const classes = useStyles()
  const { changeset } = useChangeset()
  const state = useChangesetState(changeset)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    if (state?.completionLevel.has("full")) {
      const timeoutID = window.setTimeout(() => setDismissed(true), 1500)
      return () => window.clearTimeout(timeoutID)
    }
  }, [state?.completionLevel])

  if (!state || dismissed) return null

  const { completionLevel, progress } = state

  return (
    <Dialog open onClose={() => setDismissed(true)} maxWidth="sm" fullWidth>
      <DialogTitle>Preparing diff...</DialogTitle>
      <DialogContent>
        <div className={classes.levels}>
          <span className={classes.header}>Levels:</span>
          {completionLevel.has("structure") && (
            <CompletionLevel
              className={classes.completionLevel}
              label="Structure"
            />
          )}
          {completionLevel.has("changedlines") && (
            <CompletionLevel
              className={classes.completionLevel}
              label="Changed lines"
            />
          )}
          {completionLevel.has("analysis") && (
            <CompletionLevel
              className={classes.completionLevel}
              label="Analysis"
            />
          )}
          {completionLevel.has("syntaxhighlight") && (
            <CompletionLevel
              className={classes.completionLevel}
              label="Syntax highlight"
            />
          )}
        </div>
        <div className={classes.progress}>
          <Typography
            className={classes.linearProgressLabel}
            variant="subtitle1"
          >
            Analysis progress
          </Typography>
          <LinearProgress
            className={classes.linearProgress}
            variant="determinate"
            value={(progress?.analysis ?? 0) * 100}
          />
          <Typography
            className={classes.linearProgressLabel}
            variant="subtitle1"
          >
            Syntax highlight progress
          </Typography>
          <LinearProgress
            className={classes.linearProgress}
            variant="determinate"
            value={(progress?.syntaxHighlight ?? 0) * 100}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default Registry.add("Changeset.ProgressPopup", ProgressPopup)
