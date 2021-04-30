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
import SetPrefix from "../utils/PrefixContext"
import SetRepository from "../utils/RepositoryContext"
import SetReview from "../utils/ReviewContext"
import { id, usePrefix, useResource, useSubscription } from "../utils"

type Params = {
  reviewID: string
}

const ReviewContext: FunctionComponent = () => {
  const reviewID = parseInt(useParams<Params>().reviewID)
  useSubscription(loadReview, [reviewID])
  const review = useResource("reviews", (byID) => byID.get(reviewID))
  const repository = useResource("repositories", ({ byID }) =>
    byID.get(review?.repository ?? -1),
  )
  const prefix = usePrefix()
  if (!review || review.isPartial || !repository) return <LoaderBlock />
  const reviewPrefix = `${prefix}/review/${review.id}`
  return (
    <SetPrefix prefix={`${reviewPrefix}`}>
      <SetRepository repository={repository}>
        <SetReview review={review}>
          <Breadcrumb
            category="review"
            label={String(review.id)}
            path={reviewPrefix}
          >
            <Switch>
              <Route
                path={`${reviewPrefix}/commit/:ref`}
                component={ReviewCommit}
              />
              <Route
                path={`${reviewPrefix}/diff/:from([0-9a-f]{4,40}\\^*)..:to([0-9a-f]{4,40})`}
                component={ReviewDiff}
              />
              <Route render={() => <Review />} />
            </Switch>
            <DeleteReviewDialog />
            <DropReviewDialog />
          </Breadcrumb>
        </SetReview>
      </SetRepository>
    </SetPrefix>
  )
}

export default ReviewContext
