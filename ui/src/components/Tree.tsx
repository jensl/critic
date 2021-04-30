import React from "react"
import loadable from "@loadable/component"

import Registry from "."
import { CommitID } from "../resources/types"

type Props = {
  className?: string
  commitID?: CommitID
  path?: string
}

const Tree = loadable(
  () => import("./Tree.lazy"),
) as React.FunctionComponent<Props>

export default Registry.add("Tree", Tree)
