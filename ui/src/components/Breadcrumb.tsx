import React, { useEffect, FunctionComponent, useMemo } from "react"

import { PushBreadcrumb } from "../utils/BreadcrumbContext"

type Props = {
  category?: string
  label: string
  path?: string | null
}

const Breadcrumb: FunctionComponent<Props> = ({
  category = null,
  label,
  path = null,
  children,
}) => (
  <PushBreadcrumb
    crumb={useMemo(() => ({ category, label, path }), [category, label, path])}
  >
    {children}
  </PushBreadcrumb>
)

export default Breadcrumb
