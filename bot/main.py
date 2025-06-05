import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
from discord.ui import View, Button
import os
import valo_api
import wavelink

from valo_api.endpoints import (
    get_account_details_by_name,
    get_match_history_by_puuid,
    get_mmr_details_by_puuid,
    get_leaderboard
)

# ------------------- Bot Class -------------------
class MyBot(commands.Bot):
    async def setup_hook(self):
        node = wavelink.Node(
          uri="http://lavalink-v2.pericsq.ro:6677",
          password="wwweasycodero",
          client=self
        )
        await wavelink.Pool.connect(nodes=[node])
        await self.load_extension("music")
        await self.load_extension("schedule")
        await self.load_extension("nba")

# ------------------- API Key, Env, Logging -------------------
valo_api.set_api_key("HDEV-bffb670d-98c1-48bf-a377-4e944f4e2b81")
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = MyBot(command_prefix="!", intents=intents)

# ------------------- Poll Classes -------------------
class PollView(View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.votes = {label: 0 for label in options}
        self.voters = {}

        for label in options:
            self.add_item(PollButton(label=label, view=self))

class PollButton(Button):
    def __init__(self, label, view: PollView):
        self.base_label = label
        self.view_ref = view
        super().__init__(label=f"{label} (0)", style=discord.ButtonStyle.primary, custom_id=label)

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        view = self.view_ref

        if user_id in view.voters:
            await interaction.response.send_message(
                f"You already voted for **{view.voters[user_id]}**.",
                ephemeral=True
            )
            return

        view.voters[user_id] = self.base_label
        view.votes[self.base_label] += 1

        for child in view.children:
            if isinstance(child, PollButton):
                label = child.base_label
                count = view.votes[label]
                child.label = f"{label} ({count})"

        await interaction.response.edit_message(view=view)
        await interaction.followup.send(f"✅ You voted for **{self.base_label}**", ephemeral=True)

# ------------------- Bot Events -------------------
@bot.event
async def on_ready():
    print("Bot is ready!")

@bot.event
async def on_guild_join(guild):
    channel = guild.system_channel
    if channel is None:
        for c in guild.text_channels:
            if c.permissions_for(guild.me).send_messages:
                channel = c
                break
    if channel:
        embed = discord.Embed(
            title="🤖 About Vantage",
            description=(
                "Welcome! Here are the main features and commands you can use:\n"
                "\n"
                "**Valorant Stats**\n"
                "`!stats NAME#TAG` — Get recent Valorant stats for a player (e.g. !stats 640509040147#htman).\n"
                "`!matchlist NAME#TAG` — List recent matches with basic stats.\n"
                "`!mmr NAME#TAG` — Show player's current and peak MMR.\n"
                "`!leaderboard [region]` — Show top 10 leaderboard players for a region (e.g. !leaderboard eu).\n"
                "\n"
                "**NBA Stats**\n"
                "`!gametoday` — Show today's NBA games and live scores with leaders.\n"
                "`!playerstats <player name>` — Show player career and current season stats (regular & playoffs).\n"
                "`!leagueleaders [STAT] [SEASON]` — Show top players for a stat this season (e.g. !leagueleaders PTS).\n"
                "`!roster <team name>` — Show the current roster for an NBA team (e.g. !roster lakers).\n"
                "`!standings [season] [season_type]` — Show NBA standings (e.g. !standings 2024-25 Regular Season).\n"
                "\n"
                "**Polls**\n"
                "`!poll question=\"Your Question\" choices=\"Option 1, Option 2, Option 3\"` — Create a poll with up to 5 options.\n"
                "\n"
                "**Game Scheduling**\n"
                "`!schedule @user1 @user2 2024-05-28 21:00` — Schedule a game and get a reminder 5 hours before.\n"
                "\n"
                "**Music**\n"
                "`!play <YouTube URL>` — Play a song in your current voice channel.\n"
                "`!skip` — Skip the current song.\n"
                "`!stop` — Stop music and disconnect the bot from voice chat.\n"
                "\n"
                "**Bot Info**\n"
                "`!about` — Show this help page.\n"
                "\n"
                "Type `!about` at any time to see this page again!\n"
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Bot by Mochi. DM me @greenteamatcha with feature requests!")
        await channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the matrix, {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "nigga" in message.content.lower():
        await message.channel.send(f"{message.author.mention} -- please don't pull a Will or Lion")
    if "autistic" in message.content.lower():
        await message.channel.send(f"{message.author.mention} -- we are an inclusive community")
    await bot.process_commands(message)

# ------------------- Poll Command -------------------
@bot.command()
async def poll(ctx, *, args):
    import re
    question_match = re.search(r'question="(.+?)"', args)
    choices_match = re.search(r'choices="(.+?)"', args)

    if not question_match or not choices_match:
        await ctx.send("Invalid format. Use: `!poll question=\"...\" choices=\"opt1, opt2, opt3\"`")
        return

    question = question_match.group(1)
    choices = [c.strip() for c in choices_match.group(1).split(',')]

    if not (2 <= len(choices) <= 5):
        await ctx.send("Please provide between 2 and 5 choices.")
        return

    embed = discord.Embed(title="📊 New Poll", description=question, color=discord.Color.blurple())
    await ctx.send(embed=embed, view=PollView(choices))

# ------------------- Valorant Stats Commands -------------------
@bot.command()
async def stats(ctx, *, username):
    """Get Valorant account stats. Usage: !stats NAME#TAG"""
    try:
        name, tag = username.split("#")
        region = "na"
        acc = get_account_details_by_name("v1", name=name, tag=tag)
        puuid = acc.puuid
        matches = get_match_history_by_puuid("v3", region=region, puuid=puuid, size=20)

        hs_shots = hs_total = 0
        for match in matches[:10]:
            if not hasattr(match, "players") or not hasattr(match.players, "all_players"):
                continue
            p = next((pl for pl in match.players.all_players if pl.puuid == puuid), None)
            if p and hasattr(p.stats, "headshots"):
                hs_shots += getattr(p.stats, "headshots", 0)
                hs_total += (
                    getattr(p.stats, "headshots", 0)
                    + getattr(p.stats, "bodyshots", 0)
                    + getattr(p.stats, "legshots", 0)
                )
        hs_percent = (hs_shots / hs_total * 100) if hs_total else 0

        k_sum = d_sum = 0
        for match in matches[:20]:
            if not hasattr(match, "players") or not hasattr(match.players, "all_players"):
                continue
            p = next((pl for pl in match.players.all_players if pl.puuid == puuid), None)
            if p:
                k_sum += getattr(p.stats, "kills", 0)
                d_sum += getattr(p.stats, "deaths", 0)
        kd = (k_sum / d_sum) if d_sum else 0

        wins = 0
        total = 0
        for match in matches[:20]:
            if not hasattr(match, "players") or not hasattr(match.players, "all_players"):
                continue
            p = next((pl for pl in match.players.all_players if pl.puuid == puuid), None)
            if not p:
                continue
            player_team = p.team.lower()
            team_obj = getattr(match.teams, player_team, None)
            if team_obj and getattr(team_obj, "has_won", False):
                wins += 1
            total += 1
        winrate = (wins / total * 100) if total else 0

        msg = (
            f"Account: **{acc.name}#{acc.tag}**\n"
            f"Level: {acc.account_level}\n"
            f"Headshot % (last 10): {hs_percent:.1f}%\n"
            f"K/D ratio (last 20): {kd:.2f}\n"
            f"Winrate (last 20): {winrate:.1f}%"
        )
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"Failed to fetch stats: {e}")

@bot.command()
async def matchlist(ctx, *, username):
    """Get last 5 matches. Usage: !matchlist NAME#TAG"""
    try:
        name, tag = username.split("#")
        region = "na"
        acc = get_account_details_by_name("v1", name=name, tag=tag)
        puuid = acc.puuid
        matches = get_match_history_by_puuid("v3", region=region, puuid=puuid, size=5)
        match_list = matches.data if hasattr(matches, "data") else matches
        lines = []
        for match in match_list:
            p = next((pl for pl in match.players.all_players if pl.puuid == puuid), None)
            if not p:
                continue
            team = p.team
            team_obj = getattr(match.teams, team.lower(), None)
            win = team_obj.has_won if team_obj else False
            kills = getattr(p.stats, "kills", 0)
            deaths = getattr(p.stats, "deaths", 0)
            assists = getattr(p.stats, "assists", 0)
            hs = getattr(p.stats, "headshots", 0)
            total_shots = hs + getattr(p.stats, "bodyshots", 0) + getattr(p.stats, "legshots", 0)
            hs_percent = (hs / total_shots * 100) if total_shots else 0
            lines.append(
                f"{match.metadata.map}: Agent {p.character} | {kills}/{deaths}/{assists} | HS%: {hs_percent:.1f}% | {'Won' if win else 'Lost'}"
            )
        await ctx.send("\n".join(lines) if lines else "No recent matches found.")
    except Exception as e:
        await ctx.send(f"Failed to fetch matchlist: {e}")

@bot.command()
async def mmr(ctx, *, username):
    """Get MMR details. Usage: !mmr NAME#TAG"""
    try:
        name, tag = username.split("#")
        region = "na"
        acc = get_account_details_by_name("v1", name=name, tag=tag)
        puuid = acc.puuid
        mmr = get_mmr_details_by_puuid("v2", region=region, puuid=puuid)
        if hasattr(mmr, "error") and mmr.error:
            await ctx.send(f"Failed to fetch MMR details: {mmr.error}")
            return
        name = getattr(mmr, "name", "Unknown")
        tag = getattr(mmr, "tag", "Unknown")
        current = getattr(mmr, "current_data", None)
        peak = getattr(mmr, "highest_rank", None)
        rank = getattr(current, "currenttierpatched", "Unknown") if current else "Unknown"
        rr = getattr(current, "ranking_in_tier", "N/A") if current else "N/A"
        elo = getattr(current, "elo", "N/A") if current else "N/A"
        mmr_change = getattr(current, "mmr_change_to_last_game", "N/A") if current else "N/A"
        peak_rank = getattr(peak, "patched_tier", "Unknown") if peak else "Unknown"
        peak_season = getattr(peak, "season", "N/A") if peak else "N/A"
        msg = (
            f"MMR for **{name}#{tag}**\n"
            f"Rank: {rank}\n"
            f"RR: {rr}\n"
            f"ELO: {elo}\n"
            f"MMR Change Last Game: {mmr_change}\n"
            f"Peak Rank: {peak_rank} (Season: {peak_season})"
        )
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"Failed to fetch MMR details: {e}")

@bot.command()
async def leaderboard(ctx, region="na"):
    """Get top 10 leaderboard. Usage: !leaderboard [region]"""
    try:
        lb = get_leaderboard("v2", region=region)
        players = getattr(lb, "players", []) or getattr(lb, "Players", [])
        msg = "**Top Leaderboard Players:**\n"
        for p in players[:10]:
            game_name = getattr(p, "gameName", getattr(p, "game_name", "Unknown"))
            tag_line = getattr(p, "tagLine", getattr(p, "tag_line", "???"))
            ranked_rating = getattr(p, "rankedRating", getattr(p, "ranked_rating", "N/A"))
            wins = getattr(p, "numberOfWins", getattr(p, "number_of_wins", "N/A"))
            rank = getattr(p, "leaderboardRank", getattr(p, "leaderboard_rank", "N/A"))
            msg += f"{rank}. {game_name}#{tag_line} - {ranked_rating} RR - {wins} Wins\n"
        await ctx.send(msg)
    except Exception as e:
        await ctx.send(f"Failed to fetch leaderboard: {e}")

# ------------------- About/Help Command -------------------
bot.remove_command("help")

@bot.command(name="about")
async def about(ctx):
    embed = discord.Embed(
        title="🤖 About Vantage",
        description=(
            "Welcome! Here are the main features and commands you can use:\n"
            "\n"
            "**Valorant Stats**\n"
            "`!stats NAME#TAG` — Get recent Valorant stats for a player (e.g. !stats 640509040147#htman).\n"
            "`!matchlist NAME#TAG` — List recent matches with basic stats.\n"
            "`!mmr NAME#TAG` — Show player's current and peak MMR.\n"
            "`!leaderboard [region]` — Show top 10 leaderboard players for a region (e.g. !leaderboard eu).\n"
            "\n"
            "**NBA Stats**\n"
            "`!gametoday` — Show today's NBA games and live scores with leaders.\n"
            "`!playerstats <player name>` — Show player career and current season stats (regular & playoffs).\n"
            "`!leagueleaders [STAT] [SEASON]` — Show top players for a stat this season (e.g. !leagueleaders PTS).\n"
            "`!roster <team name>` — Show the current roster for an NBA team (e.g. !roster lakers).\n"
            "`!standings [season] [season_type]` — Show NBA standings (e.g. !standings 2024-25 Regular Season).\n"
            "\n"
            "**Polls**\n"
            "`!poll question=\"Your Question\" choices=\"Option 1, Option 2, Option 3\"` — Create a poll with up to 5 options.\n"
            "\n"
            "**Game Scheduling**\n"
            "`!schedule @user1 @user2 2024-05-28 21:00` — Schedule a game and get a reminder 5 hours before.\n"
            "\n"
            "**Music**\n"
            "`!play <YouTube URL or search>` — Play a song in your current voice channel.\n"
            "`!skip` — Skip the current song.\n"
            "`!stop` — Stop music and disconnect the bot from voice chat.\n"
            "\n"
            "**Bot Info**\n"
            "`!about` — Show this help page.\n"
            "\n"
            "Type `!about` at any time to see this page again!\n"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Bot by Mochi. DM me @greenteamatcha with feature requests!")
    await ctx.send(embed=embed)

# ------------------- Bot Run -------------------
bot.run(token, log_handler=handler, log_level=logging.DEBUG)



