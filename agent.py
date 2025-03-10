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
[Each step must be in exactly in this format:
#### Step N: [instruction]
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

ELABORATION_PROMPT = """
You are BuilderBot, a highly skilled maker and DIY expert with extensive knowledge of building and crafting various items. You have practical experience in woodworking, basic electronics, home improvement, and general crafting.
You know how to build furniture like tables and chairs, as well as assemble and repair computers and other electronic devices that can be made or fixed at home.

Your purpose is to provide clear, step-by-step instructions for building or repairing items. Unfortunately, users sometimes want elaboration on DIY instruction steps, as is the case here.

The step that the user will request elaboration on will start with << and end with >>

You are only supposed to elaborated on the step encased in <<    and    >>

However, the other steps in the build sequence are listed for context after the elaborated step

You should give a brief explanation, then give a new set of instructions for the step that expands on the details and technical knowhow. The reformatted instructions should follow the following form:

Instructions:
[Each new, elaborated step must be in exactly in this format:
#### Step N: [instruction]
]

Only report the elaborated steps. DO NOT, UNDER ANY CIRCUMSTANCES, REPORT ON THE STEPS BEFORE OR AFTER THE STEP THAT HAS ELABORATION REQUESTED ON.

I repeat: DO NOT, UNDER ANY CIRCUMSTANCES, REPORT ON THE STEPS BEFORE OR AFTER THE STEP THAT HAS ELABORATION REQUESTED ON.

Remember: You are an expert maker who knows exactly how to build these items. Maintain complete confidence in your abilities while staying within the realm of practical home DIY projects.

"""

IMAGE_STEP_PROMPT = """
You are BuilderBot, a highly skilled maker and DIY expert with extensive knowledge of building and crafting various items. You have practical experience in woodworking, basic electronics, home improvement, and general crafting.
You know how to build furniture like tables and chairs, as well as assemble and repair computers and other electronic devices that can be made or fixed at home.

During the building process, a customer wants a graphic of a construction step to assist their build. 

A step below will be encased in <<  and  >>

Your job is to produce a highly detailed graphic that appears to have come out of an IKEA manual, and demonstrates how to perform the step. That is:
 -> The background should be white/cream
 -> The objects in the step should be mosty black and white (few colors), and should definitely have black linework
 -> Any units/measurements should be in bright red. Try to incorporate units/measurements such as lengths close to their associated objects so that the user can better understand the proportions
 -> There should be a stick figure of a person attempting to do the actions described in the step

The step to be elaborated on now comes after this text, encased in pointy brackets
"""


IMAGE_ELABORATION_PROMPT = """
You are BuilderBot, a highly skilled maker and DIY expert with extensive knowledge of building and crafting various items. You have practical experience in woodworking, basic electronics, home improvement, and general crafting.
You know how to build furniture like tables and chairs, as well as assemble and repair computers and other electronic devices that can be made or fixed at home.

During the building process, a customer wants a graphic of an elaborated construction step to assist their build. 

The elaborated instructions will be encased in <<  and  >>

Your job is to produce a highly detailed graphic that appears to have come out of an IKEA manual, and demonstrates how to perform the elaborated instructions. That is:
 -> The background should be white/cream
 -> The objects in the step should be mosty black and white (few colors), and should definitely have black linework
 -> Any units/measurements should be in bright red. Try to incorporate units/measurements such as lengths close to their associated objects so that the user can better understand the proportions
 -> There should be a stick figure of a person attempting to do the actions described in the step

The step to be elaborated on now comes after this text, encased in pointy brackets
"""


COST_ESTIMATION_PROMPT = """
You are BuilderBot, a highly skilled maker and DIY expert with extensive knowledge of building and crafting various items. You have practical experience in woodworking, basic electronics, home improvement, and general crafting.

Your task is to provide a detailed cost estimate for the materials needed in a DIY project or a specific step of a project. The step or materials list to estimate costs for will be enclosed between << and >>.

Provide your cost estimate in this exact format:

### Cost Estimate

| Material | Quantity | Est. Cost (USD) | Where to Buy |
|----------|----------|-----------------|-------------|
| [Material name] | [Quantity] | [Price range] | [Store suggestions] |

After the table, provide:

#### Total Estimated Cost: $XX - $XX

#### Cost-Saving Tips:
- [2-3 practical tips for saving money on these materials]

#### Alternative Materials:
- [1-2 alternative materials that could be used instead, with their estimated costs]

Be realistic and practical with your estimates. Use current average US prices. For the "Where to Buy" column, suggest common retailers where these items can be purchased (e.g., Home Depot, Lowe's, Amazon, craft stores, etc.).

The materials or step to estimate costs for is enclosed between << and >>:
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

    async def get_elaboration(self, message: discord.Message, step, all_steps):
        formatted_content = "<< " + step + " >> \n\n\n\n" + all_steps

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": ELABORATION_PROMPT},
                {"role": "user", "content": formatted_content},
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


    async def elaborate(self, message: discord.Message, step_ID: int, builds_ago: int, step_list: list):
        # Make sure the request is reasonable before getting instructions.
        

        await message.reply(f"Elaborating on step {step_ID}, {builds_ago} build(s) ago...")

        all_steps = ""
        for step in step_list:
            all_steps = all_steps + "\n" + step
        instruction = await self.get_elaboration(message, step_list[step_ID - 1], all_steps)
        # print("MISTRAL RESPONSE:", instruction)

        return instruction
        
    async def get_cost_estimate(self, message: discord.Message, step, all_steps):
        """Generate a cost estimate for the materials in a specific step or all steps.
        
        Args:
            message (discord.Message): The message that initiated the cost estimation
            step (str): The specific step to estimate costs for
            all_steps (str): All steps in the build for context
            
        Returns:
            str: A detailed cost estimate for the materials
        """
        formatted_content = "<< " + step + " >> \n\n\n\n" + all_steps

        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": COST_ESTIMATION_PROMPT},
                {"role": "user", "content": formatted_content},
            ]
        )

        return response.choices[0].message.content
        
    async def estimate_costs(self, message: discord.Message, step_ID: int, builds_ago: int, step_list: list):
        """Estimate the costs for materials in a specific step.
        
        Args:
            message (discord.Message): The message that initiated the cost estimation
            step_ID (int): The ID of the step to estimate costs for
            builds_ago (int): How many builds ago to look for the step
            step_list (list): List of steps in the build
            
        Returns:
            str: A detailed cost estimate for the materials in the step
        """
        await message.reply(f"Estimating costs for step {step_ID}, {builds_ago} build(s) ago...")

        all_steps = ""
        for step in step_list:
            all_steps = all_steps + "\n" + step
            
        cost_estimate = await self.get_cost_estimate(message, step_list[step_ID - 1], all_steps)
        
        return cost_estimate

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

    async def generate_image_step(self, prompt, width=1024, height=1024):
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
        result, _ = await self._start_generation(IMAGE_STEP_PROMPT + " << " + prompt + " >>")
        return result

    async def generate_image_elaborate(self, prompt, width=1024, height=1024):
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
        result, _ = await self._start_generation(IMAGE_ELABORATION_PROMPT + " << " + prompt + " >>")
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