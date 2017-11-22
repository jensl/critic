import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import ArrowRightAltIcon from "@material-ui/icons/ArrowRightAlt"
import Registry from "."

const useStyles = makeStyles((theme) => ({
  suggestionsReason: {
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    marginTop: theme.spacing(1),
  },
  arrow: {
    marginRight: theme.spacing(2),
  },
}))

type OwnProps = {
  className?: string
}

const SuggestionsReason: FunctionComponent<OwnProps> = ({
  className,
  children,
}) => {
  const classes = useStyles()
  return (
    <div className={clsx(className, classes.suggestionsReason)}>
      <ArrowRightAltIcon className={classes.arrow} />
      {children}
    </div>
  )
}

export default Registry.add("Suggestions.Reason", SuggestionsReason)
