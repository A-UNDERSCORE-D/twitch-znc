from __future__ import annotations
from typing import TYPE_CHECKING, Callable
import znc


class twitchznc(znc.Module):
    """
    Twitch capability handlers and other magic.

    This wont passthrough caps as that is a pain.
    But it will rewrite some cap messages to handle things better / actually
    show them in IRC.
    """
    description = 'Adds support for various twitch capabilities'
    module_types = [znc.CModInfo.NetworkModule]  # type: ignore

    def __init__(self) -> None:
        print('initing')
        self.avail_caps: list[str] = []
        self.caps = (
            'twitch.tv/membership',  # JOIN/PART for users
            'twitch.tv/tags',        # message tags for things
            'twitch.tv/commands',    # special commands for state stuff
        )

        self.handled_twitch_special_commands: dict[str, Callable[[CMessage], znc.ModRet]] = {
            'CLEARCHAT':        self.handle_clearchat,
            'CLEARMSG':         self.handle_clearmsg,
            'GLOBALUSERSTATE':  self.handle_globaluserstate,
            'ROOMSTATE':        self.handle_roomstate,
            'USERNOTICE':       self.handle_usernotice,
            'USERSTATE':        self.handle_userstate,
        }

    def OnServerCapAvailable(self, sCap: CString):
        ret = str(sCap).lower() in self.caps
        print(f'oncapavail {str(sCap)} {ret=}')
        # this is gross.
        if ret:
            self.avail_caps.append(str(sCap))

        return ret

    def OnIRCConnected(self):
        print("Connection complete; forcing CAP sends")
        for cap in self.avail_caps:
            self.PutIRC(f'CAP REQ :{cap}')
        return super().OnIRCConnected()

    def notice(self, source: str, target: str, message: str) -> None:
        self.PutUser(f':{source}!m@zncmodule NOTICE {target} :{message}')

    def handle_clearchat(self, msg: CMessage) -> znc.ModRet:
        """CLEARCHAT is a ban-like message. Redirect to a NOTICE"""

        duration = str(msg.GetTag('ban-duration'))
        channel = str(msg.GetParam(0))
        nick = str(msg.GetParam(1))

        message = f'{nick} was permanently banned'
        if duration != '':
            message = f'{nick} was banned for {duration} seconds'

        self.notice('bans', channel, message)

        return znc.HALTCORE

    def handle_clearmsg(self, msg: CMessage) -> znc.ModRet:
        """
        CLEARMSG deletes a single message

        Obviously I cant make a client delete a message (nor would I want to)
        but we can note that the message was deleted
        """
        message = str(msg.GetParam(1))
        channel = str(msg.GetParam(0))
        self.notice('deleted_msg', channel, message)
        return znc.HALTCORE

    def handle_globaluserstate(self, msg: CMessage) -> znc.ModRet:
        return znc.HALTCORE  # Nothing to really do here, I want to get it but dont want to deal with it

    def handle_roomstate(self, msg: CMessage) -> znc.ModRet:
        emote_only = str(msg.GetTag('emote-only')) == '1'
        try:
            followers_only = int(str(msg.GetTag('followers-only')))
        except ValueError:
            followers_only = -1

        r9k = str(msg.GetTag('r9k')) == '1'

        try:
            slow = int(str(msg.GetTag('slow')))
        except ValueError:
            slow = -1

        subs_only = str(msg.GetTag('subs-only')) == '1'

        message = []

        if emote_only:
            message.append('Emote Only')

        if followers_only == 0:
            message.append('Followers Only')

        elif followers_only != -1:
            if followers_only == 0:
                message.append('Followers only (All)')
            else:
                message.append(f'Followers Only (following for {followers_only} mins)')

        if r9k:
            message.append('R9K Mode (message > 9 chars must be unique)')

        if slow > 0:
            message.append(f'Slow mode ({slow}s)')

        if subs_only:
            message.append('Subscribers Only')

        channel = str(msg.GetParam(0))

        self.notice('room-state', channel, f'{", ".join(message)}')

        return znc.HALTCORE

    def handle_usernotice(self, msg: CMessage) -> znc.ModRet:
        type_ = str(msg.GetTag('msg-id'))
        if type_ == '':
            type_ = 'usernotice'

        system_msg = str(msg.GetTag('system-msg'))
        display_name = str(msg.GetTag('display-name'))
        if not display_name:
            display_name = str(msg.GetTag('login'))

        if not display_name:
            display_name = 'unknown'

        user_message = str(msg.GetParam(1))
        channel = str(msg.GetParam(0))

        self.notice(type_, channel, system_msg)
        if user_message:
            self.notice(type_, channel, user_message)

        return znc.HALTCORE

    def handle_userstate(self, msg: CMessage) -> znc.ModRet:
        return znc.HALTCORE  # Nothing really useful here

    def OnRawMessage(self, msg: CMessage):
        cmd = str(msg.GetCommand())
        print(f'Got a raw command: {cmd}')

        if cmd.upper() in self.handled_twitch_special_commands:
            return self.handled_twitch_special_commands[cmd.upper()](msg)

        return znc.CONTINUE


if TYPE_CHECKING:
    class CString:
        ...

    class CMessage:
        def GetCommand(self) -> CString: ...
        def GetTags(self): ...
        def GetTag(self, name: str) -> CString: ...
        def GetParam(self, idx: int) -> CString: ...
