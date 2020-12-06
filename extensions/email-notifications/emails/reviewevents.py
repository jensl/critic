from critic import api
from critic import pubsub
from critic.extension import Message, Subscription

async def main(critic: api.critic.Critic, subscription: Subscription)->None:
    async for message_handle in subscription.messages:
        async with message_handle as message:
