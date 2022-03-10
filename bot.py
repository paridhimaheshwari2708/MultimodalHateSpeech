# bot.py
import json
import logging
import os
import re
from enum import Enum, auto
from queue import PriorityQueue
import discord
import requests
from unidecode import unidecode
from textblob import TextBlob

from report import Report
from review import Review

from Classification.inference import HatefulMemesInference

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'token.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f'{token_path} not found!')

with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_key = tokens['perspective']


class Mode(Enum):
    REPORT = auto()
    REVIEW = auto()


class ModBot(discord.Client):
    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {}  # Map from guild to the mod channel id for that guild
        self.mod_channel = None
        self.reports = {}  # Map from user IDs to the state of their report
        self.reviews = {}
        self.perspective_key = key
        self.mode = None
        self.pending_reports = PriorityQueue()
        self.message_report_map = {} # Map message link to the reports

        # Loading inference model
        self.model = HatefulMemesInference('Classification')

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
                    self.mod_channel = channel

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs).
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel.
        '''
        # Ignore messages from us
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply = "Use the `report/review` command to begin the reporting/reviewing process.\n"
            reply += "Use the `cancel` command to cancel the report/review process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        if self.mode == Mode.REPORT or message.content.startswith(Report.START_KEYWORD):
            # Only respond to messages if they're part of a reporting flow
            # if author_id not in self.reports:
            #     return
            self.mode = Mode.REPORT

            # If we don't currently have an active report for this user, add one
            if author_id not in self.reports:
                self.reports[author_id] = \
                    Report(self, mod_channel=self.mod_channel)

            # Let the report class handle this message; forward all the messages it returns to uss
            responses = await self.reports[author_id].handle_message(message)
            for r in responses:
                if isinstance(r, dict):
                    await message.channel.send(r["content"], embed = r["embed"])
                else:
                    await message.channel.send(r)
                   

            # If the report is complete or cancelled, remove it from our map
            if self.reports[author_id].report_complete():
                self.mode = None
                self.reports.pop(author_id)

        elif self.mode == Mode.REVIEW or message.content.startswith(Review.START_KEYWORD):
            self.mode = Mode.REVIEW
            if author_id in self.reviews and \
                    self.reviews[author_id].awaiting_next_action():
                self.reviews[author_id].set_review_complete()
                self.reviews.pop(author_id)
                if not message.content.startswith(Review.CONTINUE_KEYWORD):
                    self.mode = None
                    await message.channel.send("Review stopped")
                    return
            if author_id not in self.reviews:
                self.reviews[author_id] = Review(self, mod_channel=self.mod_channel)

            reviews = await self.reviews[author_id].handle_message(message)
            for r in reviews:
                if isinstance(r, dict):
                    await message.channel.send(r["content"], embed = r["embed"])
                else:
                    await message.channel.send(r)

            if self.reviews[author_id].is_review_complete():
                self.mode = None
                self.reviews.pop(author_id)

        else:
            return

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        try:
            if not message.channel.name == f'group-{self.group_num}':
                return
        except:
            return

        # Forward the message to the mod channel
        mod_channel = self.mod_channels[message.guild.id]
        # await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')

        scores = self.eval_text(message)
        sorted_scores = {
            k: v for k, v in sorted(scores.items(), key=lambda item: item[1], reverse=True)}
        
        # TODO: Severe toxicity is only for demo
        auto_report_labels = ["SEVERE_TOXICITY", "IDENTITY_ATTACK", "THREAT"]
        thresh = 0.8
        hate_meme_thresh = 0.5
        send_report = False
        for label in auto_report_labels:
            if scores.get(label, 0) > thresh:
                send_report = True

        if scores.get("HATEFUL_MEME_SCORE", 0) > hate_meme_thresh:
            send_report = True

        if send_report:
            Report.add_report(self, message, message.jump_url)
            await mod_channel.send(
                f"Message flagged by automated detection: {message.jump_url}\
                                ```Message: {message.content}```")
            await mod_channel.send(self.code_format(json.dumps(sorted_scores, indent=2)))

    async def on_raw_message_edit(self, payload):
        channel = self.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        await self.handle_channel_message(message)

    def eval_text(self, message):
        '''
        Given a message, forwards the message to Perspective and returns a dictionary of scores.
        '''
        PERSPECTIVE_URL = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze'
        url = PERSPECTIVE_URL + '?key=' + self.perspective_key

        corrected_message = None
        scores = {}
        if message.content:
            # Decode the message if it includes unicode characters
            decoded_message = unidecode(message.content)
            textBlb = TextBlob(decoded_message)
            corrected_message = str(textBlb.correct())
            data_dict = {
                'comment': {'text': corrected_message},
                'languages': ['en'],
                'requestedAttributes': {
                    'SEVERE_TOXICITY': {}, 'PROFANITY': {},
                    'IDENTITY_ATTACK': {}, 'THREAT': {},
                    'TOXICITY': {}, 'FLIRTATION': {}
                },
                'doNotStore': True
            }
            response = requests.post(url, data=json.dumps(data_dict))
            response_dict = response.json()

            for attr in response_dict["attributeScores"]:
                scores[attr] = response_dict["attributeScores"][attr]["summaryScore"]["value"]

        if message.attachments:
            image_url = message.attachments[0].url
            hateful_meme_score = self.model.infer(image_url, corrected_message)
            scores['HATEFUL_MEME_SCORE'] = hateful_meme_score
        
        return scores

    def code_format(self, text):
        return "```" + text + "```"


client = ModBot(perspective_key)
client.run(discord_token)
