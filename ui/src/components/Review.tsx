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
import ReviewCommits from "./Review.Commits"
import ReviewChanges from "./Review.Changes"
import ReviewDiscussions from "./Review.Discussions"
import CreateBranchDialog from "./Dialog.Review.CreateBranch"
import PublishChangesDialog from "./Dialog.Review.PublishChanges"
import DiscardChangesDialog from "./Dialog.Review.DiscardChanges"
import PublishReviewDialog from "./Dialog.Review.PublishReview"
import { loadAutomaticChangeset } from "../actions/changeset"
import { usePrefix, useSubscription } from "../utils"

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
  const { activeTab, reviewID: reviewIDString } = useRouteMatch<Params>().params
  const reviewID = parseInt(reviewIDString, 10)
  useSubscription(loadAutomaticChangeset, ["everything", reviewID])
  useSubscription(loadAutomaticChangeset, ["pending", reviewID])
  const prefix = usePrefix()
  if (!activeTab) return <Redirect to={`${prefix}/commits`} />
  return (
    <>
      <Container className={clsx(className, classes.container)} maxWidth="lg">
        <ReviewHeader />
        <Paper className={classes.paper}>
          <div className={classes.details}>
            <ReviewDetails />
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
              to={`${prefix}/commits`}
              value="commits"
              label="Commits"
            />
            <Tab
              component={Link}
              to={`${prefix}/changes`}
              value="changes"
              label="Changes"
            />
            <Tab
              component={Link}
              to={`${prefix}/discussions`}
              value="discussions"
              label="Discussions"
            />
          </Tabs>
          <Switch>
            <Route path={`${prefix}/commits`} component={ReviewCommits} />
            <Route
              path={`${prefix}/changes/:mode?`}
              component={ReviewChanges}
            />
            <Route
              path={`${prefix}/discussions`}
              component={ReviewDiscussions}
            />
          </Switch>
        </Paper>
      </Container>
      <CreateBranchDialog />
      <DiscardChangesDialog />
      <PublishChangesDialog />
      <PublishReviewDialog />
    </>
  )
}

export default Registry.add("Review", Review)
