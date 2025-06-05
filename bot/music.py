import discord
from discord.ext import commands
import wavelink

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}

    async def ensure_voice(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Join a voice channel first!")
            return None
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        elif vc.channel != ctx.author.voice.channel:
            await vc.move_to(ctx.author.voice.channel)
        return vc

    @commands.command(name="play")
    async def play(self, ctx, *, search: str):
        vc = await self.ensure_voice(ctx)
        if not vc:
            return
        
        tracks = await wavelink.Playable.search(search)
        if not tracks:
            await ctx.send("No results found!")
            return
        track = tracks[0] if isinstance(tracks, list) else tracks
        guild_id = ctx.guild.id
        q = self.queue.setdefault(guild_id, [])
        if not vc.playing:
            await vc.play(track)
            await ctx.send(f"Now playing: {track.title}")
        else:
            q.append(track)
            await ctx.send(f"Added to queue: {track.title}")

    @commands.command(name="skip")
    async def skip(self, ctx):
        """Skip the current song and play the next in queue (if any)."""
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.playing:
            await ctx.send("Not playing anything.")
            return

        guild_id = ctx.guild.id
        q = self.queue.get(guild_id, [])
        if q:
            next_track = q.pop(0)
            await vc.stop()
            await vc.play(next_track)
            await ctx.send(f"Skipped! Now playing: {next_track.title}")
        else:
            await vc.stop()
            await ctx.send("Skipped! No more songs in the queue.")


    @commands.command(name="stop")
    async def stop(self, ctx):
        """Stop music and disconnect."""
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            await ctx.send("Not connected to a voice channel.")
            return

        await vc.disconnect()
        await ctx.send("Stopped and disconnected.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Play next song in queue, if any."""
        player = payload.player
        guild_id = player.guild.id
        q = self.queue.get(guild_id, [])
        if q:
            next_track = q.pop(0)
            await player.play(next_track)
            channel = discord.utils.get(player.guild.text_channels, name="general")
            if channel:
                await channel.send(f"Now playing: {next_track.title}")

async def setup(bot):
    await bot.add_cog(Music(bot))
