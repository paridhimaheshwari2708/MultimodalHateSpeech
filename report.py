import re
# Source: Wrapper around dict, inspired by https://docs.python.org/3/library/queue.html#queue.PriorityQueue
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import discord


@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any = field(compare=False)


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


expansions = {"spam": "spam", "hate": "hate speech",
              "harmful": "violence/harmful behavior", "misinfo": "misinformation"}

abuse_cat = {"1": "spam", "2": "hate", "3": "harmful", "4": "misinfo", "5": "other"}
hate_cat = {"1": "race", "2": "religion", "3": "gender identity",
            "4": "sexual orientation", "5": "something else"}
action_cat = {"1": "block", "2": "limit content", "3": "skip"}


def actions_embed():
    embed = discord.Embed(
        title="You can further choose to take the following actions to protect yourself:",
        color=0x109319)

    embed.add_field(name="(1) block",
                value="Block this user.",
                inline=False)
    embed.add_field(name="(2) limit content",
                    value="Restrict content from this user.",
                    inline=False)
    embed.add_field(name="(3) skip",
                    value="If you do not wish to take any direct action against this user.",
                    inline=False)

    embed.set_footer(text="Example: To block the user, type `block` or `1`.")

    return embed

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
        self.additional_info = None

    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        self.message = message
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
                return [
                    "I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
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
                reported_message = await channel.fetch_message(int(m.group(3)))
                self.reported_message = reported_message
                message = reported_message
                
            except discord.errors.NotFound:
                return [
                    "It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]
            self.state = State.MESSAGE_IDENTIFIED

        if self.state == State.MESSAGE_IDENTIFIED:
            reply = "I found this message:" + "```" + message.author.name + ": " + message.content + "```"

            embed = discord.Embed(title="Please tell us what is wrong with this message:",
                                  color=0x109319)
            embed.add_field(name="(1) spam",
                            value="The message is unwanted and/or repeated.",
                            inline=False)
            embed.add_field(name="(2) hate",
                            value="The message constitutes hate speech targeting a person or group.",
                            inline=False)
            embed.add_field(name="(3) harmful",
                            value="The message incites violence and/or promotes harmful behavior.",
                            inline=False)
            embed.add_field(name="(4) misinfo",
                            value="The message aims at spreading/promoting incorrect information.",
                            inline=False)
            embed.add_field(name="(5) other",
                            value="None of the above. I wish to describe the issue myself.",
                            inline=False)

            embed.set_footer(
                text="Example: To report the message for hate speech, type `hate` or `2`.")

            if message.attachments:
                embed.set_image(url=message.attachments[0])

            self.state = State.CHOOSE_TYPE
            return [{"content": reply, "embed": embed}]

        if self.state == State.CHOOSE_TYPE:
            if message.content.isdigit():
                message.content = abuse_cat[message.content]
            if message.content.lower() in ["spam", "harmful", "misinfo"]:
                # or abuse_cat[message.content] in ["spam", "harmful", "misinfo"]:

                self.state = State.SUBMIT_REPORT
                reply = "You have reported this message for " + (expansions[
                    message.content.lower()]) + "."
                reply += "\nPlease review documents for support and Discord's platform " \
                         "policies " \
                         "at https://support.discord.com/hc/en-us/categories" \
                         "/115000168351."
                # reply += "\nYou can further choose to : `skip`, `block` and `limit content`."
                embed = Report.actions_embed()
                return [{"content": reply, "embed": embed}]

            elif message.content.lower() == "hate":
                self.state = State.CHOOSE_CATEGORY
                reply = ""
                embed = Report.hate_cat_embed()
                return [{"content": reply, "embed": embed}]

            elif message.content.lower() == "other":
                self.state = State.SOMETHING_ELSE_CATEGORY
                return ["Briefly describe the problem."]

            else:
                return [
                    "Unrecognised option. Please select from `spam`, `hate`, `harmful`, `misinfo`, or `other`."]

        if self.state == State.CHOOSE_CATEGORY:

            if message.content.isdigit():
                message.content = hate_cat[message.content]

            if message.content.lower() == "something else":
                self.state = State.SOMETHING_ELSE_CATEGORY
                return ["Briefly describe the problem."]

            elif message.content.lower() == "race" or \
                    message.content.lower() == "religion" or \
                    message.content.lower() == "gender identity" or \
                    message.content.lower() == "sexual orientation":

                self.state = State.SUBMIT_REPORT
                reply = "You have reported this message for violating our hate speech policy for " + message.content + "."

                # TODO: Add documents here.
                reply += "\nPlease review documents for support and Discord's platform " \
                         "policies " \
                         "at https://support.discord.com/hc/en-us/categories" \
                         "/115000168351."
                embed = Report.actions_embed()
                return [{"content": reply, "embed": embed}]

            else:
                return [
                    "Unrecognised option. Please select from `race`, `religion`, `gender identity`, `sexual orientation` and `something else`."]

        if self.state == State.SOMETHING_ELSE_CATEGORY:
            self.additional_info = message.content
            reply = "Thank you for describing the problem."
            reply += "\nPlease review documents for support and Discord's platform " \
                     "policies " \
                     "at https://support.discord.com/hc/en-us/categories" \
                     "/115000168351."
            embed = Report.actions_embed()
            self.state = State.SUBMIT_REPORT
            return [{"content": reply, "embed": embed}]

        if self.state == State.SUBMIT_REPORT:
            reply = ""
            mod_channel_msg = "Report submitted for: %s\n```Message: %s```\n" \
                              % (self.reported_message_link,
                                 self.reported_message.content)

            if message.content.isdigit():
                message.content = action_cat[message.content]
            if message.content.lower() == "skip":
                mod_channel_msg += "%s has chosen not to take any direct action " \
                                   "against %s" \
                                   % (message.author.name,
                                      self.reported_message.author.name)
                reply += "You have chosen not to taken any direct action against %s." \
                         % self.reported_message.author.name
                await self.reported_message.add_reaction("⏭")
            elif message.content.lower() == "block":
                mod_channel_msg += "%s has chosen to block %s" \
                                   % (message.author.name,
                                      self.reported_message.author.name)
                reply += "You have chosen to block %s." \
                         % self.reported_message.author.name
                await self.reported_message.add_reaction("⛔")
            elif message.content.lower() == "limit content":
                mod_channel_msg += "%s has chosen to block %s" \
                                   % (message.author.name,
                                      self.reported_message.author.name)
                reply += "You have chosen to limit content from %s." \
                         % self.reported_message.author.name
                await self.reported_message.add_reaction("⚠")
            else:
                return ["Unrecognised option. Please select from `skip`, `block` and "
                        "`limit content`"]
            await self.mod_channel.send(mod_channel_msg)

            Report.add_report(
                client=self.client,
                reported_message=self.reported_message,
                reported_message_link=self.reported_message_link,
                reporter=self.message.author,
                additional_info=self.additional_info
            )
            reply += "\nReport complete. Thank you!"
            self.state = State.REPORT_COMPLETE
            return [reply]

        return []

    
    def report_complete(self):
        return self.state == State.REPORT_COMPLETE

    @classmethod
    def add_report(cls, client, reported_message, reported_message_link,
                   reporter=None, additional_info=None):

        if reported_message_link in client.message_report_map:
            client.message_report_map[reported_message_link]["nreports"] += 1
            if reporter and reporter not in \
                    client.message_report_map[reported_message_link]["Reporters"]:
                client.message_report_map[reported_message_link]["Reporters"].append(
                    reporter)
            if additional_info:
                if client.message_report_map[reported_message_link]["Additional Info"]:
                    client.message_report_map[reported_message_link][
                        "Additional Info"] += "\n\t" + additional_info
                else:
                    client.message_report_map[reported_message_link][
                        "Additional Info"] = additional_info

        else:
            scores = client.eval_text(reported_message)
            sorted_scores = [v for k, v in
                             sorted(scores.items(), key=lambda item: item[1],
                                    reverse=True)]
            key = sorted_scores[0]

            value = {"Message": reported_message.content,
                     "Message Link": reported_message_link,
                     "Additional Info": additional_info,
                     "nreports": 1}
            if reporter:
                value["Reporters"] = [reporter]
            else:
                value["Reporters"] = []
            if reported_message.attachments:
                value["Attachment"] = reported_message.attachments[0]
            client.message_report_map[reported_message_link] = value

            client.pending_reports.put(PrioritizedItem(-key, reported_message_link))

    @classmethod
    def hate_cat_embed(cls):
        embed = discord.Embed(
            title="What category of hate speech does the message fall under?",
            color=0x109319,
        )

        embed.add_field(name="(1) race",
                    value="The message is targeted at specific races/ethnicities.",
                    inline=False)
        embed.add_field(name="(2) religion",
                        value="The message is targeted at specific religions or religious communities.",
                        inline=False)
        embed.add_field(name="(3) gender identity",
                        value="The message is targeted at specific gender identities.",
                        inline=False)
        embed.add_field(name="(4) sexual orientation",
                        value="The message is targeted at specific sexual orientations",
                        inline=False)
        embed.add_field(name="(5) something else",
                        value="None of the above. I wish to describe the issue myself.",
                        inline=False)

        embed.set_footer(text="Example: To select race, type `race` or `1`.")

        return embed

    @classmethod
    def actions_embed(cls):
        embed = discord.Embed(
            title="You can further choose to take the following actions to protect yourself:",
            color=0x109319)

        embed.add_field(name="(1) block",
                    value="Block this user.",
                    inline=False)
        embed.add_field(name="(2) limit content",
                        value="Restrict content from this user.",
                        inline=False)
        embed.add_field(name="(3) skip",
                        value="If you do not wish to take any direct action against this user.",
                        inline=False)

        embed.set_footer(text="Example: To block the user, type `block` or `1`.")

        return embed
    