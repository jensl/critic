import React, { useState } from "react"
import { Redirect, useHistory, useParams } from "react-router"

import Tabs from "@material-ui/core/Tabs"
import Tab from "@material-ui/core/Tab"
import { makeStyles } from "@material-ui/core/styles"

import { AddItemParams, Context } from "./VerticalMenu.Item"
import { usePrefix } from "../utils"

const useStyles = makeStyles((theme) => ({
  root: {
    display: "flex",
    flexDirection: "row",
    width: "100%",
  },
  tabs: {
    flexGrow: 0,
    borderRight: `1px solid ${theme.palette.divider}`,
  },
}))

type Props = {
  parameterName: string
}

type Item = {
  id: string
  title: string
}

const a11yProps = (id: string) => ({
  id: `vertical-tab-${id}`,
  "aria-controls": `vertical-tabpanel-${id}`,
})

const VerticalMenu: React.FunctionComponent<Props> = ({
  parameterName,
  children,
}) => {
  const classes = useStyles()
  const history = useHistory()
  const parameters = useParams<{ [key: string]: string }>()
  const [items, setItems] = useState<Item[]>([])
  const prefix = usePrefix()

  const addItem = ({ id, title }: AddItemParams) => {
    setItems((items) => [...items, { id, title }])
    return () => setItems((items) => items.filter((item) => item.id !== id))
  }

  const selectedID = parameters[parameterName] ?? false

  if (items.length > 0 && !selectedID)
    return <Redirect to={`${prefix}/${items[0].id}`} />

  return (
    <Context.Provider value={[addItem, selectedID]}>
      <div className={classes.root}>
        <Tabs
          className={classes.tabs}
          orientation="vertical"
          value={selectedID}
          onChange={(_, value) => history.push(`${prefix}/${value}`)}
        >
          {items.map(({ id, title }) => (
            <Tab key={id} value={id} label={title} {...a11yProps(id)} />
          ))}
        </Tabs>
        {children}
      </div>
    </Context.Provider>
  )
}

export default VerticalMenu
