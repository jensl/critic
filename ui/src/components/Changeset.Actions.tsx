import React from "react"

import { ActionProps } from "./Changeset.Action"
import ExpandAll from "./Changeset.Action.ExpandAll"
import CollapseAll from "./Changeset.Action.CollapseAll"
import SideBySide from "./Changeset.Action.SideBySide"
import MarkAllAsReviewed from "./Changeset.Action.MarkAllAsReviewed"
import Registry from "."

const ChangesetActions: React.FunctionComponent<ActionProps> = (props) => (
  <>
    <ExpandAll {...props} />
    <CollapseAll {...props} />
    <SideBySide {...props} />
    <MarkAllAsReviewed {...props} />
  </>
)

export default Registry.add("Changeset.Actions", ChangesetActions)
