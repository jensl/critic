import React, { useContext, useEffect } from "react"

import { Breadcrumb } from "../actions"
import { useDispatch } from "../store"

const BreadcrumbContext = React.createContext<Breadcrumb[]>([])

type Props = {
  crumb: Breadcrumb
}

export const PushBreadcrumb: React.FunctionComponent<Props> = ({
  crumb,
  children,
}) => {
  const dispatch = useDispatch()
  const { category, label, path } = crumb

  const previous = useContext(BreadcrumbContext)
  const crumbs = [...previous, crumb]

  useEffect(() => {
    dispatch({ type: "SET_BREADCRUMBS", crumbs })
    return () => {
      dispatch({ type: "SET_BREADCRUMBS", crumbs: previous })
    }
  }, [dispatch, previous, category, label, path])

  return (
    <BreadcrumbContext.Provider value={crumbs}>
      {children}
    </BreadcrumbContext.Provider>
  )
}
