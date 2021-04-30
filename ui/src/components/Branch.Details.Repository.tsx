import React, { FunctionComponent } from "react"

import Registry from "."
import DetailsRow from "./Details.Row"
import { useBranch, useResource } from "../utils"

const Repository: FunctionComponent = () => {
  const branch = useBranch()
  const repository = useResource("repositories", ({ byID }) =>
    byID.get(branch?.repository ?? -1),
  )
  if (!repository) return null
  return <DetailsRow heading="Repository">{repository.path}</DetailsRow>
}

export default Registry.add("Branch.Details.Repository", Repository)
