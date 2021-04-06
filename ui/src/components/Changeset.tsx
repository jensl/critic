import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles, useTheme } from "@material-ui/core/styles"
import useMediaQuery from "@material-ui/core/useMediaQuery"

import Registry from "."
import ChangesetActions from "./Changeset.Actions"
import ChangesetFiles, { Props as ChangesetFilesProps } from "./Changeset.Files"
import { AutomaticMode } from "../actions"
import { useChangeset, useReview, useSubscription } from "../utils"
import { loadFileDiffsForChangeset } from "../actions/changeset"

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
  automaticMode?: AutomaticMode
  setAutomaticMode?: (mode: AutomaticMode) => void
  ChangesetFilesProps?: Partial<Omit<ChangesetFilesProps, "variant">>
}

const Changeset: FunctionComponent<Props> = ({
  className,
  variant,
  integrated = false,
  automaticMode,
  setAutomaticMode,
  ChangesetFilesProps = {},
}) => {
  const classes = useStyles()
  const useSideBySide = useMediaQuery(useTheme().breakpoints.up("lg"))
  const effectiveVariant =
    variant ?? (useSideBySide ? "side-by-side" : "unified")
  const { changeset } = useChangeset()
  const review = useReview()
  useSubscription(loadFileDiffsForChangeset, changeset, { reviewID: review.id })
  return (
    <div className={clsx(className, classes.changeset)}>
      <ChangesetActions
        variant={effectiveVariant}
        integrated={integrated}
        automaticMode={automaticMode}
        setAutomaticMode={setAutomaticMode}
      />
      <ChangesetFiles
        variant={effectiveVariant}
        integrated={integrated}
        automaticMode={automaticMode}
        {...ChangesetFilesProps}
      />
    </div>
  )
}

export default Registry.add("Changeset", Changeset)
