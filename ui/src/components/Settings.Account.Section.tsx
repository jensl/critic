import React from "react"
import { useRouteMatch, useHistory } from "react-router"

import ExpansionPanel from "@material-ui/core/ExpansionPanel"
import ExpansionPanelSummary from "@material-ui/core/ExpansionPanelSummary"
import ExpansionPanelDetails from "@material-ui/core/ExpansionPanelDetails"
import ExpandMoreIcon from "@material-ui/icons/ExpandMore"
import Typography from "@material-ui/core/Typography"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."

const useStyles = makeStyles((theme) => ({
  heading: {
    fontSize: theme.typography.pxToRem(15),
    fontWeight: theme.typography.fontWeightMedium,
  },
  details: {
    flexFlow: "column",
  },
}))

type Params = {
  section?: string
}

type Props = {
  id: string
  title: string
}

const Section: React.FunctionComponent<Props> = ({ id, title, children }) => {
  const classes = useStyles()
  const match = useRouteMatch<Params>()
  const history = useHistory()
  const { section } = match.params
  console.log({ match })
  return (
    <ExpansionPanel
      expanded={id === section}
      onChange={(_, isExpanded) =>
        history.replace(`/settings/account/${isExpanded ? id : ""}`)
      }
    >
      <ExpansionPanelSummary expandIcon={<ExpandMoreIcon />}>
        <Typography className={classes.heading}>{title}</Typography>
      </ExpansionPanelSummary>
      <ExpansionPanelDetails className={classes.details}>
        {children}
      </ExpansionPanelDetails>
    </ExpansionPanel>
  )
}

export default Registry.add("Settings.Account.Section", Section)
