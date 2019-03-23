import asyncio
import discord
import os
import datetime

from baseball_wrapper import get_highlight, get_baseball_blurb, get_log as get_baseball_log
from football_wrapper import get_football_blurb, start_or_sit
from basketball_wrapper import get_basketball_blurb, get_log as get_basketball_log, get_lowlight, \
    get_highlight as get_bball_highlight, get_live_log, get_last
from help_commands import get_help_text


class SportsClient(discord.Client):

    @asyncio.coroutine
    def on_message(self, message):
        if message.channel.name in ["baseball"]:
            yield from self.handle_baseball_request(message)
        elif message.channel.name in ["american-football"]:
            yield from self.handle_football_request(message)
        elif message.channel.name in ["sportsbot-testing", "basketball", "better-late-than-never", "fuck-kevin-durant",
                                      "people-order-our-patties"]:
            yield from self.handle_basketball_request(message)

    def handle_football_request(self, message):
        sport = 'nfl'
        content_lower = message.content.lower()
        # /blurb [firstname]* [lastname]*
        if content_lower.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        elif content_lower.startswith('/start'):
            msg = content_lower.split()[1:]
            try:
                embed = start_or_sit(msg)
                yield from self.send_message(message.channel, embed=embed)
            except Exception as ex:
                raise ex

    def handle_basketball_request(self, message):
        sport = 'nba'
        content_lower = message.content.lower()
        # /blurb [firstname]* [lastname]*
        if content_lower.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        # /log [player]*
        elif content_lower.startswith('/log'):
            try:
                search = " ".join(message.content.split()[1:])
                embedded_stats = get_basketball_log(search)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                raise ex
        elif content_lower.startswith('/live'):
            try:
                search = message.content.split()[1:]
                embedded_stats = get_live_log(search)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                raise ex
        elif content_lower.startswith('/last'):
            msg = message.content.split()[1:]
            try:
                games = int(msg[0])
                if not games:
                    raise ValueError('A number of last games must be provided')
                if len(msg) < 2:
                    raise ValueError('Must provide both a number of games and a name')
                embedded_stats = get_last(" ".join(msg[1:]), last=games)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                raise ex
        elif content_lower.startswith('/highlight'):
            try:
                yield from self.do_bball_highlight(channel=message.channel)
            except Exception as ex:
                raise ex
        elif content_lower.startswith('/lowlight'):
            try:
                yield from self.do_bball_lowlight(channel=message.channel)
            except Exception as ex:
                raise ex

    def handle_baseball_request(self, message):
        sport = 'mlb'
        # /help
        content_lower = message.content.lower()
        if content_lower.startswith('/help'):
            try:
                help_map = discord.Embed(title="Commands List", description=get_help_text())
                yield from self.send_message(message.channel, embed=help_map)
            except Exception as ex:
                raise ex

        # /blurb [firstname]* [lastname]*
        if content_lower.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        # /last [num days]* [player]*
        if content_lower.startswith('/last'):
            msg = message.content.split()[1:]
            try:
                days = int(msg[0])
                if not days:
                    raise ValueError('A number of last days must be provided')
                if len(msg) < 2:
                    raise ValueError('Must provide both a number of days and a name')
                embedded_stats = get_baseball_log(" ".join(msg[1:]), last_days=days)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                raise ex
        # /log [player]*
        if content_lower.startswith('/log'):
            try:
                search = " ".join(message.content.split()[1:])
                embedded_stats = get_baseball_log(search)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                raise ex
        # /season [year] [player]*
        if content_lower.startswith('/season'):
            msg = message.content.split()[1:]
            try:
                if msg[0].isdigit():
                    embedded_stats = get_baseball_log(" ".join(msg[1:]), season=True, season_year=msg[0])
                else:
                    embedded_stats = get_baseball_log(" ".join(msg), season=True)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                raise ex
        # /highlight [player]* [index]
        if content_lower.startswith('/highlight'):
            msg = message.content.split()[1:]
            response = "\n%s\n%s"
            try:
                if msg[0] == 'index':
                    search = '%2B'.join(msg[1:])
                    highlights = get_highlight(search, list_index=True)
                    yield from self.send_message(message.channel, embed=highlights)
                elif msg[-1].isdigit():
                    index = msg[-1]
                    search = '%2B'.join(msg[:-1])
                    highlight = get_highlight(search, int(index) - 1)
                    yield from self.send_message(message.channel, content=response % highlight)
                else:
                    highlight = get_highlight('%2B'.join(msg))
                    yield from self.send_message(message.channel, content=response % highlight)
            except Exception as ex:
                raise ex

    def handle_blurb(self, message, sport):
        msg = message.content.split()[1:]
        try:
            search = " ".join(msg[0:])
            if not search:
                raise ValueError('A name must be provided')
            if sport == 'mlb':
                blurb, name = get_baseball_blurb(search)
            elif sport == 'nfl':
                blurb, name = get_football_blurb(search)
            elif sport == 'nba':
                blurb, name = get_basketball_blurb(search)
            else:
                raise ValueError(f"Invalid value for 'sport': {sport}")
            embedded_blurb = discord.Embed(title=name, description=blurb)
            yield from self.send_message(message.channel, embed=embedded_blurb)
        except Exception as ex:
                raise ex

    def get_channel_from_name(self, channel_name):
        return discord.utils.get(client.get_all_channels(), name=channel_name)

    async def highlight_lowlight_loop(self):
        await self.wait_until_ready()
        channel = self.get_channel_from_name("basketball")
        while not self.is_closed:
            # check time every minute
            now = datetime.datetime.now()
            if now.hour == 14 and now.minute == 30:
                embed = get_bball_highlight()
                if embed:
                    await self.send_message(channel, embed=embed)
                else:
                    await self.send_message(channel, content="No highlight of the day yesterday")
            elif now.hour == 15 and now.minute == 0:
                embed = get_lowlight()
                if embed:
                    await self.send_message(channel, embed=embed)
                else:
                    await self.send_message(channel, content="No lowlight of the day yesterday")
            await asyncio.sleep(60)

    def do_bball_highlight(self, channel=None):
        embed = get_bball_highlight()
        if embed:
            yield from self.send_message(channel, embed=embed)
        else:
            yield from self.send_message(channel, content="No highlight of the day yesterday")

    def do_bball_lowlight(self, channel=None):
        embed = get_lowlight()
        if embed:
            yield from self.send_message(channel, embed=embed)
        else:
            yield from self.send_message(channel, content="No lowlight of the day yesterday")


if __name__ == "__main__":
    # token = json.loads(open('token.json', 'r').read())["APP_TOKEN"]
    client = SportsClient()
    token = os.environ.get('TOKEN', '')
    client.loop.create_task(client.highlight_lowlight_loop())
    client.run(token)
