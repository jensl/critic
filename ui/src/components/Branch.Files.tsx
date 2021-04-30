import React from "react"

import Registry from "."
import Tree from "./Tree"
import { useBranch } from "../utils"

const BranchFiles: React.FunctionComponent = () => (
  <Tree commitID={useBranch().head} />
)

export default Registry.add("Branch.Files", BranchFiles)
