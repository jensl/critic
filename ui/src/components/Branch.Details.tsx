import React, { FunctionComponent } from "react"

import Registry from "."
import Repository from "./Branch.Details.Repository"

const BranchDetails: FunctionComponent = () => (
  <>
    <Repository />
  </>
)

export default Registry.add("Branch.Details", BranchDetails)
