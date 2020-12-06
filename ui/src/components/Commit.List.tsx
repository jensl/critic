import React, { FunctionComponent } from "react"

import Registry from "."
import SelectionScope from "./Selection.Scope"
import CommitListItem from "./Commit.ListItem"
import Popup from "./Commit.List.Popup"
import { CommitID } from "../resources/types"
import { useSelector } from "../store"

type Props = {
  className?: string
  pathPrefix: string
  scopeID: string
  withProgress?: boolean
  commitIDs: readonly CommitID[]
}

const CommitList: FunctionComponent<Props> = ({
  className,
  pathPrefix,
  scopeID,
  commitIDs,
  withProgress = false,
}) => {
  const selectionScope = useSelector((state) => state.ui.selectionScope)
  const thisSelectionScope =
    selectionScope.scopeID === scopeID ? selectionScope : null
  return (
    <>
      <SelectionScope
        className={className}
        scopeID={scopeID}
        elementToID={(element) =>
          String(parseInt(element.dataset.commitId!, 10))
        }
      >
        {commitIDs.map((commitID) => (
          <CommitListItem
            key={commitID}
            commitID={commitID}
            withProgress={withProgress}
            selectionScope={thisSelectionScope}
          />
        ))}
      </SelectionScope>
      <Popup pathPrefix={pathPrefix} selectionScope={thisSelectionScope} />
    </>
  )
}

export default Registry.add("Commit.List", CommitList)
