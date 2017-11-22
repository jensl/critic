import React, { FunctionComponent } from "react"

import Registry from "."
import Path from "./Repository.Details.Path"

const RepositoryDetails: FunctionComponent = () => (
  <>
    <Path />
  </>
)

export default Registry.add("Repository.Details", RepositoryDetails)
