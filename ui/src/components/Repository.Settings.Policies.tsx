import React, { FunctionComponent } from "react"

import TextField from "@material-ui/core/TextField"

import Registry from "."
import Blurb from "./Blurb"
import VerticalMenuItem from "./VerticalMenu.Item"

const Policies: FunctionComponent = () => {
  return (
    <VerticalMenuItem id="policies" title="Roles &amp; policies">
      <Blurb>Roles and policies.</Blurb>
    </VerticalMenuItem>
  )
}

export default Registry.add("Repository.Settings.Policies", Policies)
