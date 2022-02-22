import re
from enum import Enum, auto

import discord


class State(Enum):
    REVIEW_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    CHOOSE_TYPE = auto()
    ADDITIONAL_REVIEW = auto()
    CHOOSE_CATEGORY = auto()
    GENERAL_CATEGORY = auto()
    SOMETHING_ELSE_CATEGORY = auto()
    CHOOSE_ACTIONS = auto()
    SUBMIT_REVIEW = auto()

    REVIEW_COMPLETE = auto()


class Review:
    START_KEYWORD = "review"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"

    def __init__(self, client):
        self.state = State.REVIEW_START
        self.client = client
        self.message = None
        self.message_under_review = None

    async def handle_message(self, message):
        '''
        This function makes up the meat of the moderator-side reviewing flow. It defines how we transition between states and what
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord.
        '''
        if message.content.lower() == self.CANCEL_KEYWORD:
            self.state = State.REVIEW_COMPLETE
            return ["Review cancelled."]

        if self.state == State.REVIEW_START:
            reply = "Thank you for starting the reviewing process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to review.\n"
            reply += "You can obtain this link by right-clicking the message and " \
                     "clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]

        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return [
                    "I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return [
                    "I cannot accept reviews of messages from guilds that I'm not in. " +
                    "Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return [
                    "It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
                self.message_under_review = message
            except discord.errors.NotFound:
                return [
                    "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            self.state = State.MESSAGE_IDENTIFIED
            # Here we've found the message - it's up to you to decide what to do next!

        if self.state == State.MESSAGE_IDENTIFIED:
            reply = "I found this message:" + "```" + message.author.name + ": " + message.content + "```"
            reply += "The message was reported by users and/or detected by our " \
                     "automated flagging mechanism for potentially violating platform " \
                     "policies. Please determine if it is valid.\n"
            # reply =  "What is wrong with this image?"
            reply += "Please select what is wrong with this message: `hate speech`, " \
                     "`other abuse type`, `non-violating`, `request additional review`."
            self.state = State.CHOOSE_TYPE
            return [reply]

        if self.state == State.CHOOSE_TYPE:
            if message.content.lower() == "hate speech":
                self.state = State.CHOOSE_CATEGORY
                return [
                    "Choose the category of hate speech: `race/ethinicity`, `religion`, "
                    "`gender identity`, `sexual orientation` and `something else`."]
            elif message.content.lower() == "non-violating":
                self.state = State.REVIEW_COMPLETE
                return ["You have marked the message as non-violating. No action will "
                        "be taken.\nReview complete."]
            elif message.content.lower() == "other abuse type":
                self.state = State.CHOOSE_ACTIONS
                reply = "Thank you for reviewing. Our team will review the message and " \
                        "take action, including disabling the account of the user " \
                        "if necessary.\nReview complete."
                self.state = State.REVIEW_COMPLETE
                return [reply]
            elif message.content.lower() == "request additional review":
                self.state = State.ADDITIONAL_REVIEW
                return ["Briefly describe your reason for seeking additional review."]
            else:
                return [
                    "Incorrect type. Please select from `hate speech`, `other abuse "
                    "type`, `non-violating`, `request additional review`."]

        if self.state == State.ADDITIONAL_REVIEW:
            reply = "The message will be forwarded along with your feedback for " \
                    "additional review. Thank you!"
            self.state = State.REVIEW_COMPLETE
            return [reply]

        if self.state == State.CHOOSE_CATEGORY:
            if message.content.lower() == "something else":
                self.state = State.SOMETHING_ELSE_CATEGORY
                return ["Briefly describe the problem."]
            elif message.content.lower() == "race/ethinicity" or \
                    message.content.lower() == "religion" or \
                    message.content.lower() == "gender identity" or \
                    message.content.lower() == "sexual orientation":
                self.state = State.SUBMIT_REVIEW
                reply = "Thank you for reviewing the message. Enter `delete` in order " \
                        "to delete the original message " \
                        "immediately and `continue` to let the platform take the " \
                        "necessary action."
                return [reply]
            else:
                return [
                    "Incorrect Category. Please select from `race/ethinicity`, "
                    "`religion`, `gender identity`, `sexual orientation` and "
                    "`something else`."]

        if self.state == State.SOMETHING_ELSE_CATEGORY:
            reply = "Thank you for describing the problem." \
                    "\nEnter `delete` in order to delete the original message " \
                    "immediately and `continue` to let the platform take the " \
                    "necessary action."
            self.state = State.SUBMIT_REVIEW
            return [reply]

        if self.state == State.SUBMIT_REVIEW:
            if message.content.lower() == "delete":
                await self.message_under_review.add_reaction("🚫")
                self.state = State.REVIEW_COMPLETE
                return ["Message successfully deleted.\nReview complete."]
            elif message.content.lower() == "continue":
                reply = "Thank you for reviewing. Our team will review the message and " \
                        "take action, including disabling the account of the user " \
                        "if necessary.\nReview complete."
                self.state = State.REVIEW_COMPLETE
                return [reply]
            else:
                return ["Incorrect selection. Please select from `delete` and `continue`"]

        return []

    def review_complete(self):
        return self.state == State.REVIEW_COMPLETE
