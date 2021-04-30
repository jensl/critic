import React, { FunctionComponent } from "react"

import Registry from "."
import BranchListItem from "./Branch.ListItem"
import { BranchID } from "../resources/types"
import { map } from "../utils"

type OwnProps = {
  branchIDs: Iterable<BranchID>
}

const BranchList: FunctionComponent<OwnProps> = ({ branchIDs }) => (
  <>
    {map(branchIDs, (branchID) => (
      <BranchListItem key={branchID} branchID={branchID} />
    ))}
  </>
)

export default Registry.add("Branch.List", BranchList)
