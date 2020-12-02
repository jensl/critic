/*
 * Copyright 2019 the Critic contributors, Opera Software ASA
 *
 * Licensed under the Apache License, Version 2.0 (the
); you may not
 * use this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an
 BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

import { immerable } from "immer"

import { primaryMap } from "../reducers/resource"

type SessionData = {
  user: null | number
  type: null | "normal" | "accesstoken"
  fields: FieldData[]
  providers: ProviderData[]
}

type SessionProps = {
  user: null | number
  type: null | "normal" | "accesstoken"
  fields: Field[]
  providers: Provider[]
}

class Session {
  [immerable] = true

  constructor(
    readonly user: null | number,
    readonly type: null | "normal" | "accesstoken",
    readonly fields: Field[],
    readonly providers: Provider[],
  ) {}

  static new(props: SessionProps) {
    return new Session(props.user, props.type, props.fields, props.providers)
  }

  static prepare(value: SessionData): SessionProps {
    return {
      ...value,
      fields: value.fields.map(Field.new),
      providers: value.providers.map(Provider.new),
    }
  }

  static reducer = primaryMap<Session, string>(
    "sessions",
    (_session) => "current",
  )

  get props(): SessionProps {
    return this
  }
}

type FieldData = {
  identifier: string
  label: string
  hidden: boolean
  description: string
}

type FieldProps = FieldData

export class Field {
  [immerable] = true

  constructor(
    readonly identifier: string,
    readonly label: string,
    readonly hidden: boolean,
    readonly description: string,
  ) {}

  static new(props: FieldProps) {
    return new Field(
      props.identifier,
      props.label,
      props.hidden,
      props.description,
    )
  }
}

type ProviderData = {
  identifier: string
  title: string
  account_id_label: string
}

type ProviderProps = ProviderData

export class Provider {
  [immerable] = true

  constructor(
    readonly identifier: string,
    readonly title: string,
    readonly accountIdLabel: string,
  ) {}

  static new(props: ProviderProps) {
    return new Provider(props.identifier, props.title, props.account_id_label)
  }
}

export default Session
