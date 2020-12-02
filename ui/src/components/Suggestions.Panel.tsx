import React, { useLayoutEffect, FunctionComponent } from "react"
import { Link } from "react-router-dom"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import Typography from "@material-ui/core/Typography"
import Accordion from "@material-ui/core/Accordion"
import AccordionSummary from "@material-ui/core/AccordionSummary"
import AccordionDetails from "@material-ui/core/AccordionDetails"
import AccordionActions from "@material-ui/core/AccordionActions"
import Container from "@material-ui/core/Container"
import ExpandMoreIcon from "@material-ui/icons/ExpandMore"
import Button from "@material-ui/core/Button"
import Divider from "@material-ui/core/Divider"

import Registry from "."
import Reason from "./Suggestions.Reason"
import { Value, UserSetting, all, useValue, useUserSetting } from "../utils"
import { setWith, setWithout } from "../utils"
import { JSONData } from "../types"

const useStyles = makeStyles((theme) => ({
  suggestionsPanel: {},
  heading: {
    fontSize: theme.typography.pxToRem(15),
    fontWeight: theme.typography.fontWeightMedium,
    flexBasis: "33.33%",
    flexShrink: 0,
  },
  secondaryHeading: {
    fontSize: theme.typography.pxToRem(15),
    color: theme.palette.text.secondary,
  },

  details: {
    display: "block",
  },
}))

const DismissedPanels = new UserSetting<ReadonlySet<string>>(
  "suggestionPanels.dismissed",
  new Set(),
  {
    fromJSON: (value: JSONData) => {
      if (
        Array.isArray(value) &&
        all(value, (item) => typeof item === "string")
      )
        return new Set(value as string[])
      return new Set()
    },
    toJSON: (value: ReadonlySet<string>) => [...value],
  },
)
const ShowDismissed = new Value("suggestionPanels.showDismissed", false)

const FirstPanel = new Value<string | null>(
  "suggestionsPanels.firstPanel",
  null,
)
const ExpandedPanel = new Value<string | null | undefined>(
  "suggestionPanels.expandedPanel",
  undefined,
)

type OwnProps = {
  className?: string
  panelID: string
  heading: string
  subheading: string
  reasons?: (JSX.Element | string)[]
  actions?: { [key: string]: string }
  dismissable?: boolean
}

const SuggestionsPanel: FunctionComponent<OwnProps> = ({
  className,
  panelID,
  heading,
  subheading,
  reasons = [],
  actions = {},
  dismissable = true,
  children,
}) => {
  const classes = useStyles()
  const [showDismissed] = useValue(ShowDismissed)
  const [firstPanel, setFirstPanel] = useValue(FirstPanel)
  const [dismissedPanels, setDismissedPanels] = useUserSetting(DismissedPanels)
  useLayoutEffect(() => {
    if (
      firstPanel === panelID ||
      (!showDismissed && dismissedPanels.has(panelID))
    )
      return
    const firstPanelEl = document.querySelector<HTMLElement>(
      ".critic-suggestions-panel",
    )
    if (firstPanelEl && firstPanelEl.dataset.panelId === panelID)
      setFirstPanel(panelID)
  }, [panelID, firstPanel, setFirstPanel, dismissedPanels, showDismissed])
  const [expandedPanel, setExpandedPanel] = useValue(ExpandedPanel)
  const expanded =
    (expandedPanel === undefined ? firstPanel : expandedPanel) === panelID
  var dismissAction = null
  if (dismissable) {
    if (dismissedPanels.has(panelID)) {
      if (!showDismissed) return null
      const undismissPanel = () =>
        setDismissedPanels(setWithout(dismissedPanels, panelID))
      dismissAction = (
        <Button variant="contained" onClick={undismissPanel}>
          Undismiss
        </Button>
      )
    } else {
      const dismissPanel = () => {
        setDismissedPanels(setWith(dismissedPanels, panelID))
        if (firstPanel === panelID) setFirstPanel(null)
        setExpandedPanel(null)
      }
      dismissAction = (
        <Button color="secondary" variant="contained" onClick={dismissPanel}>
          Dismiss
        </Button>
      )
    }
  }
  return (
    <Accordion
      className={clsx(
        className,
        classes.suggestionsPanel,
        "critic-suggestions-panel",
      )}
      data-panel-id={panelID}
      expanded={expanded}
      onChange={(_, isExpanded) =>
        setExpandedPanel(isExpanded ? panelID : null)
      }
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography className={classes.heading}>{heading}</Typography>
        <Typography className={classes.secondaryHeading}>
          {subheading}
        </Typography>
      </AccordionSummary>
      <Divider variant="middle" />
      <AccordionDetails className={classes.details}>
        <Container maxWidth="md">
          {children}
          {reasons.map((reason, index) => {
            if (typeof reason === "string")
              reason = <Typography variant="body1">{reason}</Typography>
            return <Reason key={index}>{reason}</Reason>
          })}
        </Container>
      </AccordionDetails>
      <AccordionActions>
        {Object.keys(actions).map((label) => (
          <Button key="label" component={Link} to={actions[label]}>
            {label}
          </Button>
        ))}
        {dismissAction}
      </AccordionActions>
    </Accordion>
  )
}

export default Registry.add("Suggestions.Panel", SuggestionsPanel)
