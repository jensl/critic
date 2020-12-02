import React, { useEffect, FunctionComponent } from "react"

import { PushBreadcrumb } from "../utils/BreadcrumbContext"

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
}) => (
  <PushBreadcrumb crumb={{ category, label, path }}>{children}</PushBreadcrumb>
)

export default Breadcrumb
