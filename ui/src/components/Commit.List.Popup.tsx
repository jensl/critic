import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Snackbar from "@material-ui/core/Snackbar"
import Typography from "@material-ui/core/Typography"
import Paper from "@material-ui/core/Paper"

import Registry from "."
import Actions from "./Commit.List.Actions"
import { useSelector } from "../store"
import { useResource } from "../utils"
import Commit from "../resources/commit"

const useStyles = makeStyles((theme) => ({
  commitListSelectionPopup: {},
  snackbarPaper: {
    padding: `${theme.spacing(1)}px ${theme.spacing(3)}px`,
    backgroundColor: theme.palette.secondary.main,
  },
  text: {
    textAlign: "center",
  },
  buttons: {
    textAlign: "center",
  },
}))

type Props = {
  className?: string
  scopeID: string
  pathPrefix: string
}

const CommitListSelectionPopup: FunctionComponent<Props> = ({
  className,
  scopeID,
  pathPrefix,
}) => {
  const classes = useStyles()
  const commits = useResource("commits")
  const selectionScope = useSelector((state) => state.ui.selectionScope)
  const { elementIDs, selectedIDs, isRangeSelecting } = selectionScope
  const hasSelectedCommits =
    selectionScope.scopeID === scopeID &&
    selectedIDs.size > 0 &&
    !isRangeSelecting
  if (!hasSelectedCommits) return null
  const selectedCommits = elementIDs
    .filter((elementID) => selectedIDs.has(elementID))
    .map((elementID) => commits.byID.get(parseInt(elementID, 10)))
    .filter((commit): commit is Commit => !!commit)

  return (
    <Snackbar
      open={hasSelectedCommits}
      onMouseDown={(ev) => ev.stopPropagation()}
    >
      <Paper className={clsx(className, classes.snackbarPaper)}>
        <Typography variant="body1" className={classes.text}>
          {selectedIDs.size} commits selected
        </Typography>
        <div className={classes.buttons}>
          <Actions selectedCommits={selectedCommits} pathPrefix={pathPrefix} />
        </div>
      </Paper>
    </Snackbar>
  )
}

export default Registry.add(
  "Commit.List.Selection.Popup",
  CommitListSelectionPopup
)
