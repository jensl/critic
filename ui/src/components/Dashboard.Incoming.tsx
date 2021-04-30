import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Breadcrumb from "./Breadcrumb"
import ReviewList from "./Review.List"
import SetPrefix from "../utils/PrefixContext"
import { loadReviewCategory } from "../actions/review"
import { useSubscription } from "../utils"
import { useSessionID } from "../utils/SessionContext"
import { useSelector } from "../store"

const useStyles = makeStyles((theme) => ({
  dashboardIncoming: {
    paddingTop: theme.spacing(1),
  },
}))

type Props = {
  className?: string
}

const DashboardIncoming: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const reviewIDs = useSelector((state) =>
    state.ui.rest.reviewCategories.get("incoming"),
  )
  useSubscription(loadReviewCategory, ["incoming", useSessionID()])
  if (!reviewIDs) return null
  const prefix = "/dashboard/incoming"
  return (
    <Breadcrumb category="dashboard" label="incoming" path={prefix}>
      <SetPrefix prefix={prefix}>
        <div className={clsx(className, classes.dashboardIncoming)}>
          <ReviewList reviewIDs={reviewIDs} />
        </div>
      </SetPrefix>
    </Breadcrumb>
  )
}

export default Registry.add("Dashboard.Incoming", DashboardIncoming)
