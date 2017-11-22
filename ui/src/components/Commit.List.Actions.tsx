import React, { FunctionComponent } from "react"

import Registry from "."
import ShowDiff from "./Commit.List.Actions.ShowDiff"
import CreateReview from "./Commit.List.Actions.CreateReview"
import { ActionProps } from "./Commit.List.Actions.types"

const CommitListActions: FunctionComponent<ActionProps> = (props) => (
  <>
    <ShowDiff {...props} />
    <CreateReview {...props} />
  </>
)

export default Registry.add("Commit.List.Actions", CommitListActions)
