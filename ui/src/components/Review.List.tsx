import React, { FunctionComponent } from "react"

import Registry from "."
import ReviewListItem from "./Review.ListItem"
import { ReviewID } from "../resources/types"
import { map } from "../utils"

type OwnProps = {
  reviewIDs: Iterable<ReviewID>
}

const ReviewList: FunctionComponent<OwnProps> = ({ reviewIDs }) => (
  <>
    {map(reviewIDs, (reviewID) => (
      <ReviewListItem key={reviewID} reviewID={reviewID} />
    ))}
  </>
)

export default Registry.add("Review.List", ReviewList)
