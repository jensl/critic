import email.message
import json

from multidict import MultiDictProxy

from critic import api
from critic.extension import Endpoint, Request
from critic import pubsub


async def send_email(critic: api.critic.Critic, request: Request) -> None:
    message = email.message.EmailMessage()
    message["From"] = "test-extension@example.org"
    message["To"] = ", ".join(request.query.getall("to"))
    message["Subject"] = "Test email"
    if "message_id" in request.query:
        message["Message-Id"] = request.query.get("message_id")
    message.set_content("This is a test email.")

    await pubsub.publish(
        critic,
        "test-extension",
        pubsub.PublishMessage(
            pubsub.ChannelName("email/outgoing"), pubsub.Payload(message)
        ),
    )

    async with request.response(204):
        pass


async def echo(
    critic: api.critic.Critic, request: Request, request_number: int
) -> None:
    def reduce_multidict(value: MultiDictProxy) -> object:
        return {
            key: values if len(values := value.getall(key)) > 1 else values[0]
            for key in value
        }

    reduced = {
        "method": request.method,
        "path": request.path,
        "query": reduce_multidict(request.query),
        "headers": reduce_multidict(request.headers),
    }

    if request.has_body:
        try:
            reduced["json"] = await request.json()
        except ValueError:
            try:
                reduced["text"] = await request.text()
            except ValueError:
                reduced["body"] = repr(await request.read())

    async with request.response(
        200, headers={"content-type": "application/json"}
    ) as response:
        await response.write(
            json.dumps(
                {
                    "user": repr(critic.effective_user),
                    "accesstoken": repr(critic.access_token),
                    "request_data": reduced,
                    "request_number": request_number,
                },
                indent=2,
            )
        )


async def handle_endpoint(critic: api.critic.Critic, endpoint: Endpoint) -> None:
    request_counter = 0

    async for request_handle in endpoint.requests:
        async with request_handle as request:
            if request.path == "send-email":
                await send_email(critic, request)
            elif request.path == "echo":
                await echo(critic, request, request_counter)
            else:
                async with request.response(
                    400, headers={"content-type": "text/plain"}
                ) as response:
                    await response.write(f"Invalid request path: {request.path!r}")

            request_counter += 1
