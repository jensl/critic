import React, { useContext, useEffect, useState } from "react"
import { WEB_SOCKET_MESSAGE } from "../actions"
import { assertNotNull } from "../debug"
import {
  PublishedMessage,
  IncomingMessage,
  OutgoingMessage,
} from "../protocol/WebSocket"
import { useDispatch } from "../store"
import Token from "./Token"

const INITIAL_DELAY = 100

type ChannelListener = (message: PublishedMessage) => "remove" | undefined

class Channel {
  handles: Set<Token>
  listeners: Map<Token, ChannelListener>

  constructor(readonly name: string, readonly subscribed: Promise<void>) {
    this.handles = new Set()
    this.listeners = new Map()
  }

  addHandle() {
    const token = Token.create()
    this.handles.add(token)
    return () => void this.handles.delete(token)
  }

  addListener(listener: ChannelListener) {
    const token = Token.create()
    this.listeners.set(token, listener)
    return () => void this.listeners.delete(token)
  }

  incoming(message: PublishedMessage) {
    const toRemove = []
    for (const [token, listener] of this.listeners.entries()) {
      try {
        if (listener(message) === "remove") toRemove.push(token)
      } catch (error) {
        console.error("WebSocket channel listener crashed!", {
          message,
          error,
        })
      }
    }
    for (const token of toRemove) this.listeners.delete(token)
  }
}

type ConnectionListener = (
  message: IncomingMessage | "closed",
) => "remove" | void

class Connection {
  channels: Map<string, Channel>
  listeners: Map<Token, ConnectionListener>

  constructor(readonly ws: WebSocket) {
    this.channels = new Map()
    this.listeners = new Map()
  }

  send(message: OutgoingMessage) {
    this.ws.send(JSON.stringify(message))
  }

  async subscribe(name: string, message?: OutgoingMessage) {
    let channel = this.channels.get(name)
    if (!channel) {
      channel = new Channel(
        name,
        new Promise((resolve, reject) => {
          this.addListener((message) => {
            if (message === "closed") reject("connection closed")
            else if (
              "subscribed" in message &&
              message.subscribed.includes(name)
            ) {
              resolve(undefined)
            }
          })
          this.send(message ?? { subscribe: name })
        }),
      )
      this.channels.set(name, channel)
    }
    await channel.subscribed
    return channel
  }

  addListener(listener: ConnectionListener) {
    const token = Token.create()
    this.listeners.set(token, listener)
    return () => void this.listeners.delete(token)
  }

  incoming(message: IncomingMessage) {
    const toRemove = []
    for (const [token, listener] of this.listeners.entries()) {
      try {
        if (listener(message) === "remove") toRemove.push(token)
      } catch (error) {
        console.error("WebSocket connection listener crashed!", {
          message,
          error,
        })
      }
    }
    for (const token of toRemove) this.listeners.delete(token)
    if ("publish" in message) {
      const {
        channel: channelName,
        message: publishedMessage,
      } = message.publish
      const channel = this.channels.get(channelName)
      if (channel) channel.incoming(publishedMessage)
    }
  }
}

const Context = React.createContext<Connection | null>(null)

const ConnectWebSocket: React.FunctionComponent = ({ children }) => {
  const dispatch = useDispatch()
  const [connection, setConnection] = useState<Connection | null>(null)
  const [reconnect, setReconnect] = useState(true)
  const [delay, setDelay] = useState(INITIAL_DELAY)

  const prefix = window.location.origin.replace(/^http(s?):/, "ws$1:")

  useEffect(() => {
    if (!reconnect) return
    setReconnect(false)

    const ws = new WebSocket(`${prefix}/ws`, ["pubsub_1"])
    const connection = new Connection(ws)

    let opened = false

    ws.onopen = () => {
      console.info("WebSocket connection opened")
      opened = true
      setConnection(connection)
    }

    ws.onclose = ({ code }) => {
      let usedDelay
      if (opened) {
        console.info("WebSocket connection closed", { code })
        setConnection(null)
        usedDelay = INITIAL_DELAY
      } else {
        console.info("WebSocket connection failed", { code })
        usedDelay = delay * 2
      }
      console.info(`WebSocket reconnect in ${usedDelay / 1000} seconds`)
      setDelay(usedDelay)
      setTimeout(() => setReconnect(true), usedDelay)
    }

    ws.onmessage = ({ data }) => {
      try {
        const payload = JSON.parse(data) as IncomingMessage

        if ("publish" in payload) {
          const { channel, message } = payload.publish
          dispatch({ type: WEB_SOCKET_MESSAGE, channel, message })
        }

        connection.incoming(payload)
      } catch (error) {
        console.error("Unexpected WebSocket message!", { data })
      }
    }
  }, [reconnect])

  return <Context.Provider value={connection}>{children}</Context.Provider>
}

type UseChannelOptions = {
  subscribeMessage?: OutgoingMessage
}

export const useChannel = (
  name: string | null,
  listener: ChannelListener,
  { subscribeMessage }: UseChannelOptions = {},
) => {
  const connection = useContext(Context)

  useEffect(() => {
    if (!connection || !name) return
    connection
      .subscribe(name, subscribeMessage)
      .then((channel) => channel.addListener(listener))
  }, [connection, name])
}

export default ConnectWebSocket
