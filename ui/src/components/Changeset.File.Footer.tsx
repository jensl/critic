import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, Theme } from "@material-ui/core/styles"
import ChevronRightIcon from "@material-ui/icons/ChevronRight"

import Registry from "."
import File from "../resources/file"
import FileChange from "../resources/filechange"

const useStyles = makeStyles((theme: Theme) => ({
  changesetFileFooter: {
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    padding: `2px ${theme.spacing(1)}px`,
    cursor: "pointer",
    ...theme.critic.monospaceFont,
  },

  chevronContainer: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    flexGrow: 0,
    paddingRight: "1rem",
  },
  chevron: {
    transform: "rotate(0deg)",
    transition: "transform 0.5s",
  },
  chevronExpanded: {
    transform: "rotate(-90deg)",
    transition: "transform 0.5s",
  },

  changedLines: {
    flexGrow: 0,
    minWidth: "6rem",
    padding: "0 1rem",
    textAlign: "right",
  },
  path: {
    fontWeight: 500,
    flexGrow: 1,
  },
}))

type Props = {
  className?: string
  file: File
  collapseFile: () => void
}

const ChangesetFileFooter: FunctionComponent<Props> = ({
  className,
  file,
  collapseFile,
}) => {
  const classes = useStyles()
  return (
    <div
      className={clsx(className, classes.changesetFileFooter)}
      onMouseDown={(ev) => {
        collapseFile()
        ev.preventDefault()
      }}
    >
      <span className={clsx(classes.chevronContainer)}>
        <ChevronRightIcon
          className={clsx(classes.chevron, classes.chevronExpanded)}
        />
      </span>
      <span className={classes.changedLines} />
      <span className={classes.path}>{file.path}</span>
    </div>
  )
}

export default Registry.add("Changeset.File.Footer", ChangesetFileFooter)
