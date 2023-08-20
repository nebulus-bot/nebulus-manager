import asyncio
import logging
import random
from typing import Literal, Optional

import aiohttp
import discord
from discord.ext import commands, tasks
import psycopg2
from psycopg2.extensions import connection

import breadcord
from breadcord.core_modules.module_manager import ModuleManager
from breadcord.core_modules.settings_manager import Settings
from data.modules.nebulus_manager.BaseCog import BaseModule


class NebulusHandler(logging.Handler):
    def __init__(self, bot: breadcord.Bot):
        super().__init__()
        self.bot = bot
        self.webhook = discord.Webhook.from_url(self.bot.settings.nebulus_manager.logging_webhook.value, session=aiohttp.ClientSession())
        asyncio.create_task(self.webhook.edit(
            name="Nebulus: Logger",
            reason="Proper Webhook Config"
        ))

    def emit(self, record: logging.LogRecord) -> None:
        self.format(record)

        asyncio.create_task(self.webhook.send(
            f"**{record.levelname}**    {record.name}   |   {record.message}"
        ))


class NebulusManager(BaseModule):
    def __init__(self, module_id: str, /):
        super().__init__(module_id)

        self.management_guild = discord.Object(self.settings.management_guild.value)
        self.activities = []
        self._activity = None

        self.connection: connection = psycopg2.connect(
            user=self.settings.db_user.value,
            password=self.settings.db_password.value,
            host=self.settings.db_host.value,
            port=self.settings.db_port.value,
            database=self.settings.db.value,
        )

    @tasks.loop(seconds=30)
    async def switch_presence(self):
        curr_activity = self._activity
        # default to the first activity if not set or invalid
        if curr_activity not in self.activities:
            await self.bot.change_presence(activity=discord.CustomActivity(
                name="Custom Status",
                state=self.activities[0]
            ))
            self._activity = self.activities[0]
            return
        # use modulo to start from the beginning once the list is exhausted
        next_activity_index = (self.activities.index(curr_activity) + 1) % len(self.activities)
        self._activity = self.activities[next_activity_index]
        await self.bot.change_presence(activity=discord.CustomActivity(
            name="Custom Status",
            state=self.activities[next_activity_index]
        ))

    async def cog_load(self) -> None:
        self.logger.info("Loading core module `module_manager` with correct guild syncing")
        await self.bot.remove_cog("ModuleManager")
        await self.bot.add_cog(ModuleManager("module_manager"), guild=self.management_guild)
        self.logger.info("Loaded core module `module_manager` with correct guild syncing!")

        self.logger.info("Loading core module `settings_manager` with correct guild syncing")
        await self.bot.remove_cog("Settings")
        await self.bot.add_cog(Settings("settings_manager"), guild=self.management_guild)
        self.logger.info("Loaded core module `settings_manager` with correct guild syncing!")

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.addHandler(NebulusHandler(self.bot))
        self.logger.info("Connected to discord log sync.")

        self.activities.append(
            f"Watching {len(self.bot.guilds)} guild{'s' if len(self.bot.guilds) > 1 else ''} with {len(self.bot.users)} user{'s' if len(self.bot.users) > 1 else ''}"
        )
        self.switch_presence.start()

    @commands.command("sync")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "^"]]):
        if not guilds:
            if spec == "~":
                await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "-":
                ctx.bot.tree.clear_commands()
                await ctx.bot.tree.sync()
            else:
                await ctx.bot.tree.sync()

            await ctx.send(f"Synced commands {'globally' if spec is None else 'to the current guild.'}")
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

    @commands.command()
    @commands.is_owner()
    async def add_status(self, ctx: commands.Context, *, status):
        self.activities.append(status)
        await ctx.send(f"Appended status: `{status}`")

    @commands.command()
    @commands.is_owner()
    async def list_status(self, ctx: commands.Context):
        description = []
        status_no = 0
        for status in self.activities:
            description.append(f"{status_no}. `{status.name}`")

        embed = discord.Embed(
            title="Status List",
            description="\n".join(description)
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def remove_status(self, ctx: commands.Context, status_no: int):
        self.activities.pop(status_no)
        await ctx.send(f"Removed `{status_no}`")


async def setup(bot: breadcord.Bot):
    await bot.add_cog(NebulusManager("nebulus_manager"), guild=discord.Object(bot.settings.nebulus_manager.management_guild.value))
