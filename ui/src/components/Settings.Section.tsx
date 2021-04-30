import React from "react"
import { useRouteMatch, useHistory } from "react-router"

import Accordion, { AccordionProps } from "@material-ui/core/Accordion"
import AccordionSummary from "@material-ui/core/AccordionSummary"
import AccordionDetails from "@material-ui/core/AccordionDetails"
import Container, { ContainerProps } from "@material-ui/core/Container"
import ExpandMoreIcon from "@material-ui/icons/ExpandMore"
import Typography from "@material-ui/core/Typography"
import { makeStyles } from "@material-ui/core/styles"

import Registry from "."
import { useOptionalExtension } from "../utils/ExtensionContext"
import { usePrefix } from "../utils"

const useStyles = makeStyles((theme) => ({
  heading: {
    fontSize: theme.typography.pxToRem(15),
    fontWeight: theme.typography.fontWeightMedium,
    display: "flex",
    flexGrow: 1,
  },
  details: {
    flexFlow: "column",
  },
  title: { flexGrow: 1 },

  extensionAnnotation: {
    flexGrow: 0,
    opacity: 0.7,

    "&::before": { content: "'[extension: '" },
    "&::after": { content: "']'" },
  },
}))

const ExtensionAnnotation: React.FunctionComponent<{}> = () => {
  const classes = useStyles()
  const extension = useOptionalExtension()
  return extension ? (
    <Typography variant="body2" className={classes.extensionAnnotation}>
      {extension.name}
    </Typography>
  ) : null
}

type Params = {
  section?: string
}

export type SectionProps = {
  className?: string
  id: string
  title: string
  ContainerProps?: Omit<ContainerProps, "children">
  AccordionProps?: Omit<
    AccordionProps,
    "children" | "className" | "expanded" | "onChange" | "TransitionProps"
  >
}

const Section: React.FunctionComponent<SectionProps> = ({
  className,
  id,
  title,
  children,
  AccordionProps = {},
  ContainerProps = { maxWidth: "md" },
}) => {
  const classes = useStyles()
  const match = useRouteMatch<Params>()
  const history = useHistory()
  const { section } = match.params
  const prefix = usePrefix()
  return (
    <Accordion
      className={className}
      expanded={id === section}
      onChange={(_, isExpanded) =>
        history.replace(`${prefix}/${isExpanded ? id : ""}`)
      }
      TransitionProps={{ mountOnEnter: true, unmountOnExit: true }}
      {...AccordionProps}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography className={classes.heading}>
          <span className={classes.title}>{title}</span>
        </Typography>
        <ExtensionAnnotation />
      </AccordionSummary>
      <AccordionDetails className={classes.details}>
        <Container {...ContainerProps}>
          <>{children}</>
        </Container>
      </AccordionDetails>
    </Accordion>
  )
}

export default Registry.add("Settings.Section", Section)
