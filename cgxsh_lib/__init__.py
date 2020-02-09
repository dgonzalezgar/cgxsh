#!/usr/bin/env python
# CloudGeniX SH (CGXSH). Websocket based shell/toolkit/generic utilities.
# Meant to perform similarly to Secure Shell (ssh), but via cloud service and in python.
#

__version__ = "1.0.0b1"
__author__ = "Aaron Edwards <cgxsh@ebob9.com>"
__email__ = "cgxsh@ebob9.com"

import argparse
import asyncio
import os
import signal
import sys
import cmd
import threading
import warnings
import pathlib
import yaml
import logging
import time
import tabulate
from getpass import getpass
# from logging_tree import printout  # used to debug logger issues, not required for project.

from .getch import getch
from .defaults import DEFAULT_YAML_WITH_COMMENTS, DEFAULT_CONTROL_CHAR_DICT
from .file_crypto import check_get_file, read_encrypted_file, write_encrypted_file, create_config_file, \
    CONFIG_DIR, CONFIG_YAML

import cloudgenix
from cloudgenix import websockets
from websockets.__main__ import print_during_input, print_over_input

# Set logging basics
cgxsh_logger = logging.getLogger(__name__)

# ignore fuzzywuzzy parser message. Speedup is not significant for this use case.
warnings.filterwarnings("ignore", message="Using slow pure-python SequenceMatcher. Install python-Levenshtein to "
                                          "remove this warning")
from fuzzywuzzy import process

ESCAPE_CHAR = '\N{INFORMATION SEPARATOR THREE}'

ELEMENTS_ID2N = {}
ELEMENTS_N2ID = {}
CLIENT_N2ID = {}
CLIENT_CANONICAL_N2ID = {}
CLIENT_ID2R = {}
OPERATORS_ID2N = {}

CONNECTING_ELEMENT_ID = {}

LOADED_CONFIG = {}

SDKDEBUG_LEVEL = 0
CGXSH_VERBOSITY_LEVEL = 0

jdout = cloudgenix.jdout
jd = cloudgenix.jd

# Chars at end of toolkit prompt
TOOLKIT_PROMPT_READY = "#\x1b[0m  \x08"

# Get AUTH_TOKEN/X_AUTH_TOKEN from env variable, if it exists. X_AUTH_TOKEN takes priority.
if "X_AUTH_TOKEN" in os.environ:
    CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
elif "AUTH_TOKEN" in os.environ:
    CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
else:
    # not set
    CLOUDGENIX_AUTH_TOKEN = None

# Look for CGXSH_CONFIG_PASSWORD as an environment variable.
# Only used for cgxsh (not create/edit/decrypt/encrypt of file)
if "CGXSH_CONFIG_PASSWORD" in os.environ:
    CGXSH_CONFIG_PASSWORD = os.environ.get('CGXSH_CONFIG_PASSWORD')
else:
    CGXSH_CONFIG_PASSWORD = None

# Import the WINDOWS vt100 handling function from websockets.
if sys.platform == "win32":
    from websockets.__main__ import win_enable_vt100
    # set dirslash for printing
    DIRSLASH = '\\'
else:
    DIRSLASH = '/'

# Save original traceback function
original_tracebacks = sys.excepthook


def quiet_tracebacks(exception_type, exception, traceback):
    """
    Quiet traceback function to make compact error messages unless debugging.
    :param exception_type: Exception Type
    :param exception: Exception detail
    :param traceback: Traceback
    :return: No return
    """
    sys.stderr.write(f"cgxsh: {exception_type.__name__}: {exception}\n")
    sys.stderr.flush()


def cgxsh_verbosity(verbose_level, set_format=None, set_handler=None):
    """
    Set verbosity level for debugs.
    :param verbose_level: Int for debug level
    :param set_format: (Optional) Custom format string
    :param set_handler: (Optional) Different handler than default
    :return: No Return
    """
    if not isinstance(verbose_level, int):
        return False

    # set the logging formatter and stream handle
    if set_format is None:
        # default formatter
        cgxsh_formatter = logging.Formatter("%(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s")
    elif not isinstance(set_format, str):
        # not a valid format string. Set to default.
        cgxsh_formatter = logging.Formatter("%(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s")
    else:
        # valid logging string.
        cgxsh_formatter = logging.Formatter(set_format)

    # set the logging handler if supported handler is not passed.
    if set_handler is None:
        # Default handler
        cgxsh_handler = logging.StreamHandler()
    elif not isinstance(set_handler, (logging.FileHandler, logging.Handler, logging.NullHandler,
                                      logging.StreamHandler)):
        # not a valid handler. Set to default handler.
        cgxsh_handler = logging.StreamHandler()
    else:
        # passed valid handler
        cgxsh_handler = set_handler

    # remove existing handlers
    cgxsh_logger.handlers = []

    if verbose_level == 1:
        cgxsh_logger.addHandler(cgxsh_handler)
        cgxsh_logger.setLevel(logging.INFO)
        # normal tracebacks
        sys.excepthook = original_tracebacks

    elif verbose_level >= 2:
        cgxsh_logger.addHandler(cgxsh_handler)
        cgxsh_logger.setLevel(logging.DEBUG)
        # normal tracebacks
        sys.excepthook = original_tracebacks
    else:
        # Remove all handlers
        cgxsh_logger.addHandler(cgxsh_handler)
        cgxsh_logger.setLevel(logging.WARNING)
        # make tracebacks simple
        sys.excepthook = quiet_tracebacks

    return


def print_during_input_multiline(message, indent=True):
    """
    Print during input, handle multiline.
    :param message: Text to print
    :param indent: Indent output by two chars
    :return: No return
    """
    if indent:
        final_message = message.replace('\n', '\n  ')
    else:
        final_message = message
    final_message_list = final_message.split("\n")
    for line in final_message_list:
        print_during_input(line)


def format_time_delta(cgxtimestamp):
    """
    Format a CloudGenix timestamp into Human Readable string.
    :param cgxtimestamp: Timestamp from CloudGenix API
    :return:
    """
    # cgxtimestamp may be milliseconds or nanoseconds. Drop the digits after the first 10.
    # this should work until 2264 or so :D
    cgx_seconds = int(str(cgxtimestamp)[:10])
    now_seconds = int(time.time())
    seconds = now_seconds - cgx_seconds
    # sanity check clock sku
    if seconds < 0:
        return "<=0s (client clock skew)"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 1:
        return f"{days}d{hours}h{minutes}m{seconds}s"
    elif hours > 0:
        return f"{hours}h{minutes}m{seconds}s"
    elif minutes > 0:
        return f"{minutes}m{seconds}s"
    else:
        return f"{seconds}s"


def get_input_sequence(input_data):
    """
    Take range/comma input, return list of ints
    :param input_data: String in format "1,3,10-20,5"
    :return: List of unique Integers
    """
    unique_data = set()
    for chunk in input_data.split(','):
        parts = [int(n) for n in chunk.split('-')]
        if len(parts) == 1:
            unique_data.add(parts[0])
        else:
            for range_items in range(min(parts), max(parts) + 1):
                unique_data.add(range_items)
    return list(unique_data)


def get_print_toolkitsession_list(sdk, line_filter=None):
    """
    Print a table of toolkit sessions.
    :param sdk: Logged-in CloudGenix SDK constructor
    :param line_filter: one of "all", "self" or "element"
    :return: session_id to element_id lookup dict.
    """
    session_id2e = {}
    parsed_toolkit_sessions = []
    # update caches
    operator_update = update_operators_cache(sdk)
    update_elements_cache(sdk)

    if operator_update:
        # worked, save
        operators_id2n = OPERATORS_ID2N
    else:
        # could not get API - at least make self map
        operator_id2n = {sdk.operator_id: sdk.email}

    toolkit_resp = sdk.get.toolkitsessions()
    if not toolkit_resp.cgx_status:
        # get any error
        error_msg = sdk.pull_content_error(toolkit_resp)
        # print and return
        if error_msg:
            sys.stderr.write(f"Error parsing toolkit sessions: {error_msg}\n")
        else:
            sys.stderr.write(f"Error parsing toolkit sessions.\n")
        sys.stderr.flush()
        return session_id2e, parsed_toolkit_sessions

    len_index = 1
    toolkit_items = sdk.extract_items(toolkit_resp, 'toolkitsessions')
    for toolkit_session in toolkit_items:
        start_time = toolkit_session.get("_created_on_utc")
        operator_id = toolkit_session.get("_created_by_operator_id")
        element_id = toolkit_session.get("element_id")
        session_id = toolkit_session.get("session_id")
        state = toolkit_session.get("state")
        # get ready lookup dict.
        session_id2e[session_id] = element_id

        if (line_filter == "self" and
            operator_id == sdk.operator_id) or (line_filter == "element" and
                                                element_id == CONNECTING_ELEMENT_ID) or line_filter in ["all", None]:
            # matched filter, put in table.
            parsed_toolkit_sessions.append({
                "Index": len_index,
                "Element": ELEMENTS_ID2N.get(element_id, element_id),
                "Operator": OPERATORS_ID2N.get(operator_id, operator_id),
                "Age": format_time_delta(start_time),
                "State": state,
                "Session ID": session_id
            })
            len_index += 1

    len_sessions = len(parsed_toolkit_sessions)

    if len_sessions < 1:
        # no data, make fake.
        parsed_toolkit_sessions.append({
            "Index": None,
            "Element": None,
            "Operator": None,
            "Age": None,
            "State": None,
            "Session ID": None
        })

    # start printing.
    if line_filter == "self":
        line_filter_txt = f" Matching Operator {sdk.email}"
    elif line_filter == "element":
        line_filter_txt = f" Matching Element {ELEMENTS_ID2N.get(CONNECTING_ELEMENT_ID, CONNECTING_ELEMENT_ID)}"
    else:
        line_filter_txt = ""
    sys.stdout.write(f"Toolkit Sessions{line_filter_txt}:\n")
    sys.stdout.write(tabulate.tabulate(parsed_toolkit_sessions, headers="keys"))
    sys.stdout.write(f"\nTotal: {len_sessions}")
    sys.stdout.flush()

    return session_id2e, parsed_toolkit_sessions


def kill_print_toolkitsession(sdk, line_filter=None):
    """
    Print table then give menu to kill sessions
    :param sdk: Logged-in CloudGenix SDK constructor
    :param line_filter: one of "all", "self" or "element"
    :return: Bool, True for no error.
    """
    session_id2e, parsed_toolkit_sessions = get_print_toolkitsession_list(sdk, line_filter=line_filter)

    if len(parsed_toolkit_sessions) < 1 or (len(parsed_toolkit_sessions) < 2 and
                                            parsed_toolkit_sessions[0].get("Index") is None):

        # no sessions, or "fake" session to make empty table appear.
        sys.stdout.write("No sessions to kill.\n")
        sys.stdout.flush()
        return True

    valid = False
    choice_list = []
    # valid indexes
    indexes = [index.get("Index") for index in parsed_toolkit_sessions if index.get("Index")]
    cgxsh_logger.debug(f"INDEXES: {indexes} ")
    # loop for input on what to kill.
    while not valid:
        sys.stdout.write("\nEnter Index to remove, range for multiple (eg. 1,3,5-10), or x to exit: ")
        sys.stdout.flush()
        choice = input()

        if 'x' in choice:
            # leave if x
            sys.stdout.write(f"Exiting..\n")
            sys.stdout.flush()
            return True

        # check if valid chars. Set - Set = False if chars match.
        invalid_chars = set(str(choice)) - set("0123456789,-")
        cgxsh_logger.debug(f"INVALID_CHARS: {invalid_chars} ")
        if invalid_chars:
            sys.stdout.write(f"\nError: invalid chars in input: '{','.join([str(char) for char in invalid_chars])}'\n")
            sys.stdout.flush()
        else:
            # chars are valid.
            choice_list = get_input_sequence(choice.lower())
            # check for valid indexes.
            invalid_choices = set(choice_list) - set(indexes)
            cgxsh_logger.debug(f"INVALID_CHOICES: {invalid_choices} ")
            if invalid_choices:
                # not valid
                sys.stdout.write(f"\nError: invalid choices in input: "
                                 f"'{','.join([str(char) for char in invalid_choices])}'\n")
                sys.stdout.flush()
            else:
                # good to go
                valid = True

    # kill!
    sys.stdout.write(f"Planning to end the following sessions (index): "
                     f"{','.join([str(char) for char in choice_list])}.\n")
    sys.stdout.flush()
    go_forward = input("Confirm? (y/n): ")
    if go_forward.lower() == 'y':
        # get matching entries
        remove_session_list = [session_entry for session_entry in parsed_toolkit_sessions
                               if session_entry.get("Index") in choice_list]
        # remove
        for session in remove_session_list:
            session_id = session.get("Session ID")
            element_id = session_id2e.get(session_id)
            element_name = session.get("Element")
            index = session.get("Index")

            if session_id and element_id:
                sess_del_resp = sdk.delete.element_toolkitsessions(element_id, session_id)
                if not sess_del_resp:
                    # Didn't work.
                    error_text = sdk.pull_content_error(sess_del_resp)
                    if error_text:
                        sys.stderr.write(f"Unable to end session {index} to {element_name}: {error_text}.\n")
                    else:
                        sys.stderr.write(f"Unable to end session {index} to {element_name}: "
                                         f"{sess_del_resp.status_code}.\n")
                    sys.stderr.flush()
                else:
                    # worked.
                    sys.stdout.write(f"Ended session {index} to {element_name}.\n")
                    sys.stdout.flush()
            else:
                # could not get session or element ID.
                sys.stdout.write(f"Unable to end session {index} to {element_name}: "
                                 f"Unable to get session_id ({session_id}) or element_id ({element_id}).\n")
                sys.stdout.flush()

    else:
        sys.stdout.write(f"Exiting..\n")
        sys.stdout.flush()
        return True


class CgxshMenu(cmd.Cmd):
    """
    CGXSH Escape key menu. Docstrings below this class are used in output, so descriptions are not consistent with the
    rest of the project.
    """
    intro = "\n"
    prompt = 'cgxsh> '

    send_chars = ['escape']
    debug_chars = ['0', '1', '2', '3']
    verbosity_chars = ['0', '1', '2']
    sessions_chars = ['self', 'element', 'all']
    sessions_kill_chars = ['self', 'element', 'all']

    menu_result = None
    sdk = None

    def do_send(self, line):
        """Send special characters:
        escape      Send cgxssh escape character to remote.
        """
        if line and line in self.send_chars:
            self.menu_result = f"{line}"
            return self.menu_result
        elif line == '':
            # print self docstring if no command
            print(self.do_send.__doc__)
        elif line[-1] == '?':
            # print self docstring if ends with ?
            print(self.do_send.__doc__)
        else:
            print(f"Invalid send '{line}', valid options are {', '.join(self.send_chars)}")

    def complete_send(self, text, line, begidx, endidx):
        if not text:
            completions = self.send_chars[:]
        else:
            completions = [f for f in self.send_chars if f.startswith(text)]
        return completions

    def do_sdkdebug(self, line):
        """Enable/Disable CloudGenix API/WebSocket debug messages to console:
        0           Disable Debugging
        1           INFO level Debugging (brief)
        2           DEBUG level Debugging (verbose)
        3           DEBUG level Debugging plus raw URLLIB3 output (extra verbose)
        """
        if line and str(line) in self.debug_chars:
            self.menu_result = f"sdkdebug{str(line)}"
            return self.menu_result
        elif line == '':
            # got just command without level, print current level.
            print(f"CloudGenix SDK Debug Level is currently {SDKDEBUG_LEVEL}")
        elif line[-1] == '?':
            # print self docstring if ends with ?
            print(self.do_sdkdebug.__doc__)
        else:
            print(f"Invalid debug '{line}', valid options are {', '.join(self.debug_chars)}")

    def do_verbosity(self, line):
        """Change cgxsh message verbosity:
        0           Default messages
        1           INFO level messages (brief)
        2           DEBUG level messages (verbose)
        """
        if line and str(line) in self.verbosity_chars:
            self.menu_result = f"verbosity{str(line)}"
            return self.menu_result
        elif line == '':
            # got just command without level, print current level.
            print(f"Cgxsh Verbosity Level is currently {CGXSH_VERBOSITY_LEVEL}")
        elif line[-1] == '?':
            # print self docstring if ends with ?
            print(self.do_verbosity.__doc__)
        else:
            print(f"Invalid verbosity '{line}', valid options are {', '.join(self.verbosity_chars)}")

    def complete_debug(self, text, line, begidx, endidx):
        if not text:
            completions = self.debug_chars[:]
        else:
            completions = [f for f in self.debug_chars if f.startswith(text)]
        return completions

    def do_sessions(self, line):
        """View active toolkit sessions:
        self        Your active sessions (all Elements)
        element     All active user sessions (this Element)
        all         All active user sessions (all Elements)
        """
        if line and str(line) in self.sessions_chars:
            cgxsh_logger.debug(f"SESSIONS CMD: '{line}'")
            get_print_toolkitsession_list(self.sdk, line_filter=str(line))
            self.menu_result = f"sessions-{str(line)}"
            return self.menu_result
        elif line == '':
            # got just command without level, print current docstring.
            print(self.do_sessions.__doc__)
        elif line[-1] == '?':
            # print self docstring if ends with ?
            print(self.do_sessions.__doc__)
        else:
            print(f"Invalid sessions '{line}', valid options are {', '.join(self.sessions_chars)}")

    def complete_sessions(self, text, line, begidx, endidx):
        if not text:
            completions = self.sessions_chars[:]
        else:
            completions = [f for f in self.sessions_chars if f.startswith(text)]
        return completions

    def do_sessions_kill(self, line):
        """Kill/clear active toolkit sessions:
        self        Select session to kill/clear from your active sessions (all Elements)
        element     Select session to kill/clear from all active sessions (this Element)
        all         Select session to kill/clear from all active sessions (all Elements)
        """
        if line and str(line) in self.sessions_chars:
            cgxsh_logger.debug(f"CMD: '{line}'")
            kill_print_toolkitsession(self.sdk, line_filter=str(line))
            self.menu_result = f"sessions_kill-{str(line)}"
            return self.menu_result
        elif line == '':
            # got just command without level, print current docstring.
            print(self.do_sessions_kill.__doc__)
        elif line[-1] == '?':
            # print self docstring if ends with ?
            print(self.do_sessions_kill.__doc__)
        else:
            print(f"Invalid sessions_kill '{line}', valid options are {', '.join(self.sessions_kill_chars)}")

    def complete_sessions_kill(self, text, line, begidx, endidx):
        if not text:
            completions = self.sessions_kill_chars[:]
        else:
            completions = [f for f in self.sessions_kill_chars if f.startswith(text)]
        return completions

    def do_quit(self, line):
        """Quit cgxsh"""
        self.menu_result = "quit"
        return self.menu_result

    # def do_printout(self, line):
    #     """Dump Logging Tree"""
    #     printout()
    #     return None

    def do_help(self, *args):
        if len(args) < 2 and args[0] == '':
            print("""Commands are:
    send            Send special characters (help send for more)
    sdkdebug        Enable/Disable API/WebSocket debug messages (help sdkdebug for more)
    verbosity       Change cgxsh message verbosity (help verbosity for more)
    sessions        View active Toolkit Websocket Sessions (help sessions for more)
    sessions_kill   View and kill/close active Toolkit Websocket Sessions (help sessions_kill for more)
    quit            Close the connection and exit.
    close           Close the connection and exit.
    exit            Close the connection and exit.
    help            Additional help on sub commands. eg: help <command>
    
    Pressing <enter> on empty command line will return you to session.
    """)
        else:
            cmd.Cmd.do_help(self, *args)

    # alias do_exit, do_close to do_quit
    do_exit = do_quit
    do_close = do_quit

    # def do_help(self, line):

    def emptyline(self):
        self.menu_result = "continue"
        return self.menu_result

    def precmd(self, line):
        line = line.lower()
        return line

    def cmdloop(self, intro=None, cgx_sdk=None):
        self.sdk = cgx_sdk
        if not self.sdk:
            # no SDK, exit.
            return "error no SDK"
        # override cmdloop to return value
        cmd.Cmd.cmdloop(self, intro=intro)
        return self.menu_result


def safe_log_config(config, sensitive_text=None):
    """
    When logging/printing config, replace sensitive parts.
    :param config: Text config file contents
    :param sensitive_text: List of sensitive keys
    :return: text with sensitive config items auto-hidden.
    """
    return_config_list = []

    if sensitive_text is None:
        sensitive_text = ['password', 'auth_token']

    config_list = jdout(config).split('\n')

    for config_line in config_list:
        # save initial line so it can be edited for each loop.
        modifiable_config_line = config_line
        # iterate through each sensitive word
        for sensitive_word in sensitive_text:
            # is sensitive word in line?
            if sensitive_word in modifiable_config_line.lower() and ':' in modifiable_config_line.lower():

                # sensitive word exists in key or value.
                split_config_line = config_line.split(':', 1)  # split on first colon.

                if sensitive_word in split_config_line[0].lower() and split_config_line[1] != " null":
                    # sensitive word in key, with a valid value. mute value.
                    split_config_line[1] = " < Sensitive value auto-hidden >"

                    # when modified, reset line to new value. If no modify, leave line for next word check.
                    modifiable_config_line = ":".join(split_config_line)

        # Save muted or not muted line back for return.
        return_config_list.append(modifiable_config_line)

    return "\n".join(return_config_list)


def config_read_write_default():
    """
    Load and/or create config file.
    :return: read final config file.
    """
    # check config file.
    home_dir = pathlib.Path.home()
    config_file_path = str(home_dir) + DIRSLASH + CONFIG_DIR + DIRSLASH + CONFIG_YAML
    config_directory_path = str(home_dir) + DIRSLASH + CONFIG_DIR
    config_dir_exists = os.path.exists(config_directory_path)
    config_file_exists = os.path.isfile(config_file_path)

    if not config_dir_exists or not config_file_exists:
        sys.stdout.write(f"Config File '{config_file_path}' does not exist. Create? (Y/N): ")
        sys.stdout.flush()
        answer = getch()
        if answer.lower() not in ['y']:
            raise CgxshGeneralError(f"\nUnable to create (and thus load) config '{config_file_path}'. Exiting.")

        sys.stdout.write('\n')
        # launch the config file create process.
        created_config_encrypted = create_config_file()
        if created_config_encrypted:
            # let user know they need to re-enter password.
            sys.stdout.write("Please re-enter password to use the \"just created\" encrypted config.\n")
    # check if file is readable.
    if not os.access(config_file_path, os.R_OK):
        raise CgxshGeneralError(f"\nUnable to load config '{config_file_path}'. Exiting.")

    # initialize read_config
    read_config = None

    if CGXSH_CONFIG_PASSWORD:
        # if password for config file is set via ENV variable, attempt to use.
        try:
            is_encrypted, _, _ = check_get_file(config_file_path)
            if is_encrypted:
                # try ENV VAR password
                file_pw = CGXSH_CONFIG_PASSWORD
                read_success, file_data = read_encrypted_file(config_file_path, file_pw)
                if not read_success:
                    sys.stderr.write('Cannot decrypt configuration with CGXSH_CONFIG_PASSWORD environment variable.')
                    sys.stderr.flush()
                    read_config = None
                else:
                    read_config = yaml.safe_load(file_data)

            else:
                # cleartext
                with open(config_file_path, "rb") as f:
                    read_config = yaml.safe_load(f)
        except (yaml.YAMLError, yaml.MarkedYAMLError) as e:
            raise CgxshGeneralError(f"'{config_file_path}' contains invalid YAML syntax: {e}")

    # if config file is not yet loaded/decrypted at this point, prompt for password.
    if read_config is None:
        try:
            is_encrypted, _, _ = check_get_file(config_file_path)
            if is_encrypted:
                # prompt for password.
                file_pw = getpass('Configuration Encrypted. Password: ')
                read_success, file_data = read_encrypted_file(config_file_path, file_pw)
                if not read_success:
                    raise CgxshGeneralError(f"\nUnable to load config '{config_file_path}'. Please verify password.")
                else:
                    read_config = yaml.safe_load(file_data)
            else:
                # cleartext
                with open(config_file_path, "rb") as f:
                    read_config = yaml.safe_load(f)
        except (yaml.YAMLError, yaml.MarkedYAMLError) as e:
            raise CgxshGeneralError(f"'{config_file_path}' contains invalid YAML syntax: {e}")

    # Finally, return the read config.
    return read_config


def direct_print(string):
    """
    Generic output function via STDOUT
    :param string: String to output
    :return: None
    """
    sys.stdout.write(f"{string}")
    sys.stdout.flush()


def pick_element(element_str, sdk):
    """
    Get element ID and username from string.
    :param element_str: string from argument parsing/SDK login for element.
    :param sdk: Logged in CloudGenix SDK Constructor
    :return: element_id
    """
    # update cache
    update_elements_cache(sdk)

    name_list = [name for name in ELEMENTS_N2ID.keys()]
    id_list = [idnum for idnum in ELEMENTS_ID2N.keys()]

    # fuzzy match
    host_id = None
    host_name = None
    possibilities = process.extract(element_str, name_list + id_list, limit=7)
    first_choice, first_percent = possibilities[0]
    # perfect match, just get..
    if first_percent == 100:
        #
        if first_choice in name_list:
            host_id = ELEMENTS_N2ID.get(first_choice)
            host_name = first_choice
        else:
            host_id = first_choice
            host_name = ELEMENTS_ID2N.get(first_choice)

        sys.stdout.write(f"Connecting to {host_name} ({host_id}).\n")
        return host_id

    # good guess match..
    elif first_percent >= 95:
        sys.stdout.write(f"No match for {element_str}, close match in {first_choice}, use that? (y/n):")
        sys.stdout.flush()
        yesno = getch()
        sys.stdout.write(yesno)
        sys.stdout.flush()
        if yesno.lower() == 'y':
            if first_choice in name_list:
                host_id = ELEMENTS_N2ID.get(first_choice)
                host_name = first_choice
            else:
                host_id = first_choice
                host_name = ELEMENTS_ID2N.get(first_choice)

            sys.stdout.write(f"\nConnecting to {host_name} ({host_id}).\n")
            return host_id

        # No else, if 'n', will display a list to try and get a better match.

    # If host_id not set at this point, display a list.
    if host_id is None:
        sys.stdout.write(f"No match for {element_str}, best guesses:\n")
        index = 1
        for choice, percent in possibilities:
            sys.stdout.write(f"  {index}) {choice}, ({percent}%)\n")
            index += 1
        sys.stdout.write("Select a number, or any other key to exit: ")
        sys.stdout.flush()
        picked_index = getch()
        sys.stdout.write(picked_index + '\n')
        sys.stdout.flush()
        if picked_index.isdigit() and 1 <= int(picked_index) <= len(possibilities):
            # pull the tuple out - index is one more than the list index.
            selected_choice, selected_percent = possibilities[int(picked_index) - 1]
            if selected_choice in name_list:
                host_id = ELEMENTS_N2ID.get(selected_choice)
                host_name = selected_choice
            else:
                host_id = selected_choice
                host_name = ELEMENTS_ID2N.get(selected_choice)

            sys.stdout.write(f"Connecting to {host_name} ({host_id}).\n")
            return host_id
        else:
            raise CgxshElementSelectionError(f"No presented element was acceptable.")

    # if got here, something is very wrong.
    raise CgxshElementSelectionError(f"Element Selection Failure")


def pick_client(client_string, sdk):
    """
    Get element ID and username from string.
    :param client_string: string from arg or other
    :param sdk: Logged in CloudGenix SDK Constructor
    :return: element_id, user_name
    """
    # update client caches.
    update_clients_cache(sdk)

    client_name_list = [name for name in CLIENT_N2ID.keys()]
    client_canonical_name_list = [name for name in CLIENT_CANONICAL_N2ID.keys()]
    client_id_list = [idnum for idnum in CLIENT_ID2R.keys()]

    # build inverted lookup dicts
    client_id2n = {value: key for key, value in CLIENT_N2ID.items()}
    client_canonical_id2n = {value: key for key, value in CLIENT_CANONICAL_N2ID.items()}

    # fuzzy match
    possibilities = process.extract(client_string, client_name_list + client_canonical_name_list + client_id_list,
                                    limit=7)
    first_choice, first_percent = possibilities[0]

    client_id = None
    client_name = None
    client_canonical_name = None

    # perfect match, just get..
    if first_percent == 100:
        if first_choice in client_name_list:
            client_id = CLIENT_N2ID.get(first_choice)
            client_name = first_choice
            client_canonical_name = client_canonical_id2n.get(CLIENT_N2ID.get(first_choice, {}))
        elif first_choice in client_canonical_name_list:
            client_id = CLIENT_CANONICAL_N2ID.get(first_choice)
            client_name = client_id2n.get(CLIENT_CANONICAL_N2ID.get(first_choice, {}))
            client_canonical_name = first_choice
        else:
            # has to be client_id
            client_id = first_choice
            client_name = client_id2n.get(first_choice)
            client_canonical_name = client_canonical_id2n.get(first_choice)

        cgxsh_logger.debug(f"Matched client {client_name} ({client_canonical_name}, ID: {client_id}, "
                           f"Region: {CLIENT_ID2R.get(client_id)})")

    # good guess match..
    elif first_percent >= 95:
        sys.stdout.write(f"No match for client {client_string}. Close match in {first_choice}, use that? (y/n):")
        sys.stdout.flush()
        yesno = getch()
        sys.stdout.write(yesno)
        sys.stdout.flush()
        if yesno.lower() == 'y':
            if first_choice in client_name_list:
                client_id = CLIENT_N2ID.get(first_choice)
                client_name = first_choice
                client_canonical_name = client_canonical_id2n.get(CLIENT_N2ID.get(first_choice, {}))
            elif first_choice in client_canonical_name_list:
                client_id = CLIENT_CANONICAL_N2ID.get(first_choice)
                client_name = client_id2n.get(CLIENT_CANONICAL_N2ID.get(first_choice, {}))
                client_canonical_name = first_choice
            else:
                # has to be client_id
                client_id = first_choice
                client_name = client_id2n.get(first_choice)
                client_canonical_name = client_canonical_id2n.get(first_choice)

            cgxsh_logger.debug(f"Matched client {client_name} ({client_canonical_name}, ID: {client_id}, "
                               f"Region: {CLIENT_ID2R.get(client_id)})")

        # No else, if 'n', will display a list to try and get a better match.

    # if client ID not set, have not found a direct or acceptable slightly-fuzzy match. Give a list.
    if client_id is None:

        # No close match, or close match wrong. Ask a list...
        sys.stdout.write(f"No match for {client_string}, best guesses:\n")
        index = 1
        for choice, percent in possibilities:
            sys.stdout.write(f"  {index}) {choice}, ({percent}%)\n")
            index += 1
        sys.stdout.write("Select a number, or any other key to exit: ")
        sys.stdout.flush()
        picked_index = getch()
        sys.stdout.write(picked_index + '\n')
        sys.stdout.flush()
        if picked_index.isdigit() and 1 <= int(picked_index) <= len(possibilities):
            # pull the tuple out - index is one more than the list index.
            selected_choice, selected_percent = possibilities[int(picked_index) - 1]
            if selected_choice in client_name_list:
                client_id = CLIENT_N2ID.get(selected_choice)
                client_name = selected_choice
                client_canonical_name = client_canonical_id2n.get(CLIENT_N2ID.get(selected_choice, {}))
            elif selected_choice in client_canonical_name_list:
                client_id = CLIENT_CANONICAL_N2ID.get(selected_choice)
                client_name = client_id2n.get(CLIENT_CANONICAL_N2ID.get(selected_choice, {}))
                client_canonical_name = selected_choice
            else:
                # has to be client_id
                client_id = selected_choice
                client_name = client_id2n.get(selected_choice)
                client_canonical_name = client_canonical_id2n.get(selected_choice)

            cgxsh_logger.debug(f"Matched client {client_name} ({client_canonical_name}, ID: {client_id}, "
                               f"Region: {CLIENT_ID2R.get(client_id)})")

        else:
            raise CgxshControllerClientLoginError(f"No match for {client_string} found.")

    # got here, client was picked.
    return client_id, client_name, client_canonical_name


def cgx_client_login_minimal(sdk, chosen_client_id):
    """
    Reimplementation of interactive.client_login from CloudGenix Python SDK 5.2.1 - to login with just client_id.
    :param sdk: Logged in CloudGenix SDK Constructor
    :param chosen_client_id: ID of ESP Client.
    :return: Boolean: True if successful.
    """

    clogin_resp = sdk.post.clients_login(chosen_client_id, {})

    if clogin_resp.cgx_status:
        # see if we need to change regions.
        redirect_region = clogin_resp.cgx_content.get('redirect_region')
        redirect_x_auth_token = clogin_resp.cgx_content.get('redirect_x_auth_token')
        redirect_urlpath = clogin_resp.cgx_content.get('redirect_urlpath')

        if redirect_region is not None and redirect_x_auth_token is not None:
            cgxsh_logger.debug('CLIENT REGION SWITCH: %s -> %s', sdk.controller_region,
                               redirect_region)
            # Need to change regions.
            sdk.update_region_to_controller(redirect_region)

            # Now set a temporary X-Auth-Token header, overwriting previous if there.
            # if using a static AUTH_TOKEN, client login will switch to dynamic via
            # Cookies.
            sdk.add_headers({'X-Auth-Token': redirect_x_auth_token})

        # login successful, update profile

        # Profile call will set new login cookies if switching regions.
        c_profile = sdk.interactive.update_profile_vars()
        if redirect_region is not None and redirect_x_auth_token is not None:
            # if region switch, we need to clear the X-Auth-Token header, as it was a temporary value
            # and now we are using cookies for ephemeral AUTH_TOKENs.
            sdk.remove_header('X-Auth-Token')

        # Update tenant info.
        t_profile = sdk.interactive.tenant_update_vars()

        if c_profile and t_profile:
            # remove referer header prior to continuing.
            sdk.remove_header('Referer')
            return True

        else:
            # remove referer header prior to continuing.
            sdk.remove_header('Referer')
            raise CgxshControllerClientLoginError(f"Client Login to ID {chosen_client_id} failed. "
                                                  f"(unable to retrieve Client Profile(s))")
    else:
        # remove referer header prior to continuing.
        sdk.remove_header('Referer')
        raise CgxshControllerClientLoginError(f"Client Login to ID {chosen_client_id} failed.")


def cgx_sdk_login(args):
    """
    Function to handle SDK login, hook and load config file, and also update some globle CGX object caches.
    :param args: argparse object with arguments
    :return: tuple of (Logged-in CloudGenix SDK, element ID, device toolkit username, device toolkit password)
    """

    # Build SDK Constructor
    if args['controller'] and args['insecure']:
        cgxsh_logger.debug(f"Using CONTROLLER: {args['controller']}, SSL_VERIFY: {False}")
        sdk = cloudgenix.API(controller=args['controller'], ssl_verify=False)
    elif args['controller']:
        cgxsh_logger.debug(f"Using CONTROLLER: {args['controller']}, SSL_VERIFY: {True}")
        sdk = cloudgenix.API(controller=args['controller'])
    elif args['insecure']:
        cgxsh_logger.debug(f"Using SSL_VERIFY: {False}")
        sdk = cloudgenix.API(ssl_verify=False)
    else:
        sdk = cloudgenix.API()

    # check for region ignore
    if args['ignore_region']:
        cgxsh_logger.debug(f"Using IGNORE_REGION: {True}")
        sdk.ignore_region = True

    # check for force hosts.
    if args['force_host']:
        cgxsh_logger.debug(f"Forcing HOST header to : {args['force_host']}")
        sdk.add_headers({"Host": args['force_host']})
        sdk.websocket_add_headers({"Host": args['force_host']})

    # SDK debug, default = 0. Can be set also by command shell. Set from GLOBAL (set by main func).
    # 0 = logger handlers removed, critical only
    # 1 = logger info messages
    # 2 = logger debug messages.
    # 3 = logger debug + URLLIB3 messages.
    cgxsh_logger.debug(f"CloudGenix SDK DEBUG set to : {SDKDEBUG_LEVEL}")
    sdk.set_debug(SDKDEBUG_LEVEL)

    # handle config loading defaults
    loaded_auth_token = None
    loaded_controller_email = None
    loaded_controller_password = None
    loaded_device_user = None
    loaded_device_password = None
    loaded_esp_dict = {}

    # try to load config items
    if isinstance(LOADED_CONFIG, dict):
        default_config = LOADED_CONFIG.get('DEFAULT')
        if default_config and isinstance(default_config, dict):
            loaded_auth_token = default_config.get('AUTH_TOKEN')
            loaded_controller_email = default_config.get('CONTROLLER_USER')
            loaded_controller_password = default_config.get('CONTROLLER_PASSWORD')
            loaded_device_user = default_config.get('DEVICE_USER')
            loaded_device_password = default_config.get('DEVICE_PASSWORD')
        else:
            cgxsh_logger.debug(f"Cannot read 'DEFAULT' Config key: {type(default_config)}")
        loaded_esp_dict = LOADED_CONFIG.get("ESP")

    else:
        cgxsh_logger.debug(f"Config corrupt, root not in dictionary format: {type(LOADED_CONFIG)}")

    loaded_str = ""
    loaded_str += "GLOBAL auth_token, " if loaded_auth_token else ""
    loaded_str += "GLOBAL controller_email, " if loaded_controller_email else ""
    loaded_str += "GLOBAL controller_password, " if loaded_controller_password else ""
    loaded_str += "GLOBAL device_user, " if loaded_device_user else ""
    loaded_str += "GLOBAL device_password, " if loaded_device_password else ""
    loaded_str += "initial ESP config, " if loaded_esp_dict else ""

    if loaded_str:
        cgxsh_logger.debug(f"Loaded the following items from config file: {loaded_str}")

    # login logic. Use cmdline if set, use AUTH_TOKEN next, finally user/pass from config file, then prompt.
    # figure out user
    if args["controller_email"]:
        controller_email = args["controller_email"]
        controller_email_from = "commandline arguments"
    elif loaded_controller_email:
        controller_email = loaded_controller_email
        controller_email_from = "Configuration File DEFAULT section, CONTROLLER_USER"
    else:
        controller_email = None
        controller_email_from = None

    # figure out password
    if args["controller_password"]:
        controller_password = args["controller_password"]
        controller_password_from = "commandline arguments"
    elif loaded_controller_password:
        controller_password = loaded_controller_password
        controller_password_from = "Configuration File DEFAULT section, CONTROLLER_PASSWORD"
    else:
        controller_password = None
        controller_password_from = None

    # check for token, AUTH_TOKEN takes priority
    if CLOUDGENIX_AUTH_TOKEN or loaded_auth_token:
        if CLOUDGENIX_AUTH_TOKEN:
            cgxsh_logger.debug(f"Using ENV X_AUTH_TOKEN/AUTH_TOKEN to authenticate to controller.")
            sdk.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
            if sdk.tenant_id is None:
                raise CgxshControllerLoginError(f"ENV X_AUTH_TOKEN/AUTH_TOKEN login failure, please check token.")
            else:
                cgxsh_logger.debug(f"Controller login success. tenant_id: {sdk.tenant_id}, "
                                   f"controller: {sdk.controller}.")

        elif loaded_auth_token:
            sdk.interactive.use_token(loaded_auth_token)
            cgxsh_logger.debug(f"Using Configuration File DEFAULT AUTH_TOKEN to authenticate to controller.")
            if sdk.tenant_id is None:
                raise CgxshControllerLoginError(f"Configuration File DEFAULT AUTH_TOKEN login failure, "
                                                f"please check token.")
            else:
                cgxsh_logger.debug(f"Controller login success. tenant_id: {sdk.tenant_id}, "
                                   f"controller: {sdk.controller}.")

        if sdk.is_esp:
            # if using AUTH_TOKEN, ESP tenants won't have any devices, and AUTH_TOKENs cant move into tenants. Throw
            # error.
            raise CgxshControllerLoginError(f"Logged in with AUTH_TOKEN, but account is an ESP/MSP. Cannot use "
                                            f"AUTH_TOKEN with ESP/MSP account, please connect with 'CONTROLLER_USER' "
                                            f"and 'CONTROLLER_PASSWORD'")

    else:
        cgxsh_logger.debug(f"Logging in to controller with email/password. Email from: {controller_email_from},"
                           f" Password from: {controller_password_from}.")
        retry = 0
        while sdk.tenant_id is None and retry < 3:
            sdk.interactive.login(controller_email, controller_password, client_login=False)
            # clear after one failed login, force manual login.
            if not sdk.tenant_id:
                cgxsh_logger.debug(f"Controller login FAIL. tenant_id: {sdk.tenant_id}, "
                                   f"retry count: {retry}.")
                controller_email = None
                controller_password = None
                retry += 1

        # see if login worked
        if not sdk.tenant_id:
            raise CgxshControllerLoginError(f"Login failed after {retry} attempts. "
                                            f"Stopping to prevent account lockout.")

    # parse element @ client (ESP/msp) string
    element_string = args['element[@client]']
    element_client = element_string.rsplit('@', 1)
    if len(element_client) is 1:
        # just element
        element = element_client[0]
        client = None
    else:
        # host and user
        element = element_client[0]
        client = element_client[1]

    # Check to see if we need to do Client Login, and figure out config file user(s) and password(s)
    esp_loaded_device_user = None
    esp_loaded_device_password = None
    loaded_client_config_value = None
    if sdk.is_esp and client:
        # update caches.
        cgxsh_logger.debug(f"In ESP, attempting to log into client {client}")
        client_id, client_name, client_canonical_name = pick_client(client, sdk)

        # manually log in to client to save time. Interactive re-pulls client list which can take multiple seconds.
        sys.stdout.write(f"\nConnecting to Client {client_name} ({client_canonical_name}).\n")
        sys.stdout.flush()
        client_login_status = cgx_client_login_minimal(sdk, client_id)
        cgxsh_logger.debug(f"Client Login to {client} successful")
        # attempt to get ESP specific device credentials from config file.

        if isinstance(loaded_esp_dict, dict):

            # check ID, then canonical name, then name.
            if client_id in loaded_esp_dict.keys():
                # client ID matches a key
                loaded_client_config = loaded_esp_dict.get(client_id)
                loaded_client_config_using = "Client ID"
                loaded_client_config_value = client_id
                cgxsh_logger.debug(f"Loaded ESP section config from '{loaded_client_config_value}', "
                                   f"matched {loaded_client_config_using}.")
            elif client_canonical_name in loaded_esp_dict.keys():
                # canonical name matches a key
                loaded_client_config = loaded_esp_dict.get(client_canonical_name)
                loaded_client_config_using = "Client Canonical Name"
                loaded_client_config_value = client_canonical_name
                cgxsh_logger.debug(f"Loaded ESP section config from '{loaded_client_config_value}', "
                                   f"matched {loaded_client_config_using}.")
            elif client_name in loaded_esp_dict.keys():
                # canonical name matches a key
                loaded_client_config = loaded_esp_dict.get(client_name)
                loaded_client_config_using = "Client Name"
                loaded_client_config_value = client_name
                cgxsh_logger.debug(f"Loaded ESP section config from '{loaded_client_config_value}', "
                                   f"matched {loaded_client_config_using}.")
            else:
                loaded_client_config = None
                loaded_client_config_using = None
                loaded_client_config_value = None
                cgxsh_logger.debug(f"No ESP section config found for {client_id}, {client_canonical_name} "
                                   f"or {client_name}.")

            # did we load something?
            if loaded_client_config:
                # check what we loaded
                if isinstance(loaded_client_config, dict):
                    esp_loaded_device_user = loaded_client_config.get('DEVICE_USER')
                    esp_loaded_device_password = loaded_client_config.get('DEVICE_PASSWORD')
                else:
                    cgxsh_logger.debug(f"Cannot read '{loaded_client_config_value}' ESP section "
                                       f"config key, not dictionary: {type(loaded_client_config)}")

        else:
            cgxsh_logger.debug(f"Config ESP section key corrupt, not in dictionary format: {type(loaded_esp_dict)}")

    elif client and not sdk.is_esp:
        # client specified, but not ESP session. Ignore.
        sys.stdout.write(f"Client @{client} specified, but not connected to ESP/MSP account. Ignoring.\n")
        sys.stdout.flush()

    elif sdk.is_esp and not client:
        # ESP/MSP account but no client specified..
        raise CgxshControllerLoginError(f"Logged in to ESP/MSP account, but no @client specified. Client"
                                        f" is required for ESP/MSP accounts.")

    # ok, if we got this far - we are logged into client, and we may or may not have device username/password loaded.
    if args['device_user'] is not None:
        cgxsh_logger.debug(f"Loaded Device User from commandline argument: "
                           f"{args['device_user']}")
        return_user = args['device_user']
    elif esp_loaded_device_user is not None:
        cgxsh_logger.debug(f"Loaded Device User from ESP section config '{loaded_client_config_value}': "
                           f"{esp_loaded_device_user}")
        return_user = esp_loaded_device_user
    elif loaded_device_user is not None:
        cgxsh_logger.debug(f"Loaded Device User from DEFAULT config: {loaded_device_user}")
        return_user = loaded_device_user
    else:
        cgxsh_logger.debug(f"Device User not loaded. Will prompt")
        return_user = None

    if args['device_password'] is not None:
        cgxsh_logger.debug(f"Loaded Device Password from commandline argument: "
                           f"<Sensitive value hidden>")
        return_password = args['device_password']
    if esp_loaded_device_password is not None:
        cgxsh_logger.debug(f"Loaded Device Password from ESP section config '{loaded_client_config_value}': "
                           f"<Sensitive value hidden>")
        return_password = esp_loaded_device_password
    elif loaded_device_password is not None:
        cgxsh_logger.debug(f"Loaded Device Password from DEFAULT config: <Sensitive value hidden>")
        return_password = loaded_device_password
    else:
        cgxsh_logger.debug(f"Device Password not loaded. Will prompt")
        return_password = None

    # return the SDK constructor and element_name, device login and device password.
    return sdk, element, return_user, return_password


def update_clients_cache(sdk):
    """
    Update the ESP/MSP client global name->ID caches and id->region cache.
    :param sdk: Logged in CloudGenix SDK Constructor
    :return: Boolean: True if successful.
    """
    global CLIENT_N2ID
    global CLIENT_CANONICAL_N2ID
    global CLIENT_ID2R
    cgxsh_logger.debug("Updating ESP/MSP Client Cache.")
    session_status, CLIENT_N2ID, CLIENT_CANONICAL_N2ID, CLIENT_ID2R = sdk.interactive.session_allowed_clients()
    return session_status


def update_elements_cache(sdk):
    """
    Update the global element id->name and name->id caches.
    :param sdk: Logged in CloudGenix SDK Constructor
    :return: no return, mutates globals in-place.
    """
    global ELEMENTS_ID2N
    global ELEMENTS_N2ID

    elem_resp = sdk.get.elements()

    if not elem_resp.cgx_status:
        sdk.throw_error("Unable to retrieve Elements:", elem_resp)

    elem_items = sdk.extract_items(elem_resp)

    ELEMENTS_N2ID = sdk.build_lookup_dict(elem_items)
    ELEMENTS_ID2N = sdk.build_lookup_dict(elem_items, key_val='id', value_val='name')


def update_operators_cache(sdk):
    """
    Update the global element id->name and name->id caches.
    :param sdk: Logged in CloudGenix SDK Constructor
    :return: True or False, expected to fail if no access.
    """
    global OPERATORS_ID2N

    operators_resp = sdk.get.operators_t()

    if not operators_resp.cgx_status:
        # user may not have access. Return failure.
        return False

    # update cache
    operators_items = sdk.extract_items(operators_resp)
    OPERATORS_ID2N = sdk.build_lookup_dict(operators_items, key_val='id', value_val='email')
    # return success
    return True


def force_exit_from_loop(loop, futures):
    """
    In the async thread/loop, if exit needed, send KeyboardInterrupt to main thread.
    :param loop: asyncio event loop
    :param futures: list of futures. If not all done(), send KeyboardInterrupt.
    :return: No return.
    """
    if not isinstance(futures, list):
        futures = [futures]

    loop.stop()
    force_exit = False
    for future in futures:
        if not future.done():
            cgxsh_logger.debug(f"Forcing exit due to a callback state: {str(future)}")
            force_exit = True

    if force_exit:
        try:
            ctrl_c = signal.CTRL_C_EVENT  # Windows
        except AttributeError:
            ctrl_c = signal.SIGINT  # POSIX
        cgxsh_logger.debug(f"Sending {str(ctrl_c)} to {os.getpid()}")
        os.kill(os.getpid(), ctrl_c)


async def generic_worker(loop, input_queue, stop_future, sdk, pretty_print=True, show_keepalives=False):
    """
    Generic Websocket client worker. Will be launched in different thread.
    :param loop: AsyncIO event loop, with tasks
    :param input_queue: AsyncIO Queue to get input
    :param stop_future: AsyncIO Future to call when stopping.
    :param sdk: Logged-in CloudGenix SDK
    :param pretty_print: Boolean - Pretty-print JSON responses from the server
    :param show_keepalives: Show Keepalive messages
    :return: No Return
    """
    try:
        # Get current terminal size - can't be changed after websocket connect, so right before is best time.
        termsize_tuple = os.get_terminal_size()
        columns = termsize_tuple[0]
        rows = termsize_tuple[1]
        websocket = await sdk.ws.default()
    except Exception as e:
        # failure, exit clean as possible. Some tasks end up hanging, should be canceled/exited in main thread.
        print_over_input(f"Failed to connect: {e}.")
        force_exit_from_loop(loop, [stop_future])
        return
    else:
        print_during_input(f"Connected to {sdk.tenant_name} (Tenant ID: {sdk.tenant_id})")

    # main websocket thread
    keepalive_uri = f"/v2.0/api/tenants/{sdk.tenant_id}/ws?health"
    try:
        while True:
            # Pull the websocket info.
            inbound_ws_future = asyncio.ensure_future(websocket.recv())
            outbound_ws_future = asyncio.ensure_future(input_queue.get())
            done, pending = await asyncio.wait(
                [inbound_ws_future, outbound_ws_future, stop_future],
                timeout=10,
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            if inbound_ws_future in pending:
                inbound_ws_future.cancel()
            if outbound_ws_future in pending:
                outbound_ws_future.cancel()

            if all(x in pending for x in [inbound_ws_future, outbound_ws_future, stop_future]):
                # idle timeout, send ping
                cgxsh_logger.debug("SENDING KEEPALIVE")
                await websocket.send(f'{{ "type": "GET", '
                                     f'"uri": "{keepalive_uri}", '
                                     f'"body": {{}} }}')

            if inbound_ws_future in done:
                # got a message from the Server.
                try:
                    message = inbound_ws_future.result()
                except websockets.ConnectionClosed:
                    break
                else:
                    if isinstance(message, str):
                        try:
                            success_keepalive_response = False
                            json_str = cloudgenix.json.loads(message)

                            request_body = json_str.get('request_body')

                            response_body = json_str.get('response_body')

                            if request_body:
                                json_str['request_body'] = cloudgenix.json.loads(request_body)
                            if response_body:
                                json_str['response_body'] = cloudgenix.json.loads(response_body)

                            # check for keepalive message
                            uri = json_str.get('uri')
                            body = json_str.get('body', {})
                            if not body:
                                # try response body. Set to {} if not set.
                                body = json_str.get('response_body', {})
                            # if invalid body
                            if not isinstance(body, dict):
                                body = {}
                            status = body.get("_status_code")
                            # cgxsh_logger.debug(f"JSON message. URI: {uri}, STATUS: {status}")
                            if uri == keepalive_uri and status == "200":
                                success_keepalive_response = True

                        except ValueError:
                            json_str = None
                            success_keepalive_response = False

                        # if showing keepalives, or response is NOT a successful keepalive
                        if show_keepalives or not success_keepalive_response:
                            # show keepalives is set, or response is an unsuccessful keepalive
                            if json_str is not None and pretty_print:
                                print_during_input_multiline("\u001b[31m< \u001b[0m"
                                                             "" + str(cloudgenix.json.dumps(json_str, indent=4)))

                            else:
                                print_during_input("\u001b[31m< \u001b[0m" + str(message))
                        else:
                            # show_keepalives is false and message is a successful keepalive. pass.
                            cgxsh_logger.debug('GOT SUCCESSFUL KEEPALIVE RESPONSE')
                            pass

                    else:
                        # don't print non-str
                        cgxsh_logger.debug(f"NON-STR message: {message.hex()}")

            if outbound_ws_future in done:
                # got outbound message from client. Send.
                message = outbound_ws_future.result()
                await websocket.send(message)

            if stop_future in done:
                # got a request to STOP from client.
                cgxsh_logger.debug(f"Got STOP.")
                break

    finally:
        cgxsh_logger.debug("Shutting Down worker thread.")
        # destroy the queues
        del input_queue
        await websocket.close()
        close_details = websockets.exceptions.format_close(websocket.close_code, websocket.close_reason)

        if CGXSH_VERBOSITY_LEVEL == 0:
            print_over_input(f"Connection closed.")
        else:
            print_over_input(f"Connection closed: {close_details}.")

        force_exit_from_loop(loop, [stop_future])


async def toolkit_worker(loop, input_queue, stop_future, pause_queue, element_id, sdk, element_user=None,
                         element_password=None, noexit=False, commands=None):
    """
    CloudGenix Toolkit Websocket Worker. Will be launched in different thread.
    :param loop: AsyncIO event loop, with tasks
    :param input_queue: AsyncIO Queue to get input
    :param stop_future: AsyncIO Future to call when stopping.
    :param pause_queue: AsyncIO Future to call when pausing for command shell execution
    :param element_id: Element ID to connect WebSocket to
    :param sdk: Logged-in CloudGenix SDK
    :param element_user: (optional) Username to login to toolkit with.
    :param element_password: (optional) Password to login to toolkit with.
    :param noexit: If commands are passed, and this is True, do not exit after commands.
    :param commands: (optional) List of commands to execute after login.
    :return:
    """
    try:
        # Get current terminal size - can't be changed after websocket connect, so right before is best time.
        termsize_tuple = os.get_terminal_size()
        columns = termsize_tuple[0]
        rows = termsize_tuple[1]
        websocket = await sdk.ws.toolkit_session(element_id, cols=columns, rows=rows, close_timeout=1)
    except Exception as e:
        # failure, exit clean as possible. Some tasks end up hanging, should be canceled/exited in main thread.
        print_over_input(f"Failed to connect to {element_id}: {e}.")
        force_exit_from_loop(loop, [stop_future])
        return
    else:
        print_during_input(f"Connected to {element_id}.")
        # look up escape char in table for representation, return Python representation if not found.
        print_during_input(f"Escape character is '{DEFAULT_CONTROL_CHAR_DICT.get(ESCAPE_CHAR, repr(ESCAPE_CHAR))}'.")

    # set local statuses to have function level scope throughout while loops
    logged_in = False
    paused = False
    # Check if commands are passed and noexit flag is False (do exit.) if so, exit after commands and don't send
    # interactive writes.
    deny_interactive = True if commands and not noexit else False
    cgxsh_logger.debug(f"Deny Interactive Input Flag: {deny_interactive}")
    if len(commands) > 0 and deny_interactive:
        # Send exit command at end of commands.
        commands.append('exit')

    # Initial login loop. Handle login before passing off interactive, if not a generic websocket client.
    while not logged_in:
        inbound_ws_future = asyncio.ensure_future(websocket.recv())
        outbound_ws_future = asyncio.ensure_future(input_queue.get())
        pause_future = asyncio.ensure_future(pause_queue.get())
        done, pending = await asyncio.wait(
            [inbound_ws_future, outbound_ws_future, stop_future, pause_future], timeout=60,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        if inbound_ws_future in pending:
            inbound_ws_future.cancel()
        if outbound_ws_future in pending:
            outbound_ws_future.cancel()
        if pause_future in pending:
            pause_future.cancel()

        # Even in initial login, handle pause_future. Login will still occur, however the socket will get paused
        # right after login finished.
        if pause_future in done:
            # update pause_future based on bus
            message = pause_future.result()
            cgxsh_logger.debug(f"Got PAUSE message: {message}")
            paused = message

        if inbound_ws_future in done:
            try:
                message = inbound_ws_future.result()
            except websockets.ConnectionClosed:
                break
            else:
                if isinstance(message, str):
                    if message.endswith("login: "):
                        # if user was specified, send it.
                        if element_user:
                            cgxsh_logger.debug(f"Sending Username: {element_user}")
                            await websocket.send(element_user + "\n")
                            # if password was not specified, end this loop here.
                            if not element_password:
                                logged_in = True
                        else:
                            # username was not specified, print login banner and leave initial login loop.
                            direct_print(message)
                            logged_in = True

                    elif message.endswith("Password: "):
                        if element_password:
                            cgxsh_logger.debug(f"Sending Password: <Sensitive value hidden>")
                            await websocket.send(element_password + "\n")
                            logged_in = True
                        else:
                            # password was not specified. print password banner and leave initial login loop.
                            direct_print(message)
                            logged_in = True

        if outbound_ws_future in done and deny_interactive is False:
            # send keypresses
            message = outbound_ws_future.result()
            await websocket.send(message)

        if inbound_ws_future in pending and outbound_ws_future in pending:
            print_over_input("Login Execution Timeout")
            # fail login (timeout), break.
            break

    # Command Loop, if passed.
    if commands is not None:
        while len(commands) > 0:
            inbound_ws_future = asyncio.ensure_future(websocket.recv())
            outbound_ws_future = asyncio.ensure_future(input_queue.get())
            pause_future = asyncio.ensure_future(pause_queue.get())
            done, pending = await asyncio.wait(
                [inbound_ws_future, outbound_ws_future, stop_future, pause_future], timeout=60,
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            if inbound_ws_future in pending:
                inbound_ws_future.cancel()
            if outbound_ws_future in pending:
                outbound_ws_future.cancel()
            if pause_future in pending:
                pause_future.cancel()

            # Even during commands, handle pause_future. Login will still occur, however the socket will get paused
            # right after commands finished.
            if pause_future in done:
                # update pause_future based on bus
                message = pause_future.result()
                cgxsh_logger.debug(f"Got PAUSE message: {message}")
                paused = message

            if inbound_ws_future in done:
                try:
                    message = inbound_ws_future.result()
                except websockets.ConnectionClosed:
                    break
                else:
                    if isinstance(message, str):
                        # got message, print it and lets get a-parsin.
                        direct_print(message)
                        # parse
                        if message.endswith(TOOLKIT_PROMPT_READY):
                            cgxsh_logger.debug(f"Got PROMPT READY.")
                            # Ok, we're at a prompt. Grab a command off the stack and send.
                            if len(commands) > 0:
                                command = commands.pop(0)
                            else:
                                command = None

                            if command:
                                cgxsh_logger.debug(f"Sending command: '{command}'")
                                await websocket.send(command + "\n")

                            else:
                                # Somehow got here and empty command. Log and pass on.
                                cgxsh_logger.debug(f"Got empty command: '{repr(command)}'")

                        elif message.endswith("Password: ") or message.endswith("login: "):
                            # We are in automated command mode, but user/pass login failed. Fail spectacularly.
                            cgxsh_logger.debug(f"Got login or password prompt waiting for commands. Aborting.")
                            print_over_input("ERROR: Login or Password prompt waiting for commands. Aborting.")
                            break
                    else:
                        # don't print non-str
                        cgxsh_logger.debug(f"NON-STR message: {message.hex()}")

            if outbound_ws_future in done and deny_interactive is False:
                # send keypresses.
                message = outbound_ws_future.result()
                await websocket.send(message)

            if inbound_ws_future in pending and outbound_ws_future in pending:
                print_over_input("Command Execution Timeout")
                # fail command (timeout), break.
                break

    # main interactive loop.
    try:
        # only start interactive if not doing commands, or commands with noexit.
        while True and deny_interactive is False:
            if paused is True:
                # if paused, only loop for paused items
                pause_future = asyncio.ensure_future(pause_queue.get())
                done, pending = await asyncio.wait(
                    [pause_future, stop_future], return_when=asyncio.FIRST_COMPLETED
                )
                if pause_future in pending:
                    pause_future.cancel()

                if pause_future in done:
                    # update pause_future based on bus
                    message = pause_future.result()
                    cgxsh_logger.debug(f"Got PAUSE message: {message}")
                    paused = message

                if stop_future in done:
                    cgxsh_logger.debug(f"Got STOP while PAUSED")
                    break

            else:
                # if not paused, pull the websocket info.
                inbound_ws_future = asyncio.ensure_future(websocket.recv())
                outbound_ws_future = asyncio.ensure_future(input_queue.get())
                pause_future = asyncio.ensure_future(pause_queue.get())
                done, pending = await asyncio.wait(
                    [inbound_ws_future, outbound_ws_future, stop_future, pause_future],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                if inbound_ws_future in pending:
                    inbound_ws_future.cancel()
                if outbound_ws_future in pending:
                    outbound_ws_future.cancel()
                if pause_future in pending:
                    pause_future.cancel()

                if pause_future in done:
                    # update pause_future based on bus, got a pause message/request from Client.
                    message = pause_future.result()
                    cgxsh_logger.debug(f"Got PAUSE message: {message}")
                    paused = message

                if inbound_ws_future in done and paused is not True:
                    # got a message from the Server.
                    try:
                        message = inbound_ws_future.result()
                    except websockets.ConnectionClosed:
                        break
                    else:
                        if isinstance(message, str):
                            # Print each char direct to session.
                            direct_print(message)
                        else:
                            # don't print non-str
                            cgxsh_logger.debug(f"NON-STR message: {message.hex()}")

                if outbound_ws_future in done and paused is not True:
                    # got outbound message from client. Send.
                    message = outbound_ws_future.result()
                    await websocket.send(message)

                if stop_future in done:
                    # got a request to STOP from client.
                    cgxsh_logger.debug(f"Got STOP.")
                    break

    finally:
        cgxsh_logger.debug("Shutting Down worker thread.")
        # destroy the queues
        del input_queue
        del pause_queue
        await websocket.close()
        close_details = websockets.exceptions.format_close(websocket.close_code, websocket.close_reason)

        if CGXSH_VERBOSITY_LEVEL == 0:
            print_over_input(f"Connection closed.")
        else:
            print_over_input(f"Connection closed: {close_details}.")

        force_exit_from_loop(loop, [stop_future])


def generic_client():
    """
    Launch the Generic websocket client
    :return: None
    """
    global LOADED_CONFIG
    global SDKDEBUG_LEVEL
    global CGXSH_VERBOSITY_LEVEL

    if sys.platform == "win32":
        try:
            # attempt to use websockets.__main__ Windows VT100 mode
            win_enable_vt100()
        except RuntimeError as e:
            sys.stderr.write(f"Unable to set terminal to VT100 mode. Rendering may be inconsistent.\n"
                             f"Details: {e}\n")
            sys.stderr.flush()

    # Parse arguments
    parser = argparse.ArgumentParser(description="{0} ({1})".format('cgxsh_generic_ws', __version__))

    cgxsh_group = parser.add_argument_group('cgxsh_generic_ws args', 'CGXSH Generic WebSocket Client Arguments')
    cgxsh_group.add_argument('--no-format', "-NF", help="Disable output pretty-printing/formatting.",
                             action='store_false', default=True)
    cgxsh_group.add_argument('--show-keepalives', help="Show background keepalive messages",
                             action='store_true', default=False)
    cgxsh_group.add_argument("--controller-email", "-E", help="Use this email for controller login.",
                             default=None)
    cgxsh_group.add_argument("--controller-password", help="Use this password for controller login. "
                                                           "NOT RECOMMENDED - Password will likely be stored "
                                                           "in shell history.",
                             default=None)
    cgxsh_group.add_argument('[@client]', nargs='?',
                             type=str, help="If connecting as ESP/MSP account, @client name or ID is required.",
                             default="@")

    login_group = parser.add_argument_group('Controller Options', 'These options change how the program connects to the'
                                                                  ' CloudGenix Controller')
    login_group.add_argument("--controller", "-C",
                             help="Override Controller API URI. Default: https://api.elcapitan.cloudgenix.com",
                             default=None)
    login_group.add_argument("--insecure", "-I", help="Do not verify API SSL certificate",
                             action='store_true',
                             default=False)
    login_group.add_argument("--noregion", "-NR", help="Ignore Region-based redirection.",
                             dest='ignore_region', action='store_true', default=False)

    login_group.add_argument("--override-host-header", "-OH", help="Force Host Header on API requests.",
                             dest='force_host', type=str, default=None)

    debug_group = parser.add_argument_group('Debug', 'These options enable debugging output')
    debug_group.add_argument('--verbosity', "-V", type=int, default=0, help="CGXSH Generic WebSocket Client verbosity.")
    debug_group.add_argument("--sdkdebug", "-D", help="Enable CloudGenix SDK Debug output, levels 0-3", type=int,
                             default=0)

    args = vars(parser.parse_args())

    # save the current sdkdebug and verbosity state
    CGXSH_VERBOSITY_LEVEL = args['verbosity']
    SDKDEBUG_LEVEL = args['sdkdebug']

    # Set verbosity first thing.
    cgxsh_verbosity(CGXSH_VERBOSITY_LEVEL)

    # Load config from home directory file (~/CONFIG_DIR/CONFIG_YAML).
    LOADED_CONFIG = config_read_write_default()
    cgxsh_logger.debug(f"LOADED_CONFIG: {safe_log_config(LOADED_CONFIG)}")

    # to re-use the cgx_sdk_login function, add the cgxsh arg format to args along with blank device_user/pw.
    cgxsh_logger.debug(f"CLIENT: {args['[@client]']}")
    if args['[@client]'][0] == '@':
        args['element[@client]'] = args['[@client]']
    else:
        args['element[@client]'] = '@' + args['[@client]']
    args['device_user'] = None
    args['device_password'] = None

    # log in to Controller/Client, read device_user and device_password from config/cmdline.
    sdk, element_string, device_user, device_password = cgx_sdk_login(args)

    # ignore the element string.

    # main loop - will use this in background thread
    loop = asyncio.new_event_loop()

    # Input asyncio queue
    input_queue = asyncio.Queue(loop=loop)

    # asyncio.Future callback for sending/killing the background thread, and sending a SIGINT or SIGTERM to the main
    # thread
    stop = loop.create_future()

    # Add the worker to the main loop - this will be launched in the background thread.
    asyncio.ensure_future(generic_worker(loop, input_queue, stop, sdk, pretty_print=args['no_format'],
                                         show_keepalives=args['show_keepalives']),
                          loop=loop)

    # Start the loop in the background thread.
    thread = threading.Thread(target=loop.run_forever)
    thread.start()

    # Main loop
    try:
        while True:
            # get the input from client
            message = input("\u001b[31m> \u001b[0m")
            # put it on the output bus
            loop.call_soon_threadsafe(input_queue.put_nowait, message)

    except (KeyboardInterrupt, EOFError):
        cgxsh_logger.debug("Got SIGINT")
        loop.call_soon_threadsafe(stop.set_result, None)

    # destroy queues
    del input_queue
    del stop

    # Wait for the event loop to terminate.
    thread.join()

    # Clean up any hanging tasks due to exceptions (eg, websockets)
    tasks = asyncio.all_tasks(loop)
    leftover_tasks = {task for task in tasks}
    # flag leftover tasks for cancellation
    if leftover_tasks:
        for task in leftover_tasks:
            cgxsh_logger.debug(f"Pending task at exit: {task}, {type(task)}. Will cancel.")
            task.cancel()
        # run and close the loop to end and flush.
        try:
            loop.run_until_complete(asyncio.gather(*leftover_tasks))
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()


def toolkit_client():
    """
    Launch the Element Websocket Troubleshooting Toolkit Client
    :return: None
    """
    global LOADED_CONFIG
    global SDKDEBUG_LEVEL
    global CGXSH_VERBOSITY_LEVEL
    global CONNECTING_ELEMENT_ID

    if sys.platform == "win32":
        try:
            # attempt to use websockets.__main__ Windows VT100 mode
            win_enable_vt100()
        except RuntimeError as e:
            sys.stderr.write(f"Unable to set terminal to VT100 mode. Rendering may be inconsistent.\n"
                             f"Details: {e}\n")
            sys.stderr.flush()

    # Parse arguments
    parser = argparse.ArgumentParser(description="{0} ({1})".format('cgxsh', __version__))

    cgxsh_group = parser.add_argument_group('cgxsh_args', 'CGXSH Arguments')
    cgxsh_group.add_argument("--controller-email", "-E", help="Use this email for controller login.",
                             default=None)
    cgxsh_group.add_argument("--controller-password", help="Use this password for controller login. "
                                                           "NOT RECOMMENDED - Password will likely be stored "
                                                           "in shell history.",
                             default=None)
    cgxsh_group.add_argument('--device-user', help="Use this user to login to the Element Toolkit.",
                             default=None)
    cgxsh_group.add_argument('--device-password', help="Use this password to login to the Element Toolkit. "
                                                       "NOT RECOMMENDED - Password will likely be stored "
                                                       "in shell history.",
                             default=None)
    cgxsh_group.add_argument("--noexit", help="If using commands, do not exit after running commands. Maintain "
                                              "interactive shell.",
                             action='store_true',
                             default=False)
    # Positional Arguments
    cgxsh_group.add_argument('element[@client]', type=str, help="Element name or ID to connect to. If connecting as "
                                                                "ESP/MSP account, @client name or ID is required.")

    cgxsh_group.add_argument('commands', type=str, help="(Optional) Strings of space-separated Toolkit commands to run."
                                                        " Example: \"set paging off\" \"dump lldp all\"",
                             nargs=argparse.REMAINDER, default=[])

    login_group = parser.add_argument_group('Controller Options', 'These options change how the program connects to the'
                                                                  ' CloudGenix Controller')
    login_group.add_argument("--controller", "-C",
                             help="Override Controller API URI. Default: https://api.elcapitan.cloudgenix.com",
                             default=None)
    login_group.add_argument("--insecure", "-I", help="Do not verify API SSL certificate",
                             action='store_true',
                             default=False)
    login_group.add_argument("--noregion", "-NR", help="Ignore Region-based redirection.",
                             dest='ignore_region', action='store_true', default=False)

    login_group.add_argument("--override-host-header", "-OH", help="Force Host Header on API requests.",
                             dest='force_host', type=str, default=None)

    debug_group = parser.add_argument_group('Debug', 'These options enable debugging output')
    debug_group.add_argument('--verbosity', "-V", type=int, default=0, help="CGXSH client verbosity.")
    debug_group.add_argument("--sdkdebug", "-D", help="Enable CloudGenix SDK Debug output, levels 0-3", type=int,
                             default=0)

    args = vars(parser.parse_args())

    # check commands and noexit settings
    if args['noexit'] and len(args['commands']) < 1:
        # error, noexit can only be set when commands are used.
        parser.error("--noexit can only be set when commands are specified after element[@client].")

    # save the current sdkdebug and verbosity state
    CGXSH_VERBOSITY_LEVEL = args['verbosity']
    SDKDEBUG_LEVEL = args['sdkdebug']

    # Set verbosity first thing.
    cgxsh_verbosity(CGXSH_VERBOSITY_LEVEL)

    # Load config from home directory file (~/CONFIG_DIR/CONFIG_YAML).
    LOADED_CONFIG = config_read_write_default()
    cgxsh_logger.debug(f"LOADED_CONFIG: {safe_log_config(LOADED_CONFIG)}")

    # log in to Controller/Client, read device_user and device_password from config/cmdline.
    sdk, element_string, device_user, device_password = cgx_sdk_login(args)

    # eventually figure out element id here
    element_id = pick_element(element_string, sdk)
    CONNECTING_ELEMENT_ID = element_id

    # main loop - will use this in background thread
    loop = asyncio.new_event_loop()

    # Input asyncio queue
    input_queue = asyncio.Queue(loop=loop)

    # asyncio.Future callback for sending/killing the background thread, and sending a SIGINT or SIGTERM to the main
    # thread
    stop = loop.create_future()

    # Create a pause queue to tell the background thread to stop processing the websocket temporarily.
    pause_queue = asyncio.Queue(loop=loop)

    # Add the worker to the main loop - this will be launched in the background thread.
    asyncio.ensure_future(toolkit_worker(loop, input_queue, stop, pause_queue, element_id, sdk,
                                         element_user=device_user, element_password=device_password,
                                         noexit=args['noexit'], commands=args['commands']), loop=loop)

    # Start the loop in the background thread.
    thread = threading.Thread(target=loop.run_forever)
    thread.start()

    # main loop will run as an inner function.
    def inner_main_loop():
        """
        Nested inner function for the main loop. Allows RETURN to break out of main loop at any time, without
        needing to pass all of the toolkit_client variables.
        :return: Used as full loop break
        """
        global LOADED_CONFIG
        global SDKDEBUG_LEVEL
        global CGXSH_VERBOSITY_LEVEL
        while True:
            # get the input from client on a per-keypress basis
            message = getch()
            # check for escape char, if so launch menu.
            if message == ESCAPE_CHAR:
                # Interactive interrupt menu.
                # Pause the socket output. True in the queue = Pause
                loop.call_soon_threadsafe(pause_queue.put_nowait, True)

                exit_menu_shell = False
                # loop here until command shell exit request.
                while not exit_menu_shell:
                    eventual_message = None
                    message_info = None
                    command_response = CgxshMenu().cmdloop(cgx_sdk=sdk)

                    if command_response == 'escape':
                        # send escape char
                        eventual_message = ESCAPE_CHAR
                        message_info = f"Sending escape char " \
                                       f"({DEFAULT_CONTROL_CHAR_DICT.get(ESCAPE_CHAR, repr(ESCAPE_CHAR))}).\n"
                        # set exit_menu_shell
                        exit_menu_shell = True

                    elif 'sdkdebug' in command_response:
                        # Set SDK Debug. Level will be to the right of 'sdkdebug' string.
                        SDKDEBUG_LEVEL = int(command_response.lstrip('sdkdebug'))
                        sdk.set_debug(SDKDEBUG_LEVEL)
                        message_info = f"CloudGenix SDK debug set to {SDKDEBUG_LEVEL}."
                        exit_menu_shell = False

                    elif 'verbosity' in command_response:
                        # Set cgxsh verbosity. Level will be to the right of 'verbosity' string.
                        CGXSH_VERBOSITY_LEVEL = int(command_response.lstrip('verbosity'))
                        cgxsh_verbosity(CGXSH_VERBOSITY_LEVEL)
                        message_info = f"Cgxsh verbosity set to {CGXSH_VERBOSITY_LEVEL}."
                        # set exit_menu_shell
                        exit_menu_shell = False

                    elif command_response == 'quit':
                        # set exit_menu_shell
                        exit_menu_shell = True
                        # Gracefully shut down
                        loop.call_soon_threadsafe(stop.set_result, None)
                        # Exit program completely.
                        return

                    elif command_response == 'continue':
                        # set exit_menu_shell
                        exit_menu_shell = True

                    if eventual_message or message_info:
                        # print info text if it exists
                        if message_info:
                            direct_print(message_info)
                        # send the menu-generated message
                        if eventual_message:
                            loop.call_soon_threadsafe(input_queue.put_nowait, eventual_message)

                    # Check for exit at end of loop. If set, break now. Don't wait for another loop.
                    if exit_menu_shell:
                        break

                # unpause the output:
                loop.call_soon_threadsafe(pause_queue.put_nowait, False)

            else:
                # normal keypress - send.
                loop.call_soon_threadsafe(input_queue.put_nowait, message)

    # Main loop
    try:
        inner_main_loop()

    except (KeyboardInterrupt, EOFError):
        cgxsh_logger.debug("Got SIGINT")
        # If we get a Interrupt or a EOFError from the socket, activate the stop callback
        loop.call_soon_threadsafe(stop.set_result, None)

    # destroy queues and callbacks
    del input_queue
    del pause_queue
    del stop

    # Wait for the event loop to terminate.
    thread.join()

    # Clean up any hanging tasks due to exceptions (eg, websockets)
    tasks = asyncio.all_tasks(loop)
    leftover_tasks = {task for task in tasks}
    # flag leftover tasks for cancellation
    if leftover_tasks:
        for task in leftover_tasks:
            cgxsh_logger.debug(f"Pending task at exit: {task}, {type(task)}. Will cancel.")
            task.cancel()
        # run and close the loop to end and flush.
        try:
            loop.run_until_complete(asyncio.gather(*leftover_tasks))
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

# Exceptions


class CgxshGeneralError(Exception):
    """
    Catch-all Exception
    """
    pass


class CgxshControllerLoginError(Exception):
    """
    Issue logging into controller
    """
    pass


class CgxshControllerClientLoginError(Exception):
    """
    Issue logging into client from ESP/MSP account
    """
    pass


class CgxshElementSelectionError(Exception):
    """
    Issue selecting an element(device).
    """
    pass
