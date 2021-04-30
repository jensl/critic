import React, { FunctionComponent } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"
import { useSelector } from "../store"
import { useMousePosition } from "../utils/Mouse"

const useStyles = makeStyles((theme) => ({
  root: { position: "absolute", ...theme.critic.selectionHighlight },
}))

type Props = {
  className?: string
}

const SelectionHighlight: FunctionComponent<Props> = ({ className }) => {
  const classes = useStyles()
  const { isRangeSelecting, selectedOutlineRect } = useSelector(
    (state) => state.ui.selectionScope,
  )
  if (!isRangeSelecting || !selectedOutlineRect) return null
  const { top, right, bottom, left } = selectedOutlineRect
  const width = right - left
  const height = bottom - top
  return (
    <div
      className={clsx(className, classes.root)}
      style={{
        top: top - 2,
        left: left - 2,
        width: width + 4,
        height: height + 4,
      }}
    />
  )
}

export default SelectionHighlight
