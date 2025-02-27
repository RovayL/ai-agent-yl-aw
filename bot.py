import os
import discord
import logging
import asyncio
import time

from discord.ext import commands
from dotenv import load_dotenv
from agent import BuilderAgent

# ylitchev: import the following so that regular expressions can be compiled and evaluated
import re

PREFIX = "!"

# Setup logging
logger = logging.getLogger("discord")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
agent = BuilderAgent()


# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")


# Helpful function for coloring text (ylitchev: DOES NOT WORK, ATTEMPTING TO DEBUG)
def color_text(text, color_code):
    return f"\033[{color_code}m{text}\033[0m"

# Bolds numbers followed by imperial/metric units and dimensions like 1x4 in the given text.
def bold_units_and_dimensions(text):
    pattern = re.compile(
        # r'(\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:inches|inch|in|feet|foot|ft|yards|yd|miles|mile|mi|centimeters|cm|meters|m|kilometers|km)\b|\b\d+x\d+\b)',
        r'(\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:-|)(?:inches|inch|in|feet|foot|ft|yards|yd|miles|mile|mi|centimeters|cm|meters|m|kilometers|km)\b|\b\d+x\d+\b)',
        flags=re.IGNORECASE
    )
    return pattern.sub(r'**\1**', text)


# Splits the text into sections starting with headers (####).
# Each section includes the header and content until the next header.
def split_into_sections(text):
    lines = text.split('\n')
    sections = []
    current_section = []
    step_pattern = re.compile(r'^(#### Step \d+: |\d+\. \*\*[^*]+?\*\*)')
    
    for line in lines:
        if line.startswith('#### ') or step_pattern.match(line):
            if current_section:
                sections.append('\n'.join(current_section))
                current_section = []
            current_section.append(line)
        else:
            current_section.append(line)
    if current_section:
        sections.append('\n'.join(current_section))
    return sections


# ylitchev: overkill function that guarantees that messages sent to discord are less than
#           2000 characters and that it does not break up a word
def partition_string(text, max_chunk_size=1995):
    """
    Partitions a string into chunks, maximizing chunk length up to a limit,
    and only breaking at spaces.

    Args:
        text: The input string.
        max_chunk_size: The maximum size of each chunk.

    Returns:
        A list of string chunks.  Returns an empty list if the input
        string is empty or None.
    """

    if not text: # Check for empty or None input
        return []

    partitions = []
    current_chunk = ""
    words = text.split(" ")  # Split the string into words

    for word in words:
        potential_chunk = current_chunk + (word if not current_chunk else " " + word) # Add a space if it is not the first word
        if len(potential_chunk) <= max_chunk_size:
            current_chunk = potential_chunk
        else:
            partitions.append(current_chunk)
            current_chunk = word  # Start a new chunk with the current word

    if current_chunk:  # Add the last chunk if it's not empty
        partitions.append(current_chunk)

    return partitions

async def generate_and_show_image(message: discord.Message, prompt: str):
    """ 
    Uses agent to generate an image. Waits until the image is ready. Then renders it in the channel.

    Args:
        message (discord.Message): The message that initiated the image generation
        prompt (str): The text prompt for image generation

    Returns:
        None
    """
    # Send initial response
    status_message = await message.reply(f"Starting image generation for: '{prompt}'...")

    # Start the image generation process
    generation_result = await agent.generate_image(prompt)

    if 'error' in generation_result:
        await status_message.edit(content=f"Error starting image generation: {generation_result['error']}")
        return

    generation_id = generation_result['id']
    await status_message.edit(content=f"Image generation in progress (ID: {generation_id})...")

    start_time = time.time()
    max_wait_time = 30 

    while time.time() - start_time < max_wait_time:
        status_result, status_code = await agent.check_image_status(generation_id)
        print(f"Status check result: {status_result}")
        if status_result.get('status', '') == 'Ready':
            embed = discord.Embed(title="Generated Image")
            embed.set_image(url=status_result['result']['sample'])
            await message.channel.send(embed=embed)
            await status_message.edit(content=f"Image generation complete!")
            return

        await asyncio.sleep(1)

    await status_message.edit(content="Image generation timed out. Please try again later.")
    return

@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    logger.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots.
    if (
        message.author == bot.user
        or message.author.bot
        or message.content.startswith("!")
        or not (message.content.startswith("Bob, please build me") or message.content.startswith("Make me a picture"))
    ):
        return
    
    # TODO: Improve the logic/interface of when to generate an image. Probably want to integrate with Bob, so its
    # not just when someone asks "Make me a picture"
    if message.content.startswith("Make me a picture"):
        # Extract the prompt from the message
        prompt = message.content.replace("Make me a picture", "").strip()
        if not prompt:
            prompt = "A beautiful landscape"  # Default prompt if none provided
        await generate_and_show_image(message, prompt)
        return

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Process the message with the agent you wrote
    # Open up the agent.py file to customize the agent
    logger.info(f"Processing message from {message.author}: {message.content}")
    response = await agent.run(message)

    # If response is None, the request was not reasonable.
    if response is None:
        return

    print("MESSAGE RESPONSE: ", response)

    # Send the response back to the channel
    # await message.reply(response)
    # test = color_text("Hello there", "1;32m")
    
    # response = response + test

    # Bold units and dimensions
    processed_response = bold_units_and_dimensions(response)

    # Split into sections
    sections = split_into_sections(processed_response)

    # Collect steps (#### Step N: ...)
    steps_list = []
    # step_pattern = re.compile(r'^#### Step \d+: ')
    step_pattern = re.compile(r'^(#### Step \d+: |\d+\. \*\*[^*]+?\*\*)')
    for section in sections:
        lines = section.split('\n')
        if lines and step_pattern.match(lines[0]):
            steps_list.append(section)

    # Send each section as a separate reply
    for section in sections:
        if section.strip():  # Avoid empty messages
            section_with_newline = section;
            partitioned_text = partition_string(section_with_newline)
            for partition in partitioned_text:
                await message.reply(partition)
            
            # await message.reply(section_with_newline)
    
    # await message.reply(response)
    


# Commands


# This example command is here to show you how to add commands to the bot.
# Run !ping with any number of arguments to see the command in action.
# Feel free to delete this if your project will not need commands.
@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")


# Start the bot, connecting it to the gateway
bot.run(token)
