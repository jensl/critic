import React, { FunctionComponent } from "react"

import Registry from "."
import Author from "./Review.Details.Author"
import Branch from "./Review.Details.Branch"
import State from "./Review.Details.State"
import Reviewers from "./Review.Details.Reviewers"
import Actions from "./Review.Details.Actions"

const ReviewDetails: FunctionComponent = () => (
  <>
    <State />
    <Branch />
    <Author />
    <Reviewers />
    <Actions />
  </>
)

export default Registry.add("Review.Details", ReviewDetails)
