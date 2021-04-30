import React, { FunctionComponent } from "react"
import { Link as RouterLink } from "react-router-dom"

import Typography from "@material-ui/core/Typography"
import { styled } from "@material-ui/core/styles"

import Registry from "."
import Panel from "./Suggestions.Panel"
import { loadSystemSettingByKey } from "../actions/system"
import { useSubscription, useResource } from "../utils"

const Link = styled(RouterLink)(({ theme }) => ({
  color: "inherit",
  textDecoration: "none",

  "&:hover": {
    textDecoration: "underline",
  },
}))

type ReasonProps = {
  linkTo: string
}

const Reason: React.FunctionComponent<ReasonProps> = ({ linkTo, children }) => (
  <Link to={linkTo}>
    <Typography variant="body1">{children}</Typography>
  </Link>
)

type Props = {
  className?: string
}

const kEnableSSHAccess = "authentication.enable_ssh_access"

const SuggestionsAccountSetup: FunctionComponent<Props> = ({ className }) => {
  useSubscription(loadSystemSettingByKey, [kEnableSSHAccess])
  const systemSettings = useResource("systemsettings")
  const enableSSHAccess = systemSettings.byKey.get(kEnableSSHAccess)
  const reasons = [
    <Reason key="personal-details" linkTo="/settings/account/personal-details">
      Review your personal details and email address
    </Reason>,
  ]
  if (enableSSHAccess)
    reasons.push(
      <Reason key="ssh-keys" linkTo="/settings/account/ssh-keys">
        Add one or more SSH keys to access Git repositories
      </Reason>,
    )
  reasons.push(
    <Reason key="filters" linkTo="/settings/account/filters">
      Add filters to be notified about changes in code you're interested in
    </Reason>,
  )
  return (
    <Panel
      className={className}
      panelID="accountSetup"
      heading="Account setup"
      subheading=""
      reasons={reasons}
      actions={{ "Account settings": "/settings/account" }}
    />
  )
}

export default Registry.add("Suggestions.AccountSetup", SuggestionsAccountSetup)
