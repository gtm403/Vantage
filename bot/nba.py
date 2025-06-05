from discord.ext import commands
import discord
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.endpoints import commonplayerinfo, leagueleaders, commonteamroster, playercareerstats, leaguestandings
from nba_api.stats.static import players, teams
from datetime import datetime
import pytz

class NBA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="gametoday")
    async def gametoday(self, ctx):
        """Show today's NBA games and live scores with leaders."""
        try:
            eastern = pytz.timezone('US/Eastern')
            now_est = datetime.now(eastern)
            date_str = now_est.strftime('%m/%d/%Y') 

            board = scoreboardv2.ScoreboardV2(game_date=date_str, league_id='00', day_offset=0)
            data = board.get_normalized_dict()
            game_headers = data['GameHeader']
            line_scores = data['LineScore']
            team_leaders = {tl['GAME_ID']: tl for tl in data.get('TeamLeaders', [])}

            if not game_headers:
                await ctx.send("No NBA games today.")
                return

            embed = discord.Embed(
                title=f"NBA Games Today ({date_str})",
                color=discord.Color.blue()
            )

            for game in game_headers:
                game_id = game['GAME_ID']
                status_text = game['GAME_STATUS_TEXT']
                home_team_id = game['HOME_TEAM_ID']
                away_team_id = game['VISITOR_TEAM_ID']

                # Find home and away team details
                home = next((ls for ls in line_scores if ls['GAME_ID'] == game_id and ls['TEAM_ID'] == home_team_id), None)
                away = next((ls for ls in line_scores if ls['GAME_ID'] == game_id and ls['TEAM_ID'] == away_team_id), None)

                if not home or not away:
                    continue  

                matchup = f"{away['TEAM_ABBREVIATION']} @ {home['TEAM_ABBREVIATION']}"
                matchup_detail = (
                    f"{away['TEAM_CITY_NAME']} {away['TEAM_NAME']} [{away['TEAM_WINS_LOSSES']}] @ "
                    f"{home['TEAM_CITY_NAME']} {home['TEAM_NAME']} [{home['TEAM_WINS_LOSSES']}]"
                )

                # Scores and status
                home_score = home['PTS'] if home['PTS'] is not None else 0
                away_score = away['PTS'] if away['PTS'] is not None else 0
                game_status = f"{status_text} | {away_score}-{home_score}"

                # Leaders
                leader = team_leaders.get(game_id, {})
                def get_leader(prefix):
                    name = leader.get(f"{prefix}_PLAYER_NAME")
                    pts = leader.get(f"{prefix}_PTS")
                    reb = leader.get(f"{prefix}_REB")
                    ast = leader.get(f"{prefix}_AST")
                    if name and pts is not None and reb is not None and ast is not None:
                        return f"{name} ({pts} PTS, {reb} REB, {ast} AST)"
                    return "N/A"

                home_leader = get_leader('HOME')
                away_leader = get_leader('AWAY')

                value = (
                    f"{matchup_detail}\n"
                    f"**Status:** {game_status}\n"
                    f"**Home Leader:** {home_leader}\n"
                    f"**Away Leader:** {away_leader}\n"
                )

                embed.add_field(
                    name=matchup,
                    value=value,
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Could not fetch games: {e}")



    @staticmethod
    def get_player_career_stats(player_id, season_type="Regular Season"):
        stats = playercareerstats.PlayerCareerStats(player_id=player_id, per_mode36="PerGame")
        data = stats.get_normalized_dict()
        if season_type.upper().startswith("PLAY"):
            group = "CareerTotalsPostSeason"
        else:
            group = "CareerTotalsRegularSeason"
        rows = data.get(group, [])
        if not rows:
            return None
        row = rows[0]
        return {
            "GP": row["GP"],
            "PPG": row["PTS"],
            "RPG": row["REB"],
            "APG": row["AST"],
            "FG%": row["FG_PCT"],
            "3P%": row["FG3_PCT"],
            "FT%": row["FT_PCT"],
            "MIN": row["MIN"],
        }
    
    @staticmethod
    def get_season_id():
        year = datetime.now().year
        prev = year - 1 if datetime.now().month < 10 else year
        return f"{prev}-{str(prev+1)[2:]}"
    
    @staticmethod
    def format_stats(row):
        if row is None:
            return "N/A"
        return (
            f"Games: {row['GP']} | MIN: {float(row['MIN']):.1f}\n"
            f"PPG: {float(row['PTS']):.1f} | RPG: {float(row['REB']):.1f} | APG: {float(row['AST']):.1f}\n"
            f"FG%: {float(row['FG_PCT'])*100:.1f} | 3P%: {float(row['FG3_PCT'])*100:.1f} | FT%: {float(row['FT_PCT'])*100:.1f}"
        )
    


    @commands.command(name="playerstats")
    async def playerstats(self, ctx, *, player_name):
        """Show both career and current season stats for regular and playoffs."""
        found_players = players.find_players_by_full_name(player_name)
        if not found_players:
            await ctx.send(f"Player '{player_name}' not found.")
            return
        player = found_players[0]
        pid = player['id']

        stats = playercareerstats.PlayerCareerStats(player_id=pid, per_mode36="PerGame")
        data = stats.get_normalized_dict()
        season_id = NBA.get_season_id()

        # Career regular season
        try:
            career_reg = data['CareerTotalsRegularSeason'][0]
        except Exception:
            career_reg = None

        # Current regular season
        try:
            import pandas as pd
            reg_seasons = pd.DataFrame(data['SeasonTotalsRegularSeason'])
            # Print for debugging
            # print(reg_seasons["SEASON_ID"].unique())
            curr_reg = reg_seasons[reg_seasons["SEASON_ID"].astype(str).str.contains(season_id.split("-")[0])]
            curr_reg = curr_reg.iloc[0] if not curr_reg.empty else None
        except Exception:
            curr_reg = None

        # Career playoffs
        try:
            career_po = data['CareerTotalsPostSeason'][0]
        except Exception:
            career_po = None

        # Current season playoffs
        try:
            po_seasons = pd.DataFrame(data['SeasonTotalsPostSeason'])
            curr_po = po_seasons[po_seasons["SEASON_ID"].astype(str).str.contains(season_id.split("-")[0])]
            curr_po = curr_po.iloc[0] if not curr_po.empty else None
        except Exception:
            curr_po = None

        # Player info
        info = commonplayerinfo.CommonPlayerInfo(player_id=pid)
        info_data = info.get_normalized_dict()
        player_info = info_data['CommonPlayerInfo'][0]

        desc = (
            f"**Team:** {player_info.get('TEAM_NAME','N/A')}\n"
            f"**Position:** {player_info.get('POSITION','N/A')}\n"
            f"**Height:** {player_info.get('HEIGHT','N/A')}\n"
            f"**Weight:** {player_info.get('WEIGHT','N/A')}\n"
            f"**Age:** {player_info.get('AGE','N/A')}\n\n"
        )

        desc += "**Career Regular Season:**\n" + NBA.format_stats(career_reg) + "\n\n"
        desc += f"**{season_id} Regular Season:**\n" + NBA.format_stats(curr_reg) + "\n\n"
        desc += "**Career Playoffs:**\n" + NBA.format_stats(career_po) + "\n\n"
        desc += f"**{season_id} Playoffs:**\n" + NBA.format_stats(curr_po)

        embed = discord.Embed(
            title=f"{player_info['DISPLAY_FIRST_LAST']} Stats",
            description=desc,
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)


    @commands.command(name="leagueleaders")
    async def leagueleaders_(self, ctx, stat="PTS", season=None):
        from datetime import datetime

        SUPPORTED_STATS = [
            "PTS", "REB", "AST", "STL", "BLK", "EFF",
            "MIN", "FGM", "FGA", "FG3M", "FG3A",
            "FTM", "FTA", "OREB", "DREB", "TOV",
            "FG_PCT", "FG3_PCT", "FT_PCT"
        ]
        stat = stat.upper()
        if stat not in SUPPORTED_STATS:
            await ctx.send(f"Stat not supported. Try: {', '.join(SUPPORTED_STATS)}")
            return

        if not season:
            year = datetime.now().year
            prev = year - 1 if datetime.now().month < 10 else year
            season = f"{prev}-{str(prev+1)[2:]}"

        try:
            leaders = leagueleaders.LeagueLeaders(
                league_id="00",
                season=season,
                per_mode48="PerGame",
                stat_category_abbreviation=stat,
                scope="S",
                season_type_all_star="Regular Season"
            )
            df = leaders.get_data_frames()[0]

            if df.empty:
                await ctx.send("No data found.")
                return

            desc = ""
            for _, row in df.head(10).iterrows():
                value = row[stat]
                if isinstance(value, float) and stat.endswith("_PCT"):
                    value = f"{value*100:.1f}%"
                desc += f"#{int(row['RANK'])} {row['PLAYER']} ({row['TEAM']}) — {value}\n"

            embed = discord.Embed(
                title=f"NBA {stat} Leaders ({season})",
                description=desc,
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}")

    @commands.command(name="roster")
    async def roster(self, ctx, *, team_name):
        """Show current roster for an NBA team. Example: !roster lakers"""
        tlist = teams.find_teams_by_full_name(team_name)
        if not tlist:
            await ctx.send(f"Team '{team_name}' not found.")
            return
        team = tlist[0]
        team_id = team['id']
        year = datetime.now().year
        prev = year - 1 if datetime.now().month < 10 else year
        season = f"{prev}-{str(prev+1)[2:]}"

        try:
            roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=season)
            df = roster.get_data_frames()[0]
            desc = ""
            for _, row in df.iterrows():
                desc += f"{row['PLAYER']} | #{row['NUM']} | {row['POSITION']} | {row['HEIGHT']} | {row['WEIGHT']} lbs | Age: {row['AGE']}\n"
        except Exception:
            desc = "Could not fetch roster."
        embed = discord.Embed(
            title=f"{team['full_name']} Roster ({season})",
            description=desc or "No data found.",
            color=discord.Color.dark_blue()
        )
        await ctx.send(embed=embed)

    @commands.command(name="standings")
    async def standings(self, ctx, season="2024-25", season_type="Regular Season"):
        """
        Shows NBA standings.
        Usage: !standings [season] [season_type]
        season_type: "Regular Season" or "Playoffs"
        """
        try:
            resp = leaguestandings.LeagueStandings(
                league_id="00",
                season=season,
                season_type=season_type
            )
            df = resp.get_data_frames()[0]

            east = df[df['Conference'] == 'East'].sort_values('PlayoffRank').head(8)
            west = df[df['Conference'] == 'West'].sort_values('PlayoffRank').head(8)

            def fmt(conf, teams):
                out = f"**{conf}**\n"
                for _, row in teams.iterrows():
                    out += f"`{row['PlayoffRank']}.` {row['TeamCity']} {row['TeamName']} ({row['WINS']}-{row['LOSSES']})\n"
                return out

            embed = discord.Embed(
                title=f"NBA Standings ({season}, {season_type})",
                description=f"{fmt('East', east)}\n{fmt('West', west)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Could not fetch standings: {e}")

async def setup(bot):
    await bot.add_cog(NBA(bot))
