import React from "react"

import Button from "@material-ui/core/Button"

import Registry from "."
import { ActionProps } from "./Changeset.Action"
import { useChangeset } from "../utils"
import { useExpandedFiles } from "../actions/uiFileDiff"
import { ShortcutScope } from "../utils/KeyboardShortcuts"

const CollapseAll: React.FunctionComponent<ActionProps> = () => {
  const { changeset, expandedFileIDs } = useChangeset()
  const { collapseFiles } = useExpandedFiles()
  const { files } = changeset
  if (!files || files.length <= 1) return null
  const disabled = expandedFileIDs.size === 0
  const onClick = () => collapseFiles(files)
  return (
    <ShortcutScope
      name="ShowDiff"
      handler={{ c: onClick }}
      component={Button}
      componentProps={{
        disabled,
        onClick,
      }}
    >
      Collapse all
    </ShortcutScope>
  )
}

export default Registry.add("Changeset.Action.CollapseAll", CollapseAll)
