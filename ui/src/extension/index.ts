import React, { useEffect } from "react"

import { useDispatch } from "../store"
import { ADD_COMPONENT_TO_LIST, UIAddon } from "../actions"

const EmailSettings = () => {
  return null
}

const Extension: React.FunctionComponent<{ uiAddon: UIAddon }> = ({
  uiAddon,
}) => {
  console.log("extension rendered")

  const dispatch = useDispatch()

  useEffect(() => {
    dispatch({
      type: ADD_COMPONENT_TO_LIST,
      componentList: "ACCOUNT_SETTINGS_PANE",
      component: EmailSettings,
      uiAddon,
    })
  }, [uiAddon])

  return null
}

export default Extension
