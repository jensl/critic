import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import Panel from "./Suggestions.Panel"
import { loadSystemSetting } from "../actions/system"
import { useSubscription, useResource } from "../utils"

const useStyles = makeStyles((theme) => ({
  suggestionsAccountSetup: {},
}))

type Props = {
  className?: string
}

const SuggestionsAccountSetup: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const systemSettings = useResource("systemsettings")
  useSubscription(loadSystemSetting, {
    systemSettingID: "authentication.enable_ssh_access",
  })
  const reasons = ["Review your personal details and email address"]
  const enableSSHAccess = systemSettings.get(
    "authentication.enable_ssh_access",
    null
  )
  if (enableSSHAccess)
    reasons.push("Add one or more SSH keys to access Git repositories")
  reasons.push(
    "Add filters to be notified about changes in code you're interested in"
  )
  return (
    <Panel
      className={clsx(className, classes.suggestionsAccountSetup)}
      panelID="accountSetup"
      heading="Account setup"
      subheading=""
      reasons={reasons}
      actions={{ "Account settings": "/settings/account" }}
    />
  )
}

export default Registry.add("Suggestions.AccountSetup", SuggestionsAccountSetup)
