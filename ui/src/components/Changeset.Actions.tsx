import React from "react"

import { styled } from "@material-ui/core/styles"

import { ActionProps } from "./Changeset.Action"
import ExpandAll from "./Changeset.Action.ExpandAll"
import CollapseAll from "./Changeset.Action.CollapseAll"
import SideBySide from "./Changeset.Action.SideBySide"
import AutomaticModeToggle from "./Changeset.Action.AutomaticModeToggle"
import MarkAllAsReviewed from "./Changeset.Action.MarkAllAsReviewed"
import Registry from "."

const Actions = styled("div")({
  display: "grid",
  gridTemplateColumns: "1fr auto 1fr",
  gridTemplateAreas: `"left middle right"`,
})
const Left = styled("span")({ gridArea: "left" })
const Middle = styled("span")({ gridArea: "middle" })
const Right = styled("span")({ gridArea: "right", justifySelf: "end" })

const ChangesetActions: React.FunctionComponent<ActionProps> = (props) => {
  return (
    <Actions>
      <Left>
        <ExpandAll {...props} />
        <CollapseAll {...props} />
        <SideBySide {...props} />
      </Left>
      <Middle>
        <AutomaticModeToggle {...props} />
      </Middle>
      <Right>
        <MarkAllAsReviewed {...props} />
      </Right>
    </Actions>
  )
}

export default Registry.add("Changeset.Actions", ChangesetActions)
