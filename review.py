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

abuse_cat = {"1": "hate", "2": "other", "3": "none", "4": "further"}
hate_cat = {"1": "race", "2": "religion", "3": "gender identity", "4": "sexual orientation", "5": "something else"}

class Review:
    START_KEYWORD = "review"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    CONTINUE_KEYWORD = "yes"

    def __init__(self, client, mod_channel):
        self.state = State.REVIEW_START
        self.client = client
        self.message = None
        self.message_under_review = None
        self.current_report = None
        self.author_id = None
        self.mod_channel = mod_channel

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

            message = self.client.pending_reports.queue[0].item
            self.current_report = self.client.message_report_map[message]
            # message = self.current_report["Message Link"]
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
            reply += f"This message was reported for violating our hate speech policies {self.current_report['nreports']} time(s):\n"

            if message.content == self.current_report["Message"]:
                reply += f"`Message`: {message.content}\n`Message Link`: " \
                         f"{self.current_report['Message Link']}\n`Additional Info`:\n" \
                         f"\t{self.current_report['Additional Info']}"

            else:
                reply += f"OriginalMessage: {self.current_report['Message']}\n"
                reply += f"Current Message: {message.content}\n"
                reply += f"Message Link:{self.current_report['Message Link']}\n"

            self.author_id = message.author.id

            embed = discord.Embed(title="Please tell us what is wrong with this message:",
                                  color=0x109319)
            embed.add_field(name="(1) hate",
                            value="The message violates our platform's hate speech policies.",
                            inline=False)
            embed.add_field(name="(2) other", value="The message does not constitute hate speech but violates \
                        our platform's policies for some other abuse type.", inline=False)
            embed.add_field(name="(3) none", value="The message is non-violating.",
                            inline=False)
            embed.add_field(name="(4) further",
                            value="You wish to request additional review for this message.",
                            inline=False)
            embed.set_footer(text="Example: To report the message for hate speech, type `hate` or `1`.")

            self.state = State.CHOOSE_TYPE
            return [{"content": reply, "embed": embed}]

        if self.state == State.CHOOSE_TYPE:
            if message.content.isdigit():
                message.content = abuse_cat[message.content]

            if message.content.lower() == "hate":
                report_counters[self.author_id] += 1

                self.state = State.CHOOSE_CATEGORY
                reply = ""
                # TODO: Should this be an embed or as a description?
                embed = discord.Embed(
                    title="What category of harmful speech does the message fall under?",
                    color=0x109319,
                    description="`(1) race`, `(2) religion`, `(3) gender identity`, `(4) sexual orientation` and `something else`."
                )
                
                embed.set_footer(text="Example: To select race, type `race` or `1`.")
                return [{"content": reply, "embed": embed}]

            elif message.content.lower() == "none":
                reply = "You have marked the message as non-violating and hence, will not be removed from our platform.\
                \nThe reporter will be notified of our decision and may have the option to re-appeal.\nReview complete. Thank You!"
                reply = self.update_pending(reply)
                # self.state = State.REVIEW_COMPLETE
                return [reply]

            elif message.content.lower() == "other":
                reply = "The message will be forwarded to the appropriate team for " \
                        "further action.\nReview complete. Thank You!"
                reply = self.update_pending(reply)
                # self.state = State.REVIEW_COMPLETE
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
                    "additional review.\nReview Complete. Thank you!"
            reply = self.update_pending(reply)
            # self.state = State.REVIEW_COMPLETE
            return [reply]

        if self.state == State.CHOOSE_CATEGORY:
            if message.content.isdigit():
                message.content = hate_cat[message.content]

            if message.content.lower() == "something else":
                self.state = State.SUBMIT_REVIEW
                return ["Briefly describe the problem."]

            elif message.content.lower() == "race" or \
                    message.content.lower() == "religion" or \
                    message.content.lower() == "gender identity" or \
                    message.content.lower() == "sexual orientation":
                self.state = State.SUBMIT_REVIEW

            else:
                return [
                    "Unrecognised option. Please select from `race`, "
                    "`religion`, `gender identity`, `sexual orientation` and "
                    "`something else`."]

        if self.state == State.SUBMIT_REVIEW:
            await self.message_under_review.add_reaction("🚫")
            orig_message_author = self.message_under_review.author.name

            if report_counters[self.author_id] == 1:
                reply = "Thank you for reviewing. %s has been warned and the message " \
                        "%s has been taken " \
                        "down." \
                        "\n%s may have the option to re-appeal." \
                        % (orig_message_author, self.current_report['Message Link'],
                           orig_message_author)
                reply_to_author = "Violating message: %s\nYou are being warned for " \
                                  "violating the platform " \
                                  "policies and your message has been taken down. You " \
                                  "have the option to re-appeal."\
                                  % self.current_report['Message Link']
                reply_to_reporter = "We reviewed your report for the message %s and " \
                                    "found it violating our platform policies. The " \
                                    "message has been taken down and %s has been " \
                                    "warned." \
                                    % (self.current_report['Message Link'],
                                       orig_message_author)
            elif report_counters[self.author_id] <= 5:
                reply = "Thank you for reviewing. %s's acccount has been temporarily " \
                        "disabled on the " \
                        "platform and the message %s has been taken down." \
                        "\n%s may have the option to re-appeal." \
                        % (orig_message_author, self.current_report['Message Link'],
                           orig_message_author)
                reply_to_author = "Violating message: %s\nYour account has been " \
                                  "temporarily disabled for " \
                                  "violating the platform " \
                                  "policies and your message has been taken down. You " \
                                  "have the option to re-appeal." \
                                  % self.current_report['Message Link']
                reply_to_reporter = "We reviewed your report for the message %s and " \
                                    "found it violating our platform policies. The " \
                                    "message has been taken down and %s's account has " \
                                    "been temporarily disabled." \
                                    % (self.current_report['Message Link'],
                                       orig_message_author)
            else:
                reply = "Thank you for reviewing. %s's acccount has been permanently " \
                        "disabled due to " \
                        "continued violations and the message %s has been taken down." \
                        "\n%s may have the option to re-appeal." \
                        % (orig_message_author, self.current_report['Message Link'],
                           orig_message_author)
                reply_to_author = "Violating message: %s\nYour account has been " \
                                  "permanently disabled for " \
                                  "repeated violations of the platform " \
                                  "policies and your message has been taken down. You " \
                                  "have the option to re-appeal." \
                                  % self.current_report['Message Link']
                reply_to_reporter = "We reviewed your report for the message %s and " \
                                    "found it violating our platform policies. The " \
                                    "message has been taken down and %s's account has " \
                                    "been permanently disabled for repeated " \
                                    "violations.." \
                                    % (self.current_report['Message Link'],
                                       orig_message_author)
            await self.mod_channel.send(reply)
            await self.message_under_review.author.send(reply_to_author)
            for reporter in self.current_report["Reporters"]:
                await reporter.send(reply_to_reporter)

            reply += "\n\nReview Complete."
            reply = self.update_pending(reply)

            # self.state = State.REVIEW_COMPLETE
            # self.state = State.AWAIT_NEXT_ACTION
            return [reply]

        return []

    def update_pending(self, reply):
        # Remove this message from the queue and the message-report map
        curr_message_link = self.client.pending_reports.get()
        self.client.message_report_map.pop(curr_message_link.item)

        if not self.client.pending_reports.empty():
            reply += f"\n\nDo you wish to continue reviewing the remaning" \
                     f" {self.client.pending_reports.qsize()} reports?" \
                     "\nEnter `yes` to continue."
            self.state = State.AWAIT_NEXT_ACTION
        else:
            reply += "\nNo more reports to review at this time. Bye!"
            self.state = State.REVIEW_COMPLETE
        return reply

    def awaiting_next_action(self):
        return self.state == State.AWAIT_NEXT_ACTION

    def set_review_complete(self):
        self.state = State.REVIEW_COMPLETE

    def is_review_complete(self):
        return self.state == State.REVIEW_COMPLETE
