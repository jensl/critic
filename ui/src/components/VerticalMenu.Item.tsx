import React, { useContext, useEffect } from "react"
import clsx from "clsx"

import { makeStyles } from "@material-ui/core/styles"

import { assertNotNull } from "../debug"

const useStyles = makeStyles((theme) => ({
  tabpanel: {
    flexGrow: 1,
    paddingLeft: theme.spacing(2),
  },
}))

type RemoveItem = () => void
export type AddItemParams = { id: string; title: string }
type AddItem = (params: AddItemParams) => RemoveItem

export const Context = React.createContext<[AddItem | null, string]>([null, ""])

type Props = {
  className?: string
  id: string
  title: string
}

const VerticalMenuItem: React.FunctionComponent<Props> = ({
  className,
  id,
  title,
  children,
}) => {
  const classes = useStyles()
  const [addItem, selectedID] = useContext(Context)
  assertNotNull(addItem)

  useEffect(() => addItem({ id, title }), [id, title])

  const isSelected = id === selectedID

  return (
    <div
      className={clsx(classes.tabpanel, className)}
      role="tabpanel"
      hidden={!isSelected}
      id={`vertical-tabpanel-${id}`}
    >
      {isSelected && children}
    </div>
  )
}

export default VerticalMenuItem
