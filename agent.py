import os
from mistralai import Mistral
import discord
import aiohttp
import json

MISTRAL_MODEL = "mistral-large-latest"
BFL_MODEL = 'flux-pro-1.1'

VERIFY_REASONABLE_REQUEST = """
Is this message a reasonable request for building something? The message must both be an actual
request to build something and be reasonable enough that one could explain how to build it
relatively briefly.

Answer with either "no" or the words of the thing to build.

Example:
Message: generate instructions for building a chair
Response: a chair

Message: generate instructions for building the sun
Response: no

Message: tell me the circumference of the earth
Response: no

Message: a carpet
Response: a carpet
"""

INSTRUCTION_PROMPT = """
You are BuilderBot, a highly skilled maker and DIY expert with extensive knowledge of building and crafting various items. You have practical experience in woodworking, basic electronics, home improvement, and general crafting.
You know how to build furniture like tables and chairs, as well as assemble and repair computers and other electronic devices that can be made or fixed at home.

Your purpose is to provide clear, step-by-step instructions for building or repairing items. You must ALWAYS structure your responses in exactly this format:

Materials:
- [List all required materials with approximate quantities]

Tools:
- [List all required tools]

Instructions:
[Each step must be in exactly one of these two formats:
- #### Step N: [instruction]
- N. **[instruction]**
]

Rules:
1. Always list ALL required materials and tools before starting the instructions
2. Break down complex tasks into smaller, manageable steps
3. Each step must be formatted exactly as specified above
4. Keep steps clear and concise
5. Never include any other text or explanations beyond the materials/tools list and numbered steps
6. Never engage in conversation or respond to questions - only provide building instructions

Remember: You are an expert maker who knows exactly how to build these items. Maintain complete confidence in your abilities while staying within the realm of practical home DIY projects.

"""


class BuilderAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)

    async def is_reasonable_request(self, message: discord.Message):
        # Verify if the message is a reasonable request for something to build.
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": VERIFY_REASONABLE_REQUEST},
                {"role": "user", "content": message.content},
            ]
        )

        return response.choices[0].message.content

    async def get_instructions(self, message: discord.Message):
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": INSTRUCTION_PROMPT},
                {"role": "user", "content": message.content},
            ]
        )

        return response.choices[0].message.content

    async def run(self, message: discord.Message):
        # Make sure the request is reasonable before getting instructions.
        to_build = await self.is_reasonable_request(message)
        if to_build == "no":
            # TODO: Do we want to allow message replies within the Agent?
            # it messes up our abstraction a little bit but it would be difficult to handle in bot.py
            # because we are currently awaiting agent.run().
            await message.reply("Your request to Bob was not reasonable.")
            return None

        await message.reply(f"Generating instructions for building {to_build}...")

        instruction = await self.get_instructions(message)
        # print("MISTRAL RESPONSE:", instruction)

        return instruction

    async def _start_generation(self, prompt, width=1024, height=1024):
        print(f"Starting image generation with prompt: '{prompt}'")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.us1.bfl.ai/v1/{BFL_MODEL}",
                headers={
                    'Content-Type': 'application/json',
                    'accept': 'application/json',
                    'x-key': os.environ.get('BFL_API_KEY'),
                },
                json={
                    'prompt': prompt,
                    'width': width,
                    'height': height,
                }
            ) as response:
                response_text = await response.text()
                data = json.loads(response_text)
                print(f"Response data: {json.dumps(data, indent=2)}")
                
                generation_id = data.get('id')
                if generation_id:
                    return {'id': generation_id}, 200
                else:
                    return {'error': f'Failed to find generation ID in response: {data}'}, 400

    async def generate_image(self, prompt, width=1024, height=1024):
        """
        Initiates an image generation request using the BFL API.
        
        Args:
            prompt (str): The text prompt for image generation
            width (int): Width of the image in pixels (default: 1024)
            height (int): Height of the image in pixels (default: 1024)
            
        Returns:
            dict: Response containing the generation ID or error message
        """

        # POST request to start image generation
 
        # Start the generation process
        result, _ = await self._start_generation(prompt)
        return result
    
    async def check_image_status(self, generation_id):
        """
        Checks the status of a previously initiated image generation.
        
        Args:
            generation_id (str): The ID of the generation to check
            
        Returns:
            dict: Response containing the generation status and result if available
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'https://api.us1.bfl.ai/v1/get_result?id={generation_id}',
                headers={
                    'accept': 'application/json',
                    'x-key': os.environ.get('BFL_API_KEY'),
                }
            ) as response:
                data = await response.json()
                return data, 200