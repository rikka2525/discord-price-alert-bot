"""Discord price alert bot entry point."""

from __future__ import annotations

import asyncio
import logging
import sqlite3

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from api_client import CoinGeckoClient, PriceAPIError
from config import load_settings
from database import AlertRepository
from logic import is_triggered

settings = load_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("price-alert-bot")


class PriceAlertBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.repository = AlertRepository(settings.database_path)
        self.http_session: aiohttp.ClientSession | None = None
        self.price_client: CoinGeckoClient | None = None

    async def setup_hook(self) -> None:
        self.repository.initialize()
        self.http_session = aiohttp.ClientSession(
            headers={"User-Agent": "DiscordPriceAlertBot/1.0"}
        )
        self.price_client = CoinGeckoClient(self.http_session)
        await self.tree.sync()
        price_check.change_interval(minutes=settings.check_interval_minutes)
        price_check.start()

    async def close(self) -> None:
        price_check.cancel()
        if self.http_session is not None:
            await self.http_session.close()
        await super().close()


bot = PriceAlertBot()


def _direction_label(direction: str) -> str:
    return "以上" if direction == "above" else "以下"


async def _require_guild(interaction: discord.Interaction) -> bool:
    if interaction.guild_id is None or interaction.channel_id is None:
        await interaction.response.send_message("このコマンドはサーバー内で使用してください。")
        return False
    return True


@bot.tree.command(name="register", description="暗号資産の価格通知を登録します")
@app_commands.describe(
    coin_id="CoinGecko上のID（例: bitcoin, ethereum）",
    target_price="通知する米ドル価格",
    direction="価格が目標以上または以下になったら通知",
)
@app_commands.choices(
    direction=[
        app_commands.Choice(name="目標価格以上", value="above"),
        app_commands.Choice(name="目標価格以下", value="below"),
    ]
)
async def register(
    interaction: discord.Interaction,
    coin_id: str,
    target_price: float,
    direction: app_commands.Choice[str],
) -> None:
    if not await _require_guild(interaction):
        return
    if target_price <= 0:
        await interaction.response.send_message("目標価格は0より大きい値にしてください。", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    assert bot.price_client is not None
    try:
        result = await bot.price_client.get_price(coin_id)
        alert_id = await asyncio.to_thread(
            bot.repository.add_alert,
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            user_id=interaction.user.id,
            coin_id=result.coin_id,
            target_price=target_price,
            direction=direction.value,
        )
    except PriceAPIError:
        await interaction.followup.send(
            "銘柄を確認できませんでした。CoinGeckoのIDを確認するか、少し待って再実行してください。",
            ephemeral=True,
        )
        return
    except sqlite3.IntegrityError:
        await interaction.followup.send("同じ通知条件はすでに登録されています。", ephemeral=True)
        return

    await interaction.followup.send(
        f"通知 #{alert_id} を登録しました。\n"
        f"`{result.coin_id}` が **${target_price:,.2f} {_direction_label(direction.value)}**\n"
        f"現在価格: **${result.usd:,.2f}**",
        ephemeral=True,
    )


@bot.tree.command(name="list", description="自分が登録した価格通知を一覧表示します")
async def list_alerts(interaction: discord.Interaction) -> None:
    if not await _require_guild(interaction):
        return
    alerts = await asyncio.to_thread(
        bot.repository.list_alerts,
        guild_id=interaction.guild_id,
        user_id=interaction.user.id,
    )
    if not alerts:
        await interaction.response.send_message("登録中の通知はありません。", ephemeral=True)
        return
    lines = [
        f"`#{alert.id}` {alert.coin_id}: ${alert.target_price:,.2f} {_direction_label(alert.direction)}"
        for alert in alerts
    ]
    await interaction.response.send_message("**登録中の価格通知**\n" + "\n".join(lines), ephemeral=True)


@bot.tree.command(name="delete", description="登録した価格通知を削除します")
@app_commands.describe(alert_id="/list に表示される通知番号")
async def delete(interaction: discord.Interaction, alert_id: int) -> None:
    if not await _require_guild(interaction):
        return
    deleted = await asyncio.to_thread(
        bot.repository.delete_alert,
        alert_id=alert_id,
        guild_id=interaction.guild_id,
        user_id=interaction.user.id,
    )
    message = f"通知 #{alert_id} を削除しました。" if deleted else "該当する通知が見つかりません。"
    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="price", description="暗号資産の現在価格を確認します")
@app_commands.describe(coin_id="CoinGecko上のID（例: bitcoin, ethereum）")
async def price(interaction: discord.Interaction, coin_id: str) -> None:
    await interaction.response.defer()
    assert bot.price_client is not None
    try:
        result = await bot.price_client.get_price(coin_id)
    except PriceAPIError:
        await interaction.followup.send("価格を取得できませんでした。銘柄IDを確認してください。")
        return
    await interaction.followup.send(f"**{result.coin_id}** の現在価格: **${result.usd:,.2f} USD**")


@tasks.loop(minutes=5)
async def price_check() -> None:
    alerts = await asyncio.to_thread(bot.repository.all_alerts)
    if not alerts or bot.price_client is None:
        return
    try:
        prices = await bot.price_client.get_prices([alert.coin_id for alert in alerts])
    except PriceAPIError as exc:
        logger.warning("Scheduled price check skipped: %s", exc)
        return

    for alert in alerts:
        current_price = prices.get(alert.coin_id)
        if current_price is None or not is_triggered(alert, current_price):
            continue
        try:
            channel = bot.get_channel(alert.channel_id) or await bot.fetch_channel(alert.channel_id)
            if not isinstance(channel, discord.abc.Messageable):
                raise TypeError("registered channel is not messageable")
            await channel.send(
                f"🔔 <@{alert.user_id}> **価格アラート**\n"
                f"`{alert.coin_id}` が **${current_price:,.2f}** になりました。\n"
                f"設定条件: ${alert.target_price:,.2f} {_direction_label(alert.direction)}"
            )
            await asyncio.to_thread(bot.repository.delete_triggered, alert.id)
        except (discord.HTTPException, discord.Forbidden, discord.NotFound, TypeError) as exc:
            logger.warning("Could not deliver alert %s: %s", alert.id, exc)


@price_check.before_loop
async def before_price_check() -> None:
    await bot.wait_until_ready()


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "unknown")


if __name__ == "__main__":
    bot.run(settings.discord_token, log_handler=None)
