type JSONData =
  | null
  | boolean
  | number
  | string
  | JSONData[]
  | { [key: string]: JSONData }

export type CreatedAPIObject = {
  action: "created"

  resource_name: string
  object_id: number
}

export type CreatedSystemEvent = {
  action: "created"

  resource_name: "systemevents"
  object_id: number

  category: string
  key: string
  title: string
  data: JSONData
}

export type CreatedSystemSetting = {
  action: "created"

  resource_name: "systemsettings"
  object_id: number

  key: string
}

export type CreatedBranch = {
  action: "created"

  resource_name: "branches"
  object_id: number

  repository_id: number
  name: string
}

export type CreatedReviewEvent = {
  action: "created"

  resource_name: "reviewevents"
  object_id: number

  review_id: number
  event_type: string
}

export type CreatedUserEmail = {
  action: "created"

  resource_name: "reviewevents"
  object_id: number

  user_id: number
}

export type ModifiedAPIObject = {
  action: "modified"

  resource_name: string
  object_id: number

  updates: { [key: string]: JSONData }
}

export type ModifiedSystemSetting = {
  action: "modified"

  resource_name: "systemsettings"
  object_id: number

  key: string
  updates: { [key: string]: JSONData }
}

export type DeletedAPIObject = {
  action: "deleted"

  resource_name: "systemsettings"
  object_id: number
}

export type DeletedRepository = {
  action: "deleted"

  resource_name: "repositories"
  object_id: number

  name: string
  path: string
}

export type PublishedMessage =
  | CreatedAPIObject
  | CreatedSystemEvent
  | CreatedSystemSetting
  | CreatedBranch
  | CreatedReviewEvent
  | CreatedUserEmail
  | ModifiedAPIObject
  | ModifiedSystemSetting
  | DeletedAPIObject
  | DeletedRepository

export type SubscribeResponse = {
  subscribed: string[]
}

export type UnsubscribeResponse = {
  unsubscribed: string[]
}

export type PublishNotification = {
  publish: {
    channel: string
    message: PublishedMessage
  }
}

export type MonitorChangesetResponse = {
  monitor_changeset: {
    changeset_id: number
    completion_level: string[]
  }
}

export type IncomingMessage =
  | SubscribeResponse
  | UnsubscribeResponse
  | PublishNotification
  | MonitorChangesetResponse

export type SubscribeRequest = {
  subscribe: string | string[]
}

export type UnsubscribeRequest = {
  unsubscribe: string | string[]
}

export type MonitorChangesetRequest = {
  monitor_changeset: {
    changeset_id: number
    required_levels?: string[]
  }
}

export type OutgoingMessage =
  | SubscribeRequest
  | UnsubscribeRequest
  | MonitorChangesetRequest
