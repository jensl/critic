import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, useTheme } from "@material-ui/core/styles"
import useMediaQuery from "@material-ui/core/useMediaQuery"

import Registry from "."
import ChangesetActions from "./Changeset.Actions"
import ChangesetFiles, { Props as ChangesetFilesProps } from "./Changeset.Files"

const useStyles = makeStyles({
  changeset: {},
  actions: {
    display: "flex",
  },
})

type Props = {
  className?: string
  variant?: "unified" | "side-by-side"
  integrated?: boolean
  ChangesetFilesProps?: Partial<Omit<ChangesetFilesProps, "variant">>
}

const Changeset: FunctionComponent<Props> = ({
  className,
  variant,
  integrated = false,
  ChangesetFilesProps = {},
}) => {
  const classes = useStyles()
  const useSideBySide = useMediaQuery(useTheme().breakpoints.up("lg"))
  const effectiveVariant =
    variant ?? (useSideBySide ? "side-by-side" : "unified")
  return (
    <div className={clsx(className, classes.changeset)}>
      <div className={classes.actions}>
        <ChangesetActions variant={effectiveVariant} integrated={integrated} />
      </div>
      <ChangesetFiles
        variant={effectiveVariant}
        integrated={integrated}
        {...ChangesetFilesProps}
      />
    </div>
  )
}

export default Registry.add("Changeset", Changeset)
