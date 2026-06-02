import asyncio

from app.agents.chat_graph import prepare_chat_messages
from app.config import settings
from app.profiles.store import ProfileStore


async def main() -> None:
    store = ProfileStore(settings.profiles_data_dir)
    msgs, used, retr, scenario = await prepare_chat_messages(
        store,
        condition="A",
        profile_id="pf-004",
        user_message="hola",
        include_ws_animation_protocol=True,
        scenario_id="casual_support",
    )
    print("ok", len(msgs), "profile_used", used, "retrieval", retr, "scenario", scenario)


if __name__ == "__main__":
    asyncio.run(main())
