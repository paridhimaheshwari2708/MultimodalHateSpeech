import re
from collections import defaultdict
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
    AWAIT_NEXT_ACTION = auto()
    REVIEW_COMPLETE = auto()
    # CONTINUE_REVIEW = auto()


report_counters = defaultdict(int)


class Review:
    START_KEYWORD = "review"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    CONTINUE_KEYWORD = "yes"

    def __init__(self, client):
        self.state = State.REVIEW_START
        self.client = client
        self.message = None
        self.message_under_review = None
        self.current_report = None
        self.author_id = None

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

            if self.client.pending_reports.empty():
                return ["No reports to review at this time. Bye!"]

            self.current_report = self.client.pending_reports.queue[0].item
            message = self.current_report["Message Link"]
            self.state = State.AWAITING_MESSAGE

        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message)
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

            reply = "Thank you for starting the reviewing process. "
            reply += "Say `help` at any time for more information.\n"
            reply += f"Found {self.client.pending_reports.qsize()} pending reports.\n\n"
            reply += "This message was reported for violating our hate speech policies:\n"

            if message.content == self.current_report["Message"]:
                reply += f"Message: {message.content}\nMessage Link: {self.current_report['Message Link']}\n"

            else:
                reply += f"OriginalMessage: {self.current_report['Message']}\n"
                reply += f"Current Message: {message.content}\n"
                reply += f"Message Link:{self.current_report['Message Link']}\n"

            self.author_id = message.author.id

            embed = discord.Embed(title="Please tell us what is wrong with this message:",
                                  color=0x109319)
            embed.add_field(name="hate",
                            value="The message violates our platform's hate speech policies.",
                            inline=False)
            embed.add_field(name="other", value="The message does not constitute hate speech but violates \
                        our platform's policies for some other abuse type.", inline=False)
            embed.add_field(name="none", value="The message is non-violating.",
                            inline=False)
            embed.add_field(name="further",
                            value="You wish to request additional review for this message.",
                            inline=False)

            self.state = State.CHOOSE_TYPE
            return [{"content": reply, "embed": embed}]

        if self.state == State.CHOOSE_TYPE:
            if message.content.lower() == "hate":
                report_counters[self.author_id] += 1

                self.state = State.CHOOSE_CATEGORY
                reply = ""
                # TODO: Should this be an embed or as a description?
                embed = discord.Embed(
                    title="Select the category of hate speech:",
                    color=0x109319,
                    description="`race/ethinicity`, `religion`, `gender identity`, `sexual orientation` and `something else`."
                )
                return [{"content": reply, "embed": embed}]

            elif message.content.lower() == "none":
                reply = "You have marked the message as non-violating and hence, will not be removed from our platform.\
                \nThe reporter will be notified of our decision and may have the option to re-appeal.\nReview complete. Thank You!"
                reply = self.update_pending(reply)
                self.state = State.REVIEW_COMPLETE
                return [reply]

            elif message.content.lower() == "other":
                reply = "The message will be forwarded to the appropriate team for further action.\nReview complete. Thank You!"
                reply = self.update_pending(reply)
                self.state = State.REVIEW_COMPLETE
                return [reply]

            elif message.content.lower() == "further":
                self.state = State.ADDITIONAL_REVIEW
                return ["Briefly describe your reason for seeking additional review."]
            else:
                return [
                    "Unrecognised option. Please select from `hate`, `other`, "
                    "`none` or `further`."]

        if self.state == State.ADDITIONAL_REVIEW:
            reply = "The message will be forwarded along with your feedback for " \
                    "additional review. \nReview Complete. Thank you!"
            reply = self.update_pending(reply)
            self.state = State.REVIEW_COMPLETE
            return [reply]

        if self.state == State.CHOOSE_CATEGORY:
            if message.content.lower() == "something else":
                self.state = State.SUBMIT_REVIEW
                return ["Briefly describe the problem."]

            elif message.content.lower() == "race/ethinicity" or \
                    message.content.lower() == "religion" or \
                    message.content.lower() == "gender identity" or \
                    message.content.lower() == "sexual orientation":
                self.state = State.SUBMIT_REVIEW

            else:
                return [
                    "Unrecognised option. Please select from `race/ethinicity`, "
                    "`religion`, `gender identity`, `sexual orientation` and "
                    "`something else`."]

        # if self.state == State.SOMETHING_ELSE_CATEGORY:
        #     reply = "Thank you for describing the problem." \
        #             "\nEnter `delete` in order to delete the original message " \
        #             "immediately and `continue` to let the platform take the " \
        #             "necessary action."
        #     self.state = State.SUBMIT_REVIEW
        #     return [reply]

        if self.state == State.SUBMIT_REVIEW:
            await self.message_under_review.add_reaction("🚫")

            if report_counters[self.author_id] == 1:
                reply = "The reportee has been warned and the message has been taken " \
                        "down." \
                        "\nThe reportee may have the option to re-appeal."
            elif report_counters[self.author_id] <= 5:
                reply = "The reportee acccount has been temporarily disabled on the " \
                        "platform and the message has been taken down." \
                        "\nThe reportee may have the option to re-appeal."
            else:
                reply = "The reportee acccount has been permanently disabled due to " \
                        "continued violations and the message has been taken down." \
                        "\nThe reportee may have the option to re-appeal."

            reply += "\n\nReview Complete. Thank You!"
            reply = self.update_pending(reply)

            self.state = State.REVIEW_COMPLETE

            return [reply]

        return []

    def update_pending(self, reply):
        _ = self.client.pending_reports.get()
        if not self.client.pending_reports.empty():
            reply += f"\n\nDo you wish to continue reviewing the remaning {self.client.pending_reports.qsize()} reports?" \
                     "\nEnter `yes` to continue."
        else:
            reply += "\nNo more reports to review at this time. Bye!"
        return reply

    def review_complete(self):
        return self.state == State.REVIEW_COMPLETE
