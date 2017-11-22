import React from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Switch from "@material-ui/core/Switch"
import Typography from "@material-ui/core/Typography"

import Registry from "."
import Panel from "./Suggestions.Panel"
import userSettings from "../userSettings"
import { useUserSetting } from "../utils"

const useStyles = makeStyles((theme) => ({
  suggestionsAppearance: {},
  themeSwitch: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    width: "100%",
  },
  subtitle: { display: "block", marginRight: theme.spacing(2) },
  body: { display: "block" },
}))

type Props = {
  className?: string
}

const SuggestionsAppearance: React.FunctionComponent<Props> = ({
  className,
}) => {
  const classes = useStyles()
  const [selectedTheme, setSelectedTheme] = useUserSetting(userSettings.theme)
  const updateTheme = (value: boolean) =>
    setSelectedTheme(value ? "dark" : "light")
  return (
    <Panel
      className={clsx(className, classes.suggestionsAppearance)}
      panelID="appearance"
      heading="Appearance"
      subheading="Theme and more"
      actions={{ "UI settings": "/settings/ui" }}
    >
      <div className={classes.themeSwitch}>
        <Typography className={classes.subtitle} variant="subtitle2">
          Theme:
        </Typography>
        <Typography className={classes.body} variant="body1">
          Light{" "}
          <Switch
            checked={selectedTheme === "dark"}
            onChange={(_, value) => updateTheme(value)}
          />{" "}
          Dark
        </Typography>
      </div>
    </Panel>
  )
}

export default Registry.add("Suggestions.Appearance", SuggestionsAppearance)
