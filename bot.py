import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import json

# Configuration for yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.current = {}
        self.text_channels = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        return self.queue[guild_id]

    @app_commands.command(name="play", description="Play music from YouTube")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play music from YouTube"""
        await interaction.response.defer()
        
        voice_client = interaction.guild.voice_client
        self.text_channels[interaction.guild.id] = interaction.channel

        if not voice_client:
            if interaction.user.voice:
                voice_client = await interaction.user.voice.channel.connect()
            else:
                return await interaction.followup.send("Cadê tu?")

        if interaction.user.voice.channel != voice_client.channel:
            return await interaction.followup.send("Vem K!")

        try:
            data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ytdl.extract_info(query, download=False)
            )
            
            if 'entries' in data:
                data = data['entries'][0]
            
            song = {
                'title': data['title'],
                'url': data['url'],
                'requester': interaction.user
            }
            
            self.get_queue(interaction.guild.id).append(song)
            
            if not voice_client.is_playing():
                await interaction.followup.send(f"Certo!")
                await self.play_next(interaction.guild.id)
            else:
                await interaction.followup.send(f"Adicionado: **{song['title']}**")
                
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)}")

    async def play_next(self, guild_id):
        guild = self.bot.get_guild(guild_id)
        queue = self.get_queue(guild_id)
        
        if len(queue) > 0:
            next_song = queue.pop(0)
            self.current[guild_id] = next_song
            source = discord.FFmpegPCMAudio(next_song['url'], **ffmpeg_options)
            guild.voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next(guild_id)))
            
            channel = self.text_channels.get(guild_id)
            if channel:
                await channel.send(f"Tocando: **{next_song['title']}** (requested by {next_song['requester'].mention})")
        else:
            self.current.pop(guild_id, None)
            if guild.voice_client:
                await guild.voice_client.disconnect()
                channel = self.text_channels.get(guild_id)
                if channel:
                    await channel.send("Acabou, até!")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        voice_client = interaction.guild.voice_client
        self.text_channels[interaction.guild.id] = interaction.channel
        
        if voice_client and voice_client.is_playing():
            await interaction.response.send_message("Musica pulada!")
            await self.play_next(interaction.guild.id)
        else:
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)

    @app_commands.command(name="stop", description="Stop the bot and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        """Stop the bot and clear the queue"""
        self.get_queue(interaction.guild.id).clear()
        self.text_channels[interaction.guild.id] = interaction.channel
        
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("Tá.")
        else:
            await interaction.response.send_message("Num to nem aí.", ephemeral=True)

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        """Show the current queue"""
        queue = self.get_queue(interaction.guild.id)
        voice_client = interaction.guild.voice_client
        
        if len(queue) == 0 and (not voice_client or not voice_client.is_playing()):
            return await interaction.response.send_message("Queue vazio!", ephemeral=True)
        
        current = self.current.get(interaction.guild.id, None)
        queue_list = [f"1. **{current['title']}** (Now Playing)"] if current else []
        queue_list += [f"{i+2}. {song['title']}" for i, song in enumerate(queue)]
        
        await interaction.response.send_message("\n".join(queue_list))

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        """Pause the current song"""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Pausado.")
        else:
            await interaction.response.send_message("Não tem nada tocando!", ephemeral=True)

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        """Resume the paused song"""
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Resumido.")
        else:
            await interaction.response.send_message("Mas a música já tá tocando!", ephemeral=True)

    @app_commands.command(name="join", description="Join the voice channel")
    async def join(self, interaction: discord.Interaction):
        """Join the voice channel"""
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
            await interaction.response.send_message(f"Entrei {interaction.user.voice.channel.mention}")
        else:
            await interaction.response.send_message("Cadê tu?", ephemeral=True)

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        """Leave the voice channel"""
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("Bye.")
        else:
            await interaction.response.send_message("Num to nem aí!", ephemeral=True)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix=".g ",
    intents=intents,
    description='A music bot with slash commands'
)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.add_cog(MusicBot(bot))
    await bot.tree.sync()
    print("Slash commands synced")

try:
    with open("config.json") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print("Config file config.json not found!")
    exit(1)

if __name__ == "__main__":
    bot.run(config['token'])
