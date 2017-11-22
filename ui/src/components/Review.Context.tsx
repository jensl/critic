import React, { FunctionComponent } from "react"
import { Switch, Route, useParams } from "react-router-dom"

import DeleteReviewDialog from "./Dialog.Review.Delete"
import DropReviewDialog from "./Dialog.Review.Drop"
import Review from "./Review"
import ReviewCommit from "./Review.Commit"
import ReviewDiff from "./Review.Diff"
import LoaderBlock from "./Loader.Block"
import Breadcrumb from "./Breadcrumb"

import { loadReview } from "../actions/review"
import { SetReview } from "../utils/ReviewContext"
import { useSubscription } from "../utils"
import { useSelector } from "../store"

type Params = {
  reviewID: string
}

const ReviewContext: FunctionComponent = () => {
  const reviews = useSelector((state) => state.resource.reviews)
  const reviewID = parseInt(useParams<Params>().reviewID)
  useSubscription(loadReview, reviewID)
  const review = reviews.get(reviewID)
  if (!review || review.isPartial) return <LoaderBlock />
  const prefix = `/review/${review.id}`
  return (
    <SetReview review={review}>
      <Breadcrumb category="review" label={String(review.id)} path={prefix}>
        <Switch>
          <Route path={`${prefix}/commit/:ref`} component={ReviewCommit} />
          <Route
            path={`${prefix}/diff/:from([0-9a-f]{4,40}\\^*)..:to([0-9a-f]{4,40})`}
            component={ReviewDiff}
          />
          <Route component={Review} />
        </Switch>
        <DeleteReviewDialog />
        <DropReviewDialog />
      </Breadcrumb>
    </SetReview>
  )
}

export default ReviewContext
