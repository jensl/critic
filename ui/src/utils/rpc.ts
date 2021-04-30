export class RPCError extends Error {}
export class RPCUsageError extends RPCError {}

export const rpcJSON = async <T>(
  methodName: string,
  parameters: { [key: string]: any },
) => {
  const response = await fetch(`/api/rpc/v1/${methodName}`, {
    method: "POST",
    body: JSON.stringify(parameters),
    credentials: "same-origin",
    headers: {
      "content-type": "application/vnd.api+json",
      accept: "application/vnd.api+json",
    },
  })

  switch (response.status) {
    case 200:
      return (await response.json()) as T
    case 400:
      throw new RPCUsageError(await response.text())
    default:
      throw new RPCError(await response.text())
  }
}
