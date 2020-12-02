import React, { FunctionComponent } from "react"

import Registry from "."
import Reference from "./Reference"
import { useResource } from "../utils"
import { BranchID } from "../resources/types"

type Props = {
  className?: string
  branchID: BranchID
  link?: boolean
}

const BranchName: FunctionComponent<Props> = ({
  className,
  branchID,
  link = false,
}) => {
  const branch = useResource("branches", ({ byID }) => byID.get(branchID))
  const repository = useResource("repositories", ({ byID }) =>
    byID.get(branch?.repository ?? -1),
  )
  if (!branch) return null
  return (
    <Reference
      className={className}
      linkTo={
        link && repository
          ? `/repository/${repository.name}/branch/${branch.name}`
          : undefined
      }
    >
      {branch.name}
    </Reference>
  )
}

export default Registry.add("Branch.Name", BranchName)
