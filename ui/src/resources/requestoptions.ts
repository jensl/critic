import { JSONData } from "../types"
import { RequestParams, HTTPMethod } from "../utils/Fetch.types"
import { ResourceTypes, RequestOptions } from "./types"
import { ErrorCode, ResourceError } from "./fetch"

export const withContext = (
  resourceName: keyof ResourceTypes,
  argument: number | string,
): RequestOptions => ({ context: `${resourceName}/${argument}` })
export const withArgument = (arg: number | string): RequestOptions => ({
  args: [String(arg)],
})
export const withArguments = (args: number[] | string[]): RequestOptions => ({
  args: (args as (number | string)[]).map((arg) => String(arg)),
})
export const withParameters = (params: RequestParams): RequestOptions => ({
  params,
})
export const withData = (data: any): RequestOptions => ({ data })
export const include = (
  ...include: (keyof ResourceTypes)[]
): RequestOptions => ({
  include,
})
export const includeFields = (
  resourceName: keyof ResourceTypes,
  fields: string[],
): RequestOptions => ({
  params: { [`fields[${resourceName}]`]: fields.join(",") },
})
export const excludeFields = (
  resourceName: keyof ResourceTypes,
  fields: string[],
): RequestOptions => ({
  params: { [`fields[${resourceName}]`]: `-${fields.join(",")}` },
})
export const payload = (payload: JSONData): RequestOptions => ({
  payload,
})
export const method = (method: HTTPMethod): RequestOptions => ({
  method,
})
export const expectStatuses = (
  ...expectedStatus: number[]
): RequestOptions => ({
  expectedStatus,
})
export const handleError = (
  code: ErrorCode,
  handler: (error: ResourceError) => boolean | undefined,
): RequestOptions => ({
  handleError: { [code]: handler },
})
export const disableDefaults = (): RequestOptions => ({ disableDefaults: true })
