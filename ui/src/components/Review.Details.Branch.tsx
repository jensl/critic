import React, { FunctionComponent } from "react"

import { makeStyles } from "@material-ui/core/styles"
import ArrowRightAltIcon from "@material-ui/icons/ArrowRightAlt"

import Registry from "."
import DetailsRow from "./Details.Row"
import BranchName from "./Branch.Name"
import { useReview } from "../utils/ReviewContext"

const useStyles = makeStyles({
  root: {},
  arrow: {
    margin: "0 0.5rem",
  },
})

type OwnProps = {
  className?: string
}

const ReviewDetailsBranch: FunctionComponent<OwnProps> = ({ className }) => {
  const classes = useStyles()
  const review = useReview()
  if (!review) return null
  const integrationTarget = review.integration ? (
    <>
      <ArrowRightAltIcon className={classes.arrow} />
      <BranchName branchID={review.integration.targetBranch} />
    </>
  ) : null
  return (
    <DetailsRow heading="Branch">
      {review.branch === null ? (
        <em>No branch created</em>
      ) : (
        <BranchName branchID={review.branch} />
      )}
      {integrationTarget}
    </DetailsRow>
  )
}

export default Registry.add("Review.Details.Branch", ReviewDetailsBranch)
