import React, { FunctionComponent } from "react"

import Registry from "."
import ReviewTags from "./Review.Tags"
import ReviewTitle from "./Review.Title"
import ReviewProgress from "./Review.Progress"

const ReviewHeader: FunctionComponent = () => (
  <>
    <ReviewTags />
    <ReviewTitle />
    <ReviewProgress />
  </>
)

export default Registry.add("Review.Header", ReviewHeader)
