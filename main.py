import discord
from discord.ext import commands, tasks
import asyncio
from discord import PCMVolumeTransformer, FFmpegPCMAudio
from datetime import datetime, timezone, timedelta

TOKEN = 'Token bot'  # Bot Token
GUILD_ID = 'Server id '  # Server id
CHANNEL_ID = 'id canal voice '  # channel id ( Voice)
RADIO_URL = 'Mp3 Radio'  # URL de la station de radio

intents = discord.Intents.default()
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

last_state = {"members": 0, "playing": False}
last_left_time = None

async def connect_to_channel():
    try:
        guild_id = int(GUILD_ID.strip())
        channel_id = int(CHANNEL_ID.strip())
    except ValueError as e:
        print(f"Invalid guild or channel ID: {e}")
        return None

    guild = bot.get_guild(guild_id)
    if guild is None:
        print("Guild not found.")
        return None

    channel = guild.get_channel(channel_id)
    if channel and isinstance(channel, discord.VoiceChannel):
        if channel.permissions_for(guild.me).connect and channel.permissions_for(guild.me).speak:
            try:
                voice_client = await channel.connect(reconnect=True)
                await guild.change_voice_state(channel=channel, self_deaf=True)  # Deafen the bot
                print(f"Connected to voice channel: {channel.name}")
                return voice_client
            except Exception as e:
                print(f"Failed to connect to voice channel: {e}")
                return None
        else:
            print("Bot does not have permission to connect to or speak in the channel.")
            return None
    else:
        print("Channel is not a voice channel, or CHANNEL_ID not provided.")
        return None

async def play_radio(voice_client: discord.VoiceClient):
    try:
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }
        source = FFmpegPCMAudio(RADIO_URL, **ffmpeg_options)
        if not voice_client.is_connected():
            print("Voice client is not connected. Cannot play radio.")
            return

        if not voice_client.is_playing():
            print("Starting to play radio.")
            voice_client.play(PCMVolumeTransformer(source))
            await bot.change_presence(
                status=discord.Status.dnd, 
                activity=discord.Activity(type=discord.ActivityType.listening, name="Maher Al Meaqli 🎧")
            )
        while voice_client.is_playing() or voice_client.is_paused():
            await asyncio.sleep(1)
        print("Radio playback finished.")
    except discord.ClientException as e:
        print(f"Client exception occurred: {e}")
        await asyncio.sleep(5)
    except Exception as e:
        print(f"Error playing radio URL: {e}")
        await asyncio.sleep(5)

async def stop_radio(voice_client: discord.VoiceClient):
    if voice_client.is_playing():
        voice_client.stop()
        await bot.change_presence(status=discord.Status.online, activity=None)
        print("Radio stopped.")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await bot.change_presence(status=discord.Status.online)
    voice_client = await connect_to_channel()
    if voice_client:
        await play_radio(voice_client)
    monitor_channel.start()
    check_inactivity.start()

@bot.event
async def on_voice_state_update(member, before, after):
    global last_left_time
    if member == bot.user:
        return  # Ignore bot's own voice state updates

    guild = bot.get_guild(int(GUILD_ID))
    channel = guild.get_channel(int(CHANNEL_ID))
    voice_client = guild.voice_client if guild else None

    # Check if the user joined the specific channel where the bot is playing the radio
    if after.channel and after.channel.id == channel.id:
        print(f"{member.name} a rejoint le canal vocal.")
        if voice_client and not voice_client.is_playing():
            await play_radio(voice_client)
        await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.listening, name="Maher Al Meaqli 🎧"))
        last_left_time = None  # Reset the last left time

    # Check if the user left the specific channel where the bot is playing the radio
    if before.channel and before.channel.id == channel.id:
        print(f"{member.name} a quitté le canal vocal.")
        members = before.channel.members
        if len(members) == 1 and members[0] == bot.user:
            print("La radio a été arrêtée car il n'y a plus de membres dans le canal vocal.")
            if voice_client:
                await stop_radio(voice_client)
            last_left_time = datetime.now(timezone.utc)

@tasks.loop(seconds=5)
async def monitor_channel():
    global last_state
    guild = bot.get_guild(int(GUILD_ID))
    voice_client = guild.voice_client if guild else None
    channel = guild.get_channel(int(CHANNEL_ID))

    current_state = {
        "members": len(channel.members) if channel else 0,
        "playing": voice_client.is_playing() if voice_client else False
    }

    if current_state != last_state:
        if voice_client is None:
            print("Voice client not found, reconnecting...")
            voice_client = await connect_to_channel()
        
        if voice_client and channel and current_state["members"] > 1:
            if not current_state["playing"]:
                print("Radio stopped unexpectedly, restarting...")
                await play_radio(voice_client)
        elif voice_client and (channel is None or current_state["members"] <= 1):
            print("No members in the channel, stopping radio.")
            await stop_radio(voice_client)
        
        last_state = current_state

@tasks.loop(minutes=5)
async def check_inactivity():
    global last_left_time
    if last_left_time and datetime.now(timezone.utc) - last_left_time >= timedelta(hours=12):
        print("Déconnexion après 12 heures d'inactivité.")
        guild = bot.get_guild(int(GUILD_ID))
        voice_client = guild.voice_client if guild else None
        if voice_client:
            await voice_client.disconnect(force=True)
        voice_client = await connect_to_channel()
        if voice_client:
            await play_radio(voice_client)
        last_left_time = None  # Reset the last left time after reconnecting

@bot.command(name='new')
async def new(ctx):
    voice_client = await connect_to_channel()
    if voice_client:
        if not voice_client.is_playing():
            await play_radio(voice_client)
            await ctx.send("La radio a commencé à jouer.")
        else:
            await ctx.send("La radio est déjà en cours de lecture.")
    else:
        await ctx.send("Impossible de se connecter au canal vocal.")

bot.run(TOKEN)
