import React from "react"

import Registry from "."
import { ReviewActionProps } from "./Review.Action"
import PublishChanges from "./Review.Action.PublishChanges"
import DiscardChanges from "./Review.Action.DiscardChanges"
import PublishReview from "./Review.Action.PublishReview"
import DeleteReview from "./Review.Action.DeleteReview"
import CreateBranch from "./Review.Action.CreateBranch"
import Integrate from "./Review.Action.Integrate"
import CloseReview from "./Review.Action.CloseReview"
import ReopenReview from "./Review.Action.ReopenReview"

type Props = {
  getProps: (key: string) => ReviewActionProps
}

const ReviewActions: React.FunctionComponent<Props> = ({ getProps }) => (
  <>
    <PublishReview {...getProps("publishReview")} />
    <PublishChanges {...getProps("publishChanges")} />
    <DiscardChanges {...getProps("discardChanges")} />
    <CreateBranch {...getProps("createBranch")} />
    <DeleteReview {...getProps("deleteReview")} />
    <Integrate {...getProps("integrate")} />
    <CloseReview {...getProps("closeReview")} />
    <ReopenReview {...getProps("reopenReview")} />
  </>
)

export default Registry.add("Review.Actions", ReviewActions)
