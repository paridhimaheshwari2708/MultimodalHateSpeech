import re
from enum import Enum, auto

import discord


class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    CHOOSE_TYPE = auto()
    CHOOSE_CATEGORY = auto()
    GENERAL_CATEGORY = auto()
    SOMETHING_ELSE_CATEGORY = auto()
    CHOOSE_ACTIONS = auto()
    SUBMIT_REPORT = auto()

    REPORT_COMPLETE = auto()


class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"

    def __init__(self, client, mod_channel):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
        self.mod_channel = mod_channel
        self.reported_message_link = None
        self.reported_message = None

    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content.lower() == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]

        if self.state == State.REPORT_START:
            reply = "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]

        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return [
                    "I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return [
                    "It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                self.reported_message_link = message.content
                message = await channel.fetch_message(int(m.group(3)))
                self.reported_message = message
            except discord.errors.NotFound:
                return [
                    "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            self.state = State.MESSAGE_IDENTIFIED
            # Here we've found the message - it's up to you to decide what to do next!

        if self.state == State.MESSAGE_IDENTIFIED:
            reply = "I found this message:" + "```" + message.author.name + ": " + message.content + "```"
            # reply =  "What is wrong with this image?"
            reply += "Please select what is wrong with this message: `spam`, `violence/harmful behavior`, `hate speech`, `misinformation`."
            self.state = State.CHOOSE_TYPE
            return [reply]

        if self.state == State.CHOOSE_TYPE:
            if message.content.lower() == "spam" or \
                    message.content.lower() == "violence/harmful behavior" or \
                    message.content.lower() == "misinformation":
                self.state = State.CHOOSE_ACTIONS
                reply = "You have reported this message for " + message.content + "\n"
                reply += "Please review these documents for support on hate speech and our platform policies."
                reply += "Choose action: `receive notifications`, `block` and `limit content`."
                return [reply]
            elif message.content.lower() == "hate speech":
                self.state = State.CHOOSE_CATEGORY
                return [
                    "Choose the category of hate speech: `race/ethinicity`, `religion`, `gender identity`, `sexual orientation` and `something else`."]
            else:
                return [
                    "Incorrect type. Please select from `spam`, `violence/harmful behavior`, `hate speech`, `misinformation`."]

        if self.state == State.CHOOSE_CATEGORY:
            if message.content.lower() == "something else":
                self.state = State.SOMETHING_ELSE_CATEGORY
                return ["Briefly describe the problem."]
            elif message.content.lower() == "race/ethinicity" or \
                    message.content.lower() == "religion" or \
                    message.content.lower() == "gender identity" or \
                    message.content.lower() == "sexual orientation":
                self.state = State.SUBMIT_REPORT
                reply = "You have reported this message for " + message.content + "\n"
                reply += "Please review these documents for support on " + message.content + " and our platform policies."
                reply += "Choose action: `receive notifications`, `block` and `limit content`."
                return [reply]
            else:
                return [
                    "Incorrect Category. Please select from `race/ethinicity`, `religion`, `gender identity`, `sexual orientation` and `something else`."]

        if self.state == State.SOMETHING_ELSE_CATEGORY:
            reply = "Thank you for describing the problem."
            reply += "Please review these documents for support on hate speech and our platform policies."
            reply += "Choose action: `receive notifications`, `block` and `limit content`."
            self.state = State.SUBMIT_REPORT
            return [reply]

        if self.state == State.SUBMIT_REPORT:
            if message.content.lower() in ["receive notifications", "block", "limit content"]:
                reply = "Thank you for reporting. Our team will review the message and take action, including disabling the account of the user if necessary."
                mod_channel = self.mod_channel
                await mod_channel.send("Report submitted for: %s\n\n```Message: %s"
                                       " author: %s```" %
                                       (self.reported_message_link,
                                        self.reported_message.content,
                                        self.reported_message.author.name))
                self.state = State.REPORT_COMPLETE
                return [reply]
            else:
                return ["Incorrect selection. Please select from `receive notifications`,"
                        " `block` and `limit content`"]

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
