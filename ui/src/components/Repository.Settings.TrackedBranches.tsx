import React, { FunctionComponent, useEffect, useState } from "react"

import Table from "@material-ui/core/Table"
import TableBody from "@material-ui/core/TableBody"
import TableCell from "@material-ui/core/TableCell"
import TableHead from "@material-ui/core/TableHead"
import TableRow from "@material-ui/core/TableRow"
import Typography from "@material-ui/core/Typography"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import AddTrackedBranch from "./Repository.Settings.TrackedBranches.Add"
import Blurb from "./Blurb"
import { sortedBy, useRepository, useSubscription } from "../utils"
import { loadTrackedBranches } from "../actions/trackedbranch"
import { useSelector } from "../store"
import { getTrackedBranchesForRepository } from "../selectors/trackedBranch"
import VerticalMenuItem from "./VerticalMenu.Item"
import timeSince from "../utils/TimeSince"

const CHECK_REPOSITORY_TIMEOUT_MS = 1000

import DESCRIPTION from "./Repository.Settings.TrackedBranches.description.md"

const useStyles = makeStyles((theme) => ({
  validUrlIcon: { color: theme.palette.success.main },

  blurb: {
    marginBottom: theme.spacing(2),
  },

  heading: {
    margin: theme.spacing(4, 2, 2, 2),
    borderBottom: `1px solid ${theme.palette.divider}`,
  },

  flex: {
    display: "flex",
    alignContent: "end",
  },
  monospaceInput: {
    "& input": theme.critic.monospaceFont,
  },

  remoteName: {
    flexGrow: 1,
    marginRight: theme.spacing(1),
  },
  localName: {
    flexGrow: 1,
    marginLeft: theme.spacing(1),
  },
  autocompleteContainer: {
    flexGrow: 1,
    display: "flex",
    flexDirection: "column",
    justifyContent: "flex-end",
    paddingBottom: theme.spacing(1),
  },
  slash: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "flex-end",
    padding: theme.spacing(1, 2),
    ...theme.critic.monospaceFont,
  },

  refsHeads: { "& p": theme.critic.monospaceFont },
  refOption: { display: "flex", width: "100%", ...theme.critic.monospaceFont },
  refName: { flexGrow: 1 },
  refValue: { flexGrow: 0 },

  localNameCell: {
    "& code": {
      ...theme.critic.monospaceFont,
      ...theme.critic.standout,
    },
  },
  sourceCell: {
    "& code": {
      ...theme.critic.monospaceFont,
      ...theme.critic.standout,
    },
  },
  lastUpdatedCell: { textAlign: "right" },

  center: {
    display: "flex",
    justifyContent: "space-around",
  },

  urlServer: {
    /*flexGrow: 1*/
  },
  urlPath: { flexGrow: 1 },
}))

const TrackedBranches: FunctionComponent = () => {
  const classes = useStyles()
  const repository = useRepository()

  useSubscription(loadTrackedBranches, [repository.id])

  const trackedBranches = useSelector((state) =>
    getTrackedBranchesForRepository(state, { repositoryID: repository.id }),
  )

  return (
    <VerticalMenuItem id="tracked-branches" title="Tracked branches">
      <Blurb className={classes.blurb} text={DESCRIPTION} />

      <Typography className={classes.heading} variant="h6">
        Add tracked branch
      </Typography>
      <AddTrackedBranch />

      {trackedBranches && (
        <>
          <Typography className={classes.heading} variant="h6">
            Current tracked branches
          </Typography>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Local name</TableCell>
                <TableCell>Source</TableCell>
                <TableCell className={classes.lastUpdatedCell}>
                  Last updated
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedBy(
                trackedBranches,
                (trackedBranch) => trackedBranch.name,
              ).map(({ id, name, source, lastUpdate }) => (
                <TableRow key={id}>
                  <TableCell className={classes.localNameCell}>
                    <code>{name}</code>
                  </TableCell>
                  <TableCell className={classes.sourceCell}>
                    <code>{source.name}</code>
                    {" in "}
                    <code>{source.url}</code>
                  </TableCell>
                  <TableCell className={classes.lastUpdatedCell}>
                    {lastUpdate ? `${timeSince(lastUpdate)} ago` : "N/A"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </VerticalMenuItem>
  )
}

export default Registry.add(
  "Repository.Settings.TrackedBranches",
  TrackedBranches,
)
