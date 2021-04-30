import React, { FunctionComponent } from "react"

import Registry from "."
import ExtensionListItem from "./Extension.ListItem"
import { ExtensionID } from "../resources/types"
import { map } from "../utils"

type OwnProps = {
  extensionIDs: Iterable<ExtensionID>
}

const ExtensionList: FunctionComponent<OwnProps> = ({ extensionIDs }) => (
  <>
    {map(extensionIDs, (extensionID) => (
      <ExtensionListItem key={extensionID} extensionID={extensionID} />
    ))}
  </>
)

export default Registry.add("Extension.List", ExtensionList)
