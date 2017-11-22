import React, { useEffect, useState, FunctionComponent } from "react"

import { useTheme } from "@material-ui/core/styles"
import MUITabs, { TabsActions } from "@material-ui/core/Tabs"

import userSettings from "../userSettings"
import { useUserSetting } from "../utils"

const Tabs: FunctionComponent<any> = (props) => {
  const theme = useTheme()
  const [actions, setActions] = useState<TabsActions | null>(null)
  const [sidebarVisible] = useUserSetting(userSettings.sidebar.isVisible)
  const duration = sidebarVisible
    ? theme.transitions.duration.enteringScreen
    : theme.transitions.duration.leavingScreen
  useEffect(() => {
    if (actions !== null) {
      setTimeout(() => actions.updateIndicator(), duration)
    }
  }, [duration, actions, sidebarVisible])
  return <MUITabs {...props} action={setActions} />
}

export default Tabs
