import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio

class GameScheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = [] 
        self.check_sessions.start()

    @commands.command()
    async def schedule(self, ctx, *, argstr: str):
        """
        Schedule a game session. Usage: !schedule @user1 @user2 2024-05-28 21:00
        """
        
        await ctx.send(f"Debug: received {argstr}")
        party = list(ctx.message.mentions)
        
        tokens = argstr.split()
        date_str = " ".join(t for t in tokens if not t.startswith('<@'))
        try:
            session_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except Exception:
            await ctx.send("Invalid date/time format. Use YYYY-MM-DD HH:MM (24h)")
            return

        if ctx.author not in party:
            party.append(ctx.author)

        self.sessions.append({
            'time': session_time,
            'party': party,
            'reminded': False,
            'channel_id': ctx.channel.id
        })
        names = ", ".join(u.mention for u in party)
        await ctx.send(f"Scheduled game session for {names} at {session_time}!")

    @tasks.loop(minutes=1)
    async def check_sessions(self):
        now = datetime.now()
        for session in self.sessions:
            if not session['reminded']:
                reminder_time = session['time'] - timedelta(hours=5)
                # Allow a few minutes drift
                if reminder_time <= now < reminder_time + timedelta(minutes=2):
                    # Ping party
                    channel = self.bot.get_channel(session['channel_id'])
                    if channel:
                        mentions = " ".join(u.mention for u in session['party'])
                        await channel.send(
                            f"⏰ {mentions} - Reminder: Game session in 5 hours at {session['time'].strftime('%Y-%m-%d %H:%M')}!"
                        )
                    session['reminded'] = True

    @check_sessions.before_loop
    async def before_check_sessions(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(GameScheduler(bot))
