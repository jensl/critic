import React from "react"
import { Switch, Route, Redirect, useRouteMatch } from "react-router"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Paper from "@material-ui/core/Paper"
import Tab from "@material-ui/core/Tab"
import Tabs from "@material-ui/core/Tabs"
import Divider from "@material-ui/core/Divider"
import Container from "@material-ui/core/Container"

import Registry from "."
import ReviewHeader from "./Review.Header"
import ReviewDetails from "./Review.Details"
import ReviewActions from "./Review.Actions"
import ReviewCommits from "./Review.Commits"
import ReviewChanges from "./Review.Changes"
import ReviewDiscussions from "./Review.Discussions"
import CreateBranchDialog from "./Dialog.Review.CreateBranch"
import PublishDialog from "./Dialog.Review.Publish"
import { loadAutomaticChangeset } from "../actions/changeset"
import { useSubscription } from "../utils"

const useStyles = makeStyles((theme) => ({
  container: {
    [theme.breakpoints.down("sm")]: {
      paddingLeft: theme.spacing(1),
      paddingRight: theme.spacing(1),
    },
  },

  paper: {
    marginTop: "1rem",
    paddingTop: theme.spacing(2),
    paddingBottom: theme.spacing(2),
    paddingLeft: theme.spacing(3),
    paddingRight: theme.spacing(3),

    [theme.breakpoints.down("sm")]: {
      paddingLeft: theme.spacing(1),
      paddingRight: theme.spacing(1),
    },
  },

  details: {},

  tabs: {
    marginBottom: theme.spacing(1),
  },

  actions: {},
}))

type Params = {
  activeTab: string
  reviewID: string
}

type Props = {
  className?: string
}

const Review: React.FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const { activeTab, reviewID } = useRouteMatch<Params>().params
  useSubscription(loadAutomaticChangeset, "everything", parseInt(reviewID, 10))
  if (!activeTab) return <Redirect to={`/review/${reviewID}/commits`} />
  return (
    <>
      <Container className={clsx(className, classes.container)} maxWidth="lg">
        <ReviewHeader />
        <Paper className={classes.paper}>
          <div className={classes.details}>
            <ReviewDetails />
          </div>
          <div className={classes.actions}>
            <ReviewActions />
          </div>
          <Divider />
          <Tabs
            className={classes.tabs}
            centered
            value={activeTab}
            indicatorColor="primary"
          >
            <Tab
              component={Link}
              to={`/review/${reviewID}/commits`}
              value="commits"
              label="Commits"
            />
            <Tab
              component={Link}
              to={`/review/${reviewID}/changes`}
              value="changes"
              label="Changes"
            />
            <Tab
              component={Link}
              to={`/review/${reviewID}/discussions`}
              value="discussions"
              label="Discussions"
            />
          </Tabs>
          <Switch>
            <Route path="/review/:reviewID/commits" component={ReviewCommits} />
            <Route path="/review/:reviewID/changes" component={ReviewChanges} />
            <Route
              path="/review/:reviewID/discussions"
              component={ReviewDiscussions}
            />
          </Switch>
        </Paper>
      </Container>
      <CreateBranchDialog />
      <PublishDialog />
    </>
  )
}

export default Registry.add("Review", Review)
