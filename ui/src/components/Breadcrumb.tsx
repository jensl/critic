import React, { useEffect, FunctionComponent } from "react"

import { pushBreadcrumb } from "../actions/uiBreadcrumbs"
import { useDispatch } from "../store"

type Props = {
  category: string
  label: string
  path?: string | null
}

const Breadcrumb: FunctionComponent<Props> = ({
  category,
  label,
  path = null,
  children,
}) => {
  const dispatch = useDispatch()
  useEffect(() => dispatch(pushBreadcrumb(category, label, path)), [
    dispatch,
    category,
    label,
    path,
  ])
  return <>{children}</>
}

export default Breadcrumb
