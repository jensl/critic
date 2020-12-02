export interface ResourceData {
  [name: string]: any
}

// FIXME: Should be a union of all resource types. Maybe.
export type Resource = any

// export type JSONData =
//   | null
//   | boolean
//   | number
//   | string
//   | JSONData[]
//   | { [key: string]: JSONData }

export type JSONData = any
