import React from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"
import Switch from "@material-ui/core/Switch"
import FormControlLabel from "@material-ui/core/FormControlLabel"
import Container from "@material-ui/core/Container"

import Registry from "."
import Panels from "./Suggestions.Panels"
import { Value, useValue } from "../utils"

const ShowDismissed = new Value("suggestionPanels.showDismissed", false)

const useStyles = makeStyles((theme) => ({
  suggestions: {},
  header: {
    display: "flex",
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginBottom: theme.spacing(2),

    /*[theme.breakpoints.down("sm")]: {
      flexDirection: "column",
    },*/
  },
  title: {
    /*flexGrow: 1,*/
  },
  showDismissed: {
    /*flexGrow: 0,*/
    alignSelf: "flex-start",
    marginLeft: "auto",

    /*[theme.breakpoints.down("sm")]: {
      alignSelf: "flex-end",
    },*/
  },
}))

type Props = {
  className?: string
}

const Suggestions: React.FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const [showDismissed, setShowDismissed] = useValue(ShowDismissed)
  return (
    <Container maxWidth="lg" className={clsx(className, classes.suggestions)}>
      <div className={classes.header}>
        <Typography className={classes.title} variant="h4" gutterBottom>
          Your suggestions
        </Typography>
        <FormControlLabel
          className={classes.showDismissed}
          control={
            <Switch
              checked={showDismissed}
              onChange={(_, value) => setShowDismissed(value)}
            />
          }
          label="Show dismissed"
        />
      </div>
      <Panels />
    </Container>
  )
}

export default Registry.add("Suggestions", Suggestions)
