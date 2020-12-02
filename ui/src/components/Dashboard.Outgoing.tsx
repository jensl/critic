import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import ReviewList from "./Review.List"
import { loadReviewCategory } from "../actions/review"
import { useSubscription } from "../utils"
import { useSessionID } from "../utils/SessionContext"
import { useSelector } from "../store"

const useStyles = makeStyles((theme) => ({
  dashboardOutgoing: { paddingTop: theme.spacing(1) },
}))

type Props = {
  className?: string
}

const DashboardOutgoing: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const reviewIDs = useSelector((state) =>
    state.ui.rest.reviewCategories.get("outgoing", null),
  )
  useSubscription(loadReviewCategory, "outgoing", useSessionID())
  if (!reviewIDs) return null
  return (
    <div className={clsx(className, classes.dashboardOutgoing)}>
      <ReviewList reviewIDs={reviewIDs} />
    </div>
  )
}

export default Registry.add("Dashboard.Outgoing", DashboardOutgoing)
