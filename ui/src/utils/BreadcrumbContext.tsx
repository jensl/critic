import React, { useContext, useEffect, useMemo } from "react"

import { Breadcrumb } from "../actions"
import { Thunk } from "../state"
import { useDispatch } from "../store"

type BreadcrumbsSetter = (index: number, crumb: Breadcrumb) => Thunk<void>

const setBreadcrumb: BreadcrumbsSetter = (index, crumb) => (dispatch) =>
  dispatch({ type: "SET_BREADCRUMB", index, crumb })

const BreadcrumbContext = React.createContext<number>(0)

type Props = {
  crumb: Breadcrumb
}

export const PushBreadcrumb: React.FunctionComponent<Props> = ({
  crumb,
  children,
}) => {
  const dispatch = useDispatch()
  const index = useContext(BreadcrumbContext)
  const { category, label, path } = crumb

  useEffect(() => {
    dispatch(setBreadcrumb(index, crumb))
  }, [dispatch, index, category, label, path])

  useEffect(
    () => () => void dispatch({ type: "TRIM_BREADCRUMBS", length: index }),
    [],
  )

  return (
    <BreadcrumbContext.Provider value={index + 1}>
      {children}
    </BreadcrumbContext.Provider>
  )
}
