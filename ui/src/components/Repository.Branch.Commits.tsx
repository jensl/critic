import React from "react"

import Registry from "."
import BranchCommits from "./Branch.Commits"
import { useBranch, useRepository } from "../utils"
import SetPrefix from "../utils/PrefixContext"

type Props = {
  className?: string
}

const RepositoryBranchCommits: React.FunctionComponent<Props> = ({
  className,
}) => {
  const branch = useBranch()
  if (!branch) return null
  return <BranchCommits className={className} branch={branch} />
}

export default Registry.add(
  "Repository.Branch.Commits",
  RepositoryBranchCommits,
)
