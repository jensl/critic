import React from "react"

import Registry from "."
import Section, { SectionProps } from "./Settings.Section"

const AccountSection: React.FunctionComponent<SectionProps> = (props) => (
  <Section {...props} />
)

export default Registry.add("Settings.Account.Section", AccountSection)
