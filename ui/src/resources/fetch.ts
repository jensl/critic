import { Dispatch, AsyncThunk, Thunk } from "../state"
import { ResourceData, Resource, JSONData } from "../types"
import {
  RequestParams,
  FetchJSONParams,
  HandleError,
} from "../utils/Fetch.types"
import { fetchJSON } from "../utils/Fetch"
import { dataUpdate } from "../actions/data"
import { DataUpdateParams } from "../actions"
import { assertIsObject, assertNotReached, assertTrue } from "../debug"
import { RequestOptions } from "./types"
import { ResourceTypes } from "./resourcetypes"
import resourceDefinitions from "./definitions"
import {
  withParameters,
  include,
  excludeFields,
  method,
  payload,
} from "./requestoptions"
import { any, sorted } from "../utils/Functions"
import ResourceError, { ErrorResponseJSON } from "./resourceerror"

type BaseResponseJSON = {
  linked?: { [resourceName: string]: JSONData[] | "limited" }
  deleted?: { [resourceName: string]: (number | string)[] }
  invalid?: { [resourceName: string]: (number | string)[] }
}

type MainResponseJSON = {
  [resourceName: string]: JSONData[]
}

type ResponseJSON = BaseResponseJSON & MainResponseJSON

export interface PaginationInfo {
  total: number
}

export interface FetchResult<T> {
  resourceName: keyof ResourceTypes
  status: number | "delayed" | "deleted" | "notfound"
  json?: JSONData
  error?: ResourceData
  updates?: Map<string, any[]>
  primary: T[]
  limited?: Set<string>
  deleted: Map<string, Set<number | string>> | null
  invalid: Map<string, Set<number | string>> | null
  pagination: PaginationInfo | null
}

const mergeOptions = (current: RequestOptions, next: RequestOptions) => {
  Object.entries(next).forEach(([keyString, nextValue]) => {
    const key = keyString as keyof RequestOptions
    if (key in current) {
      const currentValue = current[key]
      switch (key) {
        case "context":
          current.context = `${currentValue}/${nextValue}`
          break
        case "params":
          Object.assign(
            currentValue as RequestParams,
            nextValue as RequestParams,
          )
          break
        case "include":
          const include = currentValue as string[]
          include.push(...(nextValue as string[]))
          break
        case "handleError":
          Object.assign(currentValue as HandleError, nextValue as HandleError)
          break
        default:
          assertNotReached(`Duplicate request option: ${key}`)
      }
    } else current[key] = nextValue as any
  })
  return current
}

const makeRequest = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  optionsList: RequestOptions[],
): FetchJSONParams => {
  const {
    defaultParams,
    defaultInclude,
    defaultExcludeFields,
    completeRequest,
  } = resourceDefinitions[resourceName]

  const finalOptionsList = []

  const disableDefaults = any(
    optionsList,
    ({ disableDefaults }) => !!disableDefaults,
  )

  if (!disableDefaults) {
    if (defaultParams) finalOptionsList.push(withParameters(defaultParams))
    if (defaultInclude) finalOptionsList.push(include(...defaultInclude))
    if (defaultExcludeFields)
      Object.entries(defaultExcludeFields).forEach(([resourceName, fields]) =>
        finalOptionsList.push(
          excludeFields(resourceName as keyof ResourceTypes, fields),
        ),
      )
  }

  const options: RequestOptions = {}

  finalOptionsList.push(...optionsList)
  finalOptionsList.reduce(mergeOptions, options)

  const { method, payload } = options

  if (completeRequest) completeRequest(options, payload)

  const context = options.context ? `${options.context}/` : ""
  const args = options.args ? `/${options.args}` : ""
  const path = `${context}${resourceName}${args}`

  const params = { ...options.params }
  if (options.include)
    params.include = sorted(new Set(options.include)).join(",")

  const { expectedStatus = [200, 202, 204, 404], handleError } = options

  const post = method === "POST" ? payload : undefined
  const put = method === "PUT" ? payload : undefined

  return {
    path,
    params,
    options: { method },
    post,
    put,
    expectStatus: expectedStatus,
    handleError,
  }
}

export const fetch = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  ...options: RequestOptions[]
): AsyncThunk<FetchResult<ResourceTypes[ResourceName]>> => async (dispatch) => {
  // var request: FetchJSONParams | null = null
  // var params: RequestParams = { ...resourceDefinition.defaultParams }
  // var include: string[] = [...(resourceDefinition.defaultInclude || [])]
  // var excludeFields: ExcludeFields = resourceDefinition.excludeFields || {}
  // var expectStatus: number[] | null = null

  // if (typeof arg !== "undefined")
  //   if (typeof arg === "number" || typeof arg === "string") path += "/" + arg
  //   else if (Array.isArray(arg)) path += "/" + arg.join(",")
  //   else if (isRequestOptions(arg)) {
  //     if ("arg" in arg) path += "/" + arg.arg
  //     if (Array.isArray(arg.args)) path += "/" + arg.args.join(",")
  //     if (arg.params) params = { ...params, ...arg.params }
  //     if (arg.include) include = [...include, ...arg.include]
  //     if (arg.excludeFields)
  //       excludeFields = mergeExcludeFields(excludeFields, arg.excludeFields)
  //     if (arg.request) request = arg.request
  //     if (arg.expectedStatus) expectStatus = arg.expectedStatus
  //   } else if (typeof arg === "object") Object.assign(params, arg)
  //   else assertNotReached()

  //else if (args.length && typeof args[0] === "object")
  //  Object.assign(request, args[0])

  const { status, json } = await dispatch(
    fetchJSON(makeRequest(resourceName, options)),
  )

  if (status !== 200) {
    const result = (status: "delayed" | "deleted" | "notfound") => ({
      resourceName,
      status,
      primary: [],
      deleted: null,
      invalid: null,
      pagination: null,
    })

    switch (status) {
      case 202:
        return result("delayed")
      case 204:
        return result("deleted")
      case 404:
        if (json.invalid) break
        return result("notfound")

      default:
        throw new Error("Unexpected HTTP status: " + status)
    }
  }

  return dispatch(handleJSONResponse({ resourceName, status, json }))
}

export const fetchOne = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  ...options: RequestOptions[]
): AsyncThunk<ResourceTypes[ResourceName]> => async (dispatch) => {
  const { primary } = await dispatch(fetch(resourceName, ...options))
  assertTrue(primary.length === 1)
  return primary[0]
}

type UpdatesFromJSONExtra<ResourceType> = {
  resourceName: keyof ResourceTypes
  deleted: Map<string, Set<number | string>>
  invalid: Map<string, Set<number | string>>
  limited: Set<string>
  primary: ResourceType[]
  pagination: PaginationInfo | null
}

const updatesFromJSON = <ResourceName extends keyof ResourceTypes>(
  mainResourceName: ResourceName,
  state: any,
  { linked = {}, deleted = {}, invalid = {}, ...main }: ResponseJSON,
): DataUpdateParams & UpdatesFromJSONExtra<ResourceTypes[ResourceName]> => {
  const limited = new Set<string>()

  const postProcess = (
    resourceName: ResourceName,
    items: JSONData[] | "limited",
  ): ResourceTypes[ResourceName][] => {
    var { recordType } = resourceDefinitions[resourceName]
    const construct = recordType.new
    const prepare = recordType.prepare || ((value: ResourceData) => value)
    const lookup = (resource: any, value: ResourceData) =>
      resource.byID
        ? resource.byID.get(value.id, null)
        : resource.get(value.id, null)
    const resource = state.resource[resourceName]
    if (items === "limited") {
      limited.add(resourceName as string)
      return []
    }
    return items.map((value: JSONData) => {
      assertIsObject(value)
      const prepared = prepare(value)
      if (value.is_partial) {
        // If the received value is partial (i.e. if the request used the
        // `fields` query parameter to skip some fields) then update an
        // existing record, if there is one. Otherwise, we'd end up nulling
        // the skipped fields in the existing record.
        delete prepared.is_partial
        const existing = lookup(resource, value)
        if (existing) {
          const existingProps = existing.props
          for (const key of Object.keys(existingProps))
            if (!value.hasOwnProperty(key)) prepared[key] = existingProps[key]
          return construct(Object.assign(existing.props, prepared))
        }
      }
      return construct(prepared)
    })
  }

  const primary = main[mainResourceName]
    ? postProcess(mainResourceName, main[mainResourceName])
    : []
  const updates = new Map<string, Resource[]>(
    [...new Set([mainResourceName as string, ...Object.keys(linked)])].map(
      (resourceName) => {
        const linkedItems = linked[resourceName]
          ? postProcess(resourceName as ResourceName, linked[resourceName])
          : []
        if (resourceName === mainResourceName)
          return [resourceName, [...primary, ...linkedItems]]
        return [resourceName, linkedItems]
      },
    ),
  )

  const pagination = ((main["pagination"] as unknown) as PaginationInfo) ?? null

  return {
    resourceName: mainResourceName,
    updates,
    primary,
    limited,
    deleted:
      deleted &&
      new Map<string, Set<number | string>>(
        Object.entries(deleted).map(([resourceName, ids]) => [
          resourceName,
          new Set(ids),
        ]),
      ),
    invalid:
      invalid &&
      new Map<string, Set<number | string>>(
        Object.entries(invalid).map(([resourceName, ids]) => [
          resourceName,
          new Set(ids),
        ]),
      ),
    pagination,
  }
}

export const handleJSONResponse = <ResourceName extends keyof ResourceTypes>({
  resourceName,
  status = 200,
  json,
  raiseOnError = false,
}: {
  resourceName: ResourceName
  status?: number
  json: ResponseJSON | ErrorResponseJSON
  raiseOnError?: boolean
}): Thunk<FetchResult<ResourceTypes[ResourceName]>> => (dispatch, getState) => {
  if (status >= 400 && raiseOnError)
    throw new ResourceError(status, json as ErrorResponseJSON)
  if (status !== 200) {
    return {
      resourceName,
      status,
      primary: [],
      json,
      deleted: null,
      invalid: null,
      pagination: null,
    }
  }
  const updates = updatesFromJSON(
    resourceName,
    getState(),
    json as ResponseJSON,
  )
  dispatch(dataUpdate(updates))
  return { status, json, ...updates }
}

const resourceRequest = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  args: FetchJSONParams,
): AsyncThunk<FetchResult<ResourceTypes[ResourceName]>> => async (dispatch) =>
  dispatch(
    handleJSONResponse<ResourceName>({
      ...(await dispatch(fetchJSON(args))),
      resourceName,
      raiseOnError: true,
    }),
  )

const primaryResource = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  options: RequestOptions[],
): AsyncThunk<ResourceTypes[ResourceName][]> => async (dispatch: Dispatch) => {
  const { primary } = await dispatch(
    resourceRequest(resourceName, makeRequest(resourceName, options)),
  )
  return primary
}

export const createResources = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  resources: ResourceData[],
  ...options: RequestOptions[]
): AsyncThunk<ResourceTypes[ResourceName][]> =>
  primaryResource(resourceName, [
    ...options,
    method("POST"),
    payload({ [resourceName]: resources }),
  ])

export const createResource = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  resource: ResourceData,
  ...options: RequestOptions[]
): AsyncThunk<ResourceTypes[ResourceName]> => async (dispatch) =>
  (
    await dispatch(
      primaryResource(resourceName, [
        ...options,
        method("POST"),
        payload(resource),
      ]),
    )
  )[0]

export const updateResources = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  resource: ResourceData,
  ...options: RequestOptions[]
): AsyncThunk<ResourceTypes[ResourceName][]> =>
  primaryResource(resourceName, [...options, method("PUT"), payload(resource)])

export const updateResource = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  resource: ResourceData,
  ...options: RequestOptions[]
): AsyncThunk<ResourceTypes[ResourceName]> => async (dispatch) =>
  (await dispatch(updateResources(resourceName, resource, ...options)))[0]

export const deleteResource = <ResourceName extends keyof ResourceTypes>(
  resourceName: ResourceName,
  ...options: RequestOptions[]
): AsyncThunk<FetchResult<ResourceTypes[ResourceName]>> =>
  resourceRequest(
    resourceName,
    makeRequest(resourceName, [...options, method("DELETE")]),
  )