#!/usr/bin/python
# coding: UTF-8
#
# TileCutter, version 0.5
#

# Copyright © 2008-2011 Timothy Baldock. All Rights Reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. The name of the author may not be used to endorse or promote products derived from this software without specific prior written permission from the author.
#
# 4. Products derived from this software may not be called "TileCutter" nor may "TileCutter" appear in their names without specific prior written permission from the author.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. 

# First thing imported is logger, so that other imports can use logging too
import logger
debug = logger.Log()

import sys, os

try:
    import wx
    debug(u"main: WX version is: %s" % wx.version())
except ImportError:
    debug(u"main: WXPython not installed, please install module and try again!")
    raise

import pickle
import tcui, tc, imres, codecs
import project
from optparse import OptionParser

# Classes to read/write TileCutter files
from tcp import tcp_writer
from tcp import tcp_reader

# Utility functions
import translator
gt = translator.Translator()
# _gt() used where class needs to be fed untranslated string, but we still want TCTranslator
# script to pick it up for the translation file
_gt = gt.loop

import config
config = config.Config()
config.save()

debug(u"main: configuration source is %s" % config.source)
debug(u"main: configuration loaded from file: %s" % config.conf_path)
debug(unicode(config))

class App(wx.App):
    """The main application, pre-window launch stuff should go here"""
    def __init__(self, gui):
        self.gui = gui
        self.start_directory = os.getcwdu()
        wx.App.__init__(self)
        # Catch activate events from other applications (OSX)
        self.Bind(wx.EVT_ACTIVATE_APP, self.OnActivate)

    def OnInit(self):
        """Called after app has been initialised"""
        # Wx also overrides stderr/stdout, override this
        if self.gui:
            sys.stderr = debug
            sys.stdout = debug
        else:
            sys.stderr = sys.__stderr__
            sys.stdout = sys.__stdout__

        debug(u"App: OnInit - Starting...")
        self.start_directory = os.getcwd()

        # Create a default active project
        debug(u"App: OnInit - Create default project")
        self.projects = {}
        self.projects["default"] = project.Project(self)
        self.activeproject = self.projects["default"]
        self.update_title_text()

        if self.gui:
            debug(u"App: OnInit - Create + Show main frame")
            # Create and show main frame
            self.frame = tcui.MainWindow(None, self, wx.ID_ANY, "TileCutter")
            self.SetTopWindow(self.frame)

            debug(u"App: OnInit - Bind Quit Event")
            # Bind quit event
            self.frame.Bind(wx.EVT_CLOSE, self.OnQuit)
            self.frame.Bind(wx.EVT_CLOSE, self.OnQuit)

            debug(u"App: OnInit - Init window sizes")
            # Window inits itself to its minimum size
            # If a larger size is specified in config, set to this instead
            if config.window_size[0] > self.frame.GetBestSize().GetWidth() and config.window_size[1] > self.frame.GetBestSize().GetHeight():
                self.frame.SetSize(config.window_size)
            else:
                # Otherwise just use the minimum size
                self.frame.Fit()
            debug(u"App: OnInit - Init window position")
            # If a window position is saved, place the window there
            if config.window_position != [-1,-1]:
                self.frame.SetPosition(config.window_position)
            else:
                # Otherwise center window on the screen
                self.frame.CentreOnScreen(wx.BOTH)
        else:
            debug(u"App: OnInit - Command line mode, not creating GUI")

        debug(u"App: OnInit - Completed!")
        return True


    # Mac-specific stuff
    def OnActivate(self, e):
        # if this is an activate event, rather than something else, like iconize.
        if e.GetActive():
            self.BringWindowToFront()
        e.Skip()
    def BringWindowToFront(self):
        try: # it's possible for this event to come when the frame is closed
            self.GetTopWindow().Raise()
        except:
            pass
    def MacOpenFile(self, filename):
        """Called for files droped on dock icon, or opened via finders context menu"""
        debug(u"App: MacOpenFile - %s dropped on app" % (filename))
        self.OnLoadProject(filename)
    def MacReopenApp(self):
        """Called when the doc icon is clicked, and for other reasons that need to focus the application"""
        self.BringWindowToFront()


    # Called by the currently active project
    def project_has_changed(self):
        """Whenever the active project changes, this function is called"""
        # If it has, update the title text
        if self.gui:
            self.update_title_text()
            self.frame.set_title()
            # On Mac OSX due to bug with wx 2.8 we need to refresh the display window
            # this is due to the SetTitle method forcibly refreshing all child windows
            self.frame.update()

    # Functions concerning the title text of the program window
    def get_title_text(self):
        """Get a string to use for the window's title text"""
        return self.title_text
    def update_title_text(self):
        """Updates the title text with the details of the currently active project"""
        debug(u"App: update_title_text")
        if self.activeproject.saved():
            # Project has been previously saved
            if self.activeproject.has_changed():
                # Project has changed but was previously saved
                # Title string will be *FileName.tcp - TileCutter
                self.title_text = "*%s - %s" % (self.activeproject.save_location(), "%s")
            else:
                # Project hasn't changed and is saved
                # Title string will be FileName.tcp - TileCutter
                self.title_text = "%s - %s" % (self.activeproject.save_location(), "%s")
        else:
            # Project hasn't been saved before
            if self.activeproject.has_changed():
                # Unsaved, but changed
                # Title string will be *(New Project) - TileCutter
                self.title_text = "*(%s) - %s" % (_gt("New Project"), "%s")
            else:
                # Unsaved and unchanged
                # Title string will be (New Project) - TileCutter
                self.title_text = "(%s) - %s" % (_gt("New Project"), "%s")
        debug(u"App: update_title_text - Setting title_text to: %s" % (self.title_text % _gt("TileCutter")))

    def set_status_text(self, message, field=0):
        """Updates the status bar text field specified with the message specified"""
        self.frame.set_status_text(message, field)

    # Method to invoke cutting engine on a particular project
    def export_project(self, project, pak_output=False, return_dat=None, write_dat=None):
        """Trigger exporting of specified project"""
        if return_dat is None:
            return_dat = not config.write_dat
        if write_dat is None:
            write_dat = config.write_dat
        # First trigger project to generate cut images
        project.cut_images(tc.export_cutter)
        # Then feed project into outputting routine
        # Will need a way to report back progress to a progress bar/indicator
        ret = tc.export_writer(project, pak_output, return_dat, write_dat)
        if self.gui and ret != True:
            # Pop up a modal dialog box to display the .dat file info
            pass

    # Dialogs involved in loading/saving
    def dialog_save_changes(self, project):
        """Prompts user to save file, return wx.ID_YES, wx.ID_NO or wx.ID_CANCEL"""
        debug(u"App: dialog_save_changes")
        dlg = wx.MessageDialog(self.frame, gt("Save changes before proceeding?"),
                               gt("Current project has changed"),
                               style=wx.YES_NO|wx.CANCEL|wx.YES_DEFAULT|wx.ICON_QUESTION)
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_YES:
            debug(u"App: dialog_save_changes - Result YES")
        if result == wx.ID_NO:
            debug(u"App: dialog_save_changes - Result NO")
        if result == wx.ID_CANCEL:
            debug(u"App: dialog_save_changes - Result CANCEL")
        return result
    def dialog_save_location(self, project):
        """Prompts user to select a location to save project to, returns True if location picked,
        False if cancelled. Sets project's save location to result file"""
        debug(u"App: dialog_save_location - Grabbing save path from dialog")
        filesAllowed = "TileCutter Project files (*.tcp)|*.tcp"
        dialogFlags = wx.FD_SAVE|wx.OVERWRITE_PROMPT
        path = os.path.split(project.save_location())[0]
        filename = os.path.split(project.save_location())[1]
        dlg = wx.FileDialog(self.frame, gt("Choose a location to save to..."),
                            path, filename, filesAllowed, dialogFlags)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            #project.save_location(os.path.join(dlg.GetDirectory(), dlg.GetFilename()))
            project.save_location(dlg.GetPath())
            config.last_save_path = dlg.GetDirectory()
            debug(u"App: dialog_save_location - New save_location for project is: %s" % project.save_location())
            dlg.Destroy()
            return True
        else:
            # Else cancel was pressed, do nothing
            debug(u"App: dialog_save_location - User cancelled save_location Dialog")
            dlg.Destroy()
            return False
    def dialog_load(self):
        """Prompts user to select a location to load a project file from, returns filename or wx.ID_CANCEL"""
        debug(u"App: dialog_load - Opening Load Dialog to allow location picking")
        filesAllowed = "TileCutter Project files (*.tcp)|*.tcp"
        dialogFlags = wx.FD_OPEN|wx.FD_FILE_MUST_EXIST
        # This probably needs to be more robust
        path = os.path.split(self.activeproject.save_location())[0]
        file = os.path.split(self.activeproject.save_location())[1]
        dlg = wx.FileDialog(self.frame, gt("Choose a project file to open..."),
                            path, file, filesAllowed, dialogFlags)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            debug(u"App: dialog_load - directory: %s, filename: %s" % (dlg.GetDirectory(), dlg.GetFilename()))
            #load_location = os.path.join(dlg.GetDirectory(), dlg.GetFilename())
            load_location = dlg.GetPath()
            dlg.Destroy()
            debug(u"App: dialog_load - User picked location: %s" % load_location)
            return load_location
        else:
            # Else cancel was pressed, do nothing
            dlg.Destroy()
            debug(u"App: dialog_load - User cancelled location picking")
            return False


    # Methods for loading/saving projects

    def save_project(self, project):
        """Save project to its save location, returns True if success, False if failed"""
        debug(u"App: save_project - Save project out to disk")

        # Create new writer
        t_writer = tcp_writer(self.activeproject.save_location(), "json")

        # Write out project
        ret = t_writer.write(project)

        # If saving worked, update current status
        if ret:
            project.saved(ret)
            project.update_hash()

            # Update frame to reflect change to active project
            if self.gui:
                self.frame.update()
                self.project_has_changed()
                self.set_status_text(gt("Project was saved successfully"))
            debug(u"App: save_project - save_project - Save project success")
            return True
        else:
            # Saving failed for some reason
            debug(u"App: save_project - ERROR: save_project - Saving failed!")
            if self.gui:
                self.set_status_text(gt("ERROR: Failed to save project!"), 0)
                dlg = wx.MessageDialog(None, "Error saving file, please see log file for details", "Error", wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            return False

    def load_project(self, location):
        """Load a project based on a file location"""
        debug(u"App: load_project - Load project from file: %s" % location)

        t_reader = tcp_reader(location)

        # Load project, passing reference to self which will be set as project's parent in its post_serialisation method
        project = t_reader.load([self,])

        if project == False:
            debug(u"App: load_project - ERROR: load_project - Loading failed!")
            if self.gui:
                self.set_status_text(gt("ERROR: Failed to load project!"), 0)
                dlg = wx.MessageDialog(None, "Error loading file, please see log file for details", "Error", wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
            # Project loading has failed, abort
            return False

        # Check parent after
        debug(u"App: load_project - after - parent of project: %s is: %s" % (str(project), str(project.parent)))

        self.activeproject = project
        if self.gui:
            self.frame.update()
            self.project_has_changed()
            self.set_status_text(gt("Project was loaded successfully"), 0)
        debug(u"App: load_project - Load Project succeeded")
        return True

    def new_project(self):
        """Create a new project"""
        debug(u"App: new_project - Create new project")
        self.activeproject = project.Project(self)
        # Finally update the frame to display changes
        if self.gui:
            self.frame.update()
            self.project_has_changed()
            self.set_status_text(gt("New project created"), 0)
        debug(u"App: new_project - Complete!")

    def OnNewProject(self):
        """Init process of starting a new project"""
        debug(u"App: OnNewProject")
        project = self.activeproject
        if self.activeproject.has_changed():
            ret = self.dialog_save_changes(project)
            if ret == wx.ID_YES:
                if not project.saved():
                    if not self.dialog_save_location(project):
                        return False
                if not self.save_project(project):
                    return False
            elif ret == wx.ID_CANCEL:
                return False
        self.new_project()

    def OnLoadProject(self, loadpath=None):
        """Init process of loading a project from file, if optional savepath is specified then skip the load file dialog"""
        debug(u"App: OnLoadProject")
        project = self.activeproject
        if self.activeproject.has_changed():
            ret = self.dialog_save_changes(project)                 # Prompt to save project
            if ret == wx.ID_YES:                                    # If answer is yes
                if not project.saved():                             #  Check if file has a save location
                    if not self.dialog_save_location(project):      #  If it doesn't, prompt user for one
                        return False                                #  If user cancels, quit out
                if not self.save_project(project):                  #  Otherwise save the project
                    return False                                    # If project saving fails abort loading or we'd lose changes
            elif ret == wx.ID_CANCEL:                               # If answer is no
                return False                                        # Quit out
            # else ret is wx.ID_NO, so we don't want to save but can continue
        if loadpath is None:                                        # Check if a load path was passed into this function
            loadpath = self.dialog_load()                           # If not prompt for file to load
        if loadpath != wx.ID_CANCEL and loadpath != False:          # If user picked a file and didn't cancel the dialog
            debug(u"App: OnLoadProject - Load dialog returned a path: %s" % loadpath)
            return self.load_project(loadpath)                      # Load the project (returns project object or False depending on success)
        else:                                                       # Otherwise
            return False                                            # Quit out

    def OnSaveProject(self, project):
        """Init process of saving a project to file"""
        debug(u"App: OnSaveProject")
        if project.saved():
            return self.save_project(project)                       # Returns True on save success, False on failure
        else:
            if self.dialog_save_location(project):
                return self.save_project(project)                   # Returns True on save success, False on failure
            return False
        # Project already saved
        return True

    def OnSaveAsProject(self, project):
        """Init process of saving a project to a new location"""
        debug(u"App: OnSaveAsProject")
        if self.dialog_save_location(project):
            return self.save_project(project)
        return False



    def Exit(self):
        """Quit the application indirectly"""
        debug(u"App: Exit -> self.OnQuit()")
        self.OnQuit(None)

    def OnQuit(self, e):
        """Close all windows and quit the application on a quit event in the main window"""
        debug(u"App: OnQuit - Application quitting...")
        debug(u"App: OnQuit - Saving current application window size (%s) to config file" % unicode(self.frame.GetSizeTuple()))
        config.window_size = self.frame.GetSizeTuple()
        debug(u"App: OnQuit - Saving current application window position (%s) to config file" % unicode(self.frame.GetPositionTuple()))
        config.window_position = self.frame.GetPositionTuple()
        debug(u"App: OnQuit - Destroying frame...")
        self.frame.Destroy()
        debug(u"App: OnQuit - End")



def run():
    """Initialise the application in either GUI or CLI mode"""
    # Create app, but don't show the frame if command line being used
    # For each file in the input list, load the file (abort if load fails),
    # then do a standard export, plus compilation if needed
    # If any override flags are set, modify the output paths of the project before continuing

    # Command line arguments could indicate files to open (if they are the only things)
    # Use of the "-c" option will invoke the CLI operation mode
    debug(u"main: run - sys.argv says: %s" % sys.argv)
    # Parse command line arguments (if any)
    usage = "usage: %prog [options] filename1 [filename2 ... ]"
    parser = OptionParser(usage=usage)

    parser.set_defaults(pak_output=False, dat_output=True, cli=False)

    parser.add_option("-c", action="store_true", dest="cli",
                      help="run program in CLI mode (must be specified or program will run in GUI mode and load the first file specified on the command line)")

    parser.add_option("-i", dest="png_directory",
                      help="override .png file output location to DIRECTORY", metavar="DIRECTORY")
    parser.add_option("-I", dest="png_filename",
                      help="override .png file output name to FILENAME", metavar="FILENAME")

    parser.add_option("-n", action="store_false", dest="dat_output",
                      help="disable .dat file output (if -m specified, dat info will be output to tempfile)")
    parser.add_option("-d", dest="dat_directory",
                      help="override .dat file output location to DIRECTORY", metavar="DIRECTORY")
    parser.add_option("-D", dest="dat_filename",
                      help="override .dat file output name to FILENAME", metavar="FILENAME")

    parser.add_option("-m", action="store_true", dest="pak_output",
                      help="enable .pak file output (requires Makeobj)")
#        parser.add_option("-M", dest="makeobj_directory",
#                          help="override object specific makeobj with PATH", metavar="PATH")
    parser.add_option("-p", dest="pak_directory",
                      help="override .pak file output location to DIRECTORY", metavar="DIRECTORY")
    parser.add_option("-P", dest="pak_filename",
                      help="override .pak file output name to FILENAME", metavar="FILENAME")

    parser.add_option("-v", action="store_true", dest="verbose",
                      help="enable verbose output")
    parser.add_option("-q", action="store_false", dest="verbose",
                      help="suppress stdout")

    # options are the defined options, args are the list of files to process
    options, args = parser.parse_args()

    start_directory = os.getcwd()

    # Use of command line argument "-c" disables GUI and uses command line parsing instead
    if options.cli:
        # Create the application without GUI
        debug(u"main: run - Init - Creating app without GUI")
        app = App(gui=False)
        # Not making use of app's event handling loop etc., so don't start it
        #app.MainLoop()

        if options.verbose is True:
            print "options: %s" % str(options)
            print "args: %s" % str(args)
        # Another good option would be to support "stub" datfiles
        # produced as part of a pakset, which would have some kind of
        # marker to allow inserting the image array matrix in a particular location

        # Check through all args for directories, and expand these to list
        # all contained .tcp files for processing

        for file in args:
            if options.verbose is not False:
                print "processing file: %s" % file
            # For every filename specified by the user, perform export
            # Try to load in project, if this fails skip this filename and print an error
            if app.load_project(file):
                if options.verbose is not False:
                    print "loaded file, preparing to export"
                # Apply any command line overrides specified by user
                # For PNG file
                if options.png_directory is not None:
                    png_dir = options.png_directory
                else:
                    png_dir = os.path.split(app.activeproject.pngfile_location())[0]
                if options.png_filename is not None:
                    png_file = options.png_filename
                else:
                    png_file = os.path.split(app.activeproject.pngfile_location())[1]
                app.activeproject.pngfile(os.path.join(png_dir, png_file))
                # For DAT file
                if options.dat_directory is not None:
                    dat_dir = options.dat_directory
                else:
                    dat_dir = os.path.split(app.activeproject.datfile_location())[0]
                if options.dat_filename is not None:
                    dat_file = options.dat_filename
                else:
                    dat_file = os.path.split(app.activeproject.datfile_location())[1]
                app.activeproject.datfile(os.path.join(dat_dir, dat_file))
                # For PAK file
                if options.pak_directory is not None:
                    pak_dir = options.pak_directory
                else:
                    pak_dir = os.path.split(app.activeproject.pakfile_location())[0]
                if options.pak_filename is not None:
                    pak_file = options.pak_filename
                else:
                    pak_file = os.path.split(app.activeproject.pakfile_location())[1]
                app.activeproject.pakfile(os.path.join(pak_dir, pak_file))

                app.export_project(app.activeproject, pak_output=options.pak_output, return_dat=False, write_dat=options.dat_output)
                if options.verbose is not False:
                    print "...Done!"
            else:
                if options.verbose is not False:
                    print "loading file failed, skipping: %s" % file

        # Finally destroy app
        app.Destroy()
    else:
        # Create the application with GUI
        # Redirect stdout/err to internal logging mechanism
        # Only do this redirection if running in GUI mode
        # Needs tweaks to the debug module for -q option etc., different logging levels?
        debug(u"main: run - options: %s" % str(options))
        debug(u"main: run - args: %s" % str(args))
        sys.stderr = debug
        sys.stdout = debug
        # Create the application with GUI
        debug(u"main: run - Init - Creating app with GUI")
        app = App(gui=True)

        # If a project was specified on the command line, open it for editing (open the first one)
        if len(args) > 0:
            debug(u"main: run - Activating load_project based on CLI args (in GUI mode)")
            app.load_project(args[0])

        # Init all main frame controls
        app.frame.update()
        # Show the main window frame
        app.frame.Show(1)
        # Launch into application's main loop
        app.MainLoop()
        app.Destroy()



if __name__ == "__main__":
    run()

# BackImage[direction][ydim][xdim][zdim][frame][season]=path.ypos.xpos

