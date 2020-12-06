import React from "react"

import Registry from "."
import PublishChanges from "./Review.Actions.PublishChanges"
import PublishReview from "./Review.Actions.PublishReview"
import Delete from "./Review.Actions.Delete"
import CreateBranch from "./Review.Actions.CreateBranch"
import Integrate from "./Review.Actions.Integrate"
import Close from "./Review.Actions.Close"
import Reopen from "./Review.Actions.Reopen"

const ReviewActionsPrimary = () => {
  return (
    <>
      <PublishReview />
      <PublishChanges />
      <CreateBranch />
      <Delete />
      <Integrate />
      <Close />
      <Reopen />
    </>
  )
}

export default Registry.add("Review.Actions.Primary", ReviewActionsPrimary)
