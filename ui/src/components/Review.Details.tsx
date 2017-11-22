import React, { FunctionComponent } from "react"

import Registry from "."
import Author from "./Review.Details.Author"
import Branch from "./Review.Details.Branch"
import State from "./Review.Details.State"
import Reviewers from "./Review.Details.Reviewers"

const ReviewDetails: FunctionComponent = () => (
  <>
    <State />
    <Branch />
    <Author />
    <Reviewers />
  </>
)

export default Registry.add("Review.Details", ReviewDetails)
