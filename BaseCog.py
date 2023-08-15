import breadcord


class BaseModule(breadcord.module.ModuleCog):
    def __int__(self, module_id: str):
        super().__init__(module_id)

    async def cog_load(self) -> None:
        for command in self.walk_app_commands():
            command.extras["cog"] = self.qualified_name
