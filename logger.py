# coding: UTF-8
#
# TileCutter debugger window
#

# To use:
# import logger
# debug = logger.Log()
#
# Then debug(<string to output>)
# Time/newline added automatically

import config
config = config.Config()

from datetime import datetime as dt

class Log(object):
    """Debug/log output to file"""
    file = None
    line_number = 0
    newline = True
    def __init__(self, file=None):
        """"""
        if Log.file == None:
            if file == None:
                # Appends this session's log info to the logging file
                Log.file = open(config.logfile, "a")
            else:
                Log.file = open(file, "a")
    def __call__(self, s):
        """Calls self.write()"""
        self.out(s)
    def out(self, s):
        """Write a string to file, stripping newlines and reformatting"""
        outline = dt.now().replace(microsecond=0).isoformat(" ") + " |    " + s + "\n"
        Log.file.write(outline)
        Log.file.flush()
    def write(self, s):
        """Write a string to file, preserving newlines fed in"""
        # Check string, if it's entirely whitespace or just a newline, or blank do nothing
        # Prepend current time/date, append newline
        if self.newline:
            outline = dt.now().replace(microsecond=0).isoformat(" ") + " |    " + s
        else:
            outline = s
        # Check if next line will need the date prepending
        if s[-1] == "\n":
            self.newline = True
        else:
            self.newline = False
        Log.file.write(outline)
        Log.file.flush()

