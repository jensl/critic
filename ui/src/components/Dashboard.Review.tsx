import React, { FunctionComponent } from "react"

import Registry from "."
import Breadcrumb from "./Breadcrumb"
import SetPrefix from "../utils/PrefixContext"
import ReviewContext from "./Review.Context"
import { useParams } from "react-router"

type Params = { category: string }

const DashboardReview: FunctionComponent = () => {
  const { category } = useParams<Params>()
  const prefix = `/dashboard/${category}`
  return (
    <Breadcrumb category="dashboard" label={category} path={prefix}>
      <SetPrefix prefix={prefix}>
        <ReviewContext />
      </SetPrefix>
    </Breadcrumb>
  )
}

export default Registry.add("Dashboard.Review", DashboardReview)
