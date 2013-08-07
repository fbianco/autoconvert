#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    \package autoconvert

    \file autoconvert.py
    \author François Bianco, University of Geneva - francois.bianco@unige.ch
    \date 2012.05.22
    \version 0.02

    \updates
        v0.01: 2012 fbianco, command line only
        v0.02: 2013 fbianco, adding a Qt Gui for non-geek users


    \mainpage Automatic convert STM data file with Vernissage and
              Gwyexport/Gwyddion

    \section Copyright

    Copyright (C) 2011 François Bianco, University of Geneva - francois.bianco@unige.ch

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import sys, os, re

from PyQt4 import Qt

debug = False

class InvalidFlag(Exception): pass

def _tr(s):
    """ Allow to implement a translation mechanism """
    return s

    
def build_command_list(cmd, flags='', arguments={}):

    command_list = [cmd,]

    try:
        argument = re.compile('^\{.*\}$')
        for flag in flags.split(' '):
            if argument.match(flag):
                if isinstance(arguments[flag], list):
                    command_list.extend(arguments[flag])
                else:
                    command_list.append(arguments[flag])
            else:
                command_list.append(flag)
    except KeyError:
        mb = Qt.QMessageBox()
        mb.setWindowTitle('Error')
        mb.setIcon(Qt.QMessageBox.Critical)
        mb.setText(_tr('Error malformed command string for %s,\n' \
                       'check flags %s' % (cmd, flags)))
        mb.exec_()
        raise InvalidFlag

    return command_list


class RetardedProcess(Qt.QProcess):
    """Implement a process class that can be started on will later."""

    def __init__(self, program=None, *args):
        """Program is a QStringList with program nam and arguments"""
        Qt.QProcess.__init__(self, *args)
        self.args = program

    def setArgs(self, args):
        """Args is a QStringList with program nam and arguments"""
        self.args = args

    def start(self):
        if debug:
            for s in self.systemEnvironment():
                print s

        if len(self.args)>1:
            super(RetardedProcess, self).start(self.args[0], self.args[1:])
        else:
            super(RetardedProcess, self).start(self.args[0])

            
class ProcessesQueue(Qt.QObject):
    """Implement a very basic process queue fro the many conversion
       processes."""

    def __init__(self, maxProcesses=2, *args):

        Qt.QObject.__init__(self, *args)

        self.maxProcesses = maxProcesses
        self.processesQueue = []
        self.running = 0

    def append(self,process):
        self.processesQueue.append(process)

        Qt.QObject.connect(process, Qt.SIGNAL("finished(int)"),
                           self.startNextProcess)
        Qt.QObject.connect(process, Qt.SIGNAL("finished(int)"),
                           self.countFinished)

    def startNextProcess(self):
        if len(self.processesQueue) == 0:
            return

        p = self.processesQueue.pop(0)
        self.running+=1
        p.start()

    def countFinished(self):

        self.running-=1
        if len(self.processesQueue) == 0 and self.running == 0:
            if debug: print 'Queue finished'
            self.emit(Qt.SIGNAL("finished()"))
        
    def start(self):

        if len(self.processesQueue) == 0:
            self.emit(Qt.SIGNAL("finished()"))
            
        for i in range(self.maxProcesses):
            self.startNextProcess()

    def stop(self):
        self.processesQueue = []


class DetailMessageBox(Qt.QMessageBox):
    """A message box to show the result of the launched process """

    def __init__(self, process, button, *args):

        Qt.QMessageBox.__init__(self, *args)
        self.setIcon(Qt.QMessageBox.Information)
        self.setWindowTitle(_tr('Details'))
        self.addButton(Qt.QMessageBox.Ok)
        self.setDefaultButton(Qt.QMessageBox.Ok)
        self.setText('...')
        self.setDetailedText('...')

        # Get the text edit out of the message box
        self.logTextEdit = self.children()[4].children()[2]
        horizontalSpacer = Qt.QSpacerItem(500, 0,
                           Qt.QSizePolicy.Minimum, Qt.QSizePolicy.Expanding)
        # Add a spacer to control the message box size
        layout = self.layout()
        layout.addItem(horizontalSpacer, layout.rowCount(), 0, 1,
                       layout.columnCount());

        self.button = button
        self.process = process
        self.log = Qt.QString()

    def readOutput(self):
        self.log.append(
            Qt.QString(unicode(self.process.readAllStandardOutput(),'utf-8',
                               errors='replace')))
        self.setDetailedText(self.log)
        self.logTextEdit.moveCursor(Qt.QTextCursor.End)

    def readErrors(self):
        self.log.append("error: " +
            Qt.QString(unicode(self.process.readAllStandardError(),'utf-8',
                               errors='replace')))
        self.setDetailedText(self.log)
        self.logTextEdit.moveCursor(Qt.QTextCursor.End)

    def showEvent(self, event):

        state = self.process.state()
        if state == Qt.QProcess.NotRunning:
            self.setText(_tr('Not running'))
        elif state == Qt.QProcess.Starting:
            self.setText(_tr('Starting'))
        elif state == Qt.QProcess.Running:
            self.setText(_tr('Running'))
            
        error = self.process.error()
        if error == Qt.QProcess.FailedToStart:
            self.setInformativeText(_tr('The process failed to start. Either ' \
'the invoked program is missing, or you may have insufficient permissions to ' \
'invoke the program.'))
        elif error == Qt.QProcess.Crashed:
            self.setInformativeText(_tr('The process crashed some time ' \
'after starting successfully.'))
        elif error == Qt.QProcess.Timedout:
            self.setInformativeText(_tr('The process timedout.'))
        elif error == Qt.QProcess.WriteError:
            self.setInformativeText(_tr('An error occurred when' \
'attempting to write to the process. For example, the process may not be' \
'running, or it may have closed its input channel.'))
        elif error == Qt.QProcess.ReadError:
            self.setInformativeText(_tr('An error occurred when' \
'attempting to read from the process. For example, the process may not be' \
'running.'))
        elif error == Qt.QProcess.UnknownError:
            self.setInformativeText(_tr('Check process output below.'))

        self.setDetailedText(self.log)
        self.logTextEdit.moveCursor(Qt.QTextCursor.End)

        super(DetailMessageBox, self).showEvent(event)


class StatusItem(Qt.QTableWidgetItem):
    """An item showing the state of the conversion process"""

    States = {'idle':0,'running':1,'error':2,'finished':3,'cancelled':4}

    def __init__(self, *args):

        Qt.QTableWidgetItem.__init__(self, *args)
        self.setIdle()

    def setState(self, s):
        self.state = StatusItem.States[s]

    def setIdle(self):
        self.setState('idle')
        self.setIcon(Qt.QIcon('img/idle.svgz'))
        self.setText(_tr('Idle'))

    def setStarted(self):
        if self.state == StatusItem.States['idle']:
            self.setState('running')
            self.setIcon(Qt.QIcon('img/running.svgz'))
            self.setText(_tr('Running'))

    def setFinished(self, exitCode):
        if self.state == StatusItem.States['running']:
            if exitCode == 0:
                self.setFinishedDone() # /!\ do not imply success of process
            else:
                self.setFinishedError()

    def setFinishedDone(self):
        self.setState('finished')
        self.setIcon(Qt.QIcon('img/done.svgz'))
        self.setText(_tr('Done'))

    def setFinishedError(self):
        self.setState('error')
        self.setIcon(Qt.QIcon('img/error.svgz'))
        self.setText(_tr('Error'))

    def setCanceled(self):
        if self.state == StatusItem.States['running'] or \
           self.state == StatusItem.States['idle'] :
            self.setState('cancelled')
            self.setIcon(Qt.QIcon('img/canceled.svgz'))
            self.setText(_tr('Canceled'))

    
class FolderLineEdit(Qt.QHBoxLayout):
    """ Helper class to create a Hlayout to edit folder path
        containing an edit line and a button """

    def __init__(self, parent=None, *args):

        Qt.QHBoxLayout.__init__( self, parent, *args)

        self.lineEdit = Qt.QLineEdit()
        b = Qt.QPushButton(Qt.QIcon('img/open.svgz'), _tr('Select folder'))
        Qt.QObject.connect( b, Qt.SIGNAL("clicked()"), self.selectFolder)

        self.addWidget(self.lineEdit)
        self.addWidget(b)

    def selectFolder(self):
        """ Open a file dialog to let the user choose its snapshot file. """

        folderName = Qt.QFileDialog.getExistingDirectory(self.lineEdit,
                        _tr("Select folder"), self.lineEdit.text())
        if folderName :
            self.lineEdit.setText(folderName)

    def setText(self, t):
        self.lineEdit.setText(t)

    def text(self):
        return self.lineEdit.text()


class PathLineEdit(Qt.QHBoxLayout):
    """ Helper class to create a Hlayout to edit executable path
        containing an edit line and a button """

    def __init__(self, parent=None, *args):

        Qt.QHBoxLayout.__init__(self, parent, *args)

        self.lineEdit = Qt.QLineEdit()
        b = Qt.QPushButton(Qt.QIcon('img/open.svgz'), _tr('Select exe'))
        Qt.QObject.connect( b, Qt.SIGNAL("clicked()"), self.selectExecutable)

        self.addWidget(self.lineEdit)
        self.addWidget(b)

    def selectExecutable(self):
        """ Open a file dialog to let the user choose its snapshot file. """

        executableName = Qt.QFileDialog.getOpenFileName(self.lineEdit,
                        _tr("Select executable"), self.lineEdit.text())
        if executableName :
            self.lineEdit.setText(executableName)

    def setText(self, t):
        self.lineEdit.setText(t)

    def text(self):
        return self.lineEdit.text()

        
class AutoconvertWindow(Qt.QMainWindow):
    """ Autoconvert window construct a widget with all input parameters
        and options for the conversion"""

    def __init__(self, application = None, *args) :
        """ Constructor : Application argument is used for connecting the
        quitAction to the quit slot of the application."""

        Qt.QMainWindow.__init__( self, *args )

        self.setWindowTitle( _tr('Autoconvert') )
        self.setWindowIcon( Qt.QIcon('img/icon.svgz') )

        # store the application for the quit action
        self.application = application

        widget = Qt.QWidget(self)
        layout = Qt.QFormLayout()
        widget.setLayout(layout)
        self.setCentralWidget(widget)


        self.inputFolder = FolderLineEdit()
        self.recursive = Qt.QCheckBox()

        self.vernissageOutFolder = FolderLineEdit()
        self.exportVernissage = Qt.QCheckBox()
        
        self.imageOutFolder = FolderLineEdit()
        self.exportImage = Qt.QCheckBox()

        self.startButton = Qt.QPushButton(Qt.QIcon('img/start.svgz'),
                                          _tr('Start'))
        Qt.QObject.connect(self.startButton, Qt.SIGNAL("clicked()"),
                           self.startConvert)
        
        layout.addRow(_tr('Input folder'), self.inputFolder)
        layout.addRow(_tr('Recursive'), self.recursive)
        layout.addRow(_tr('Vernissage output folder'), self.vernissageOutFolder)
        layout.addRow(_tr('Export data with Vernissage'), self.exportVernissage)
        layout.addRow(_tr('Image output folder'), self.imageOutFolder)
        layout.addRow(_tr('Export data to image files'), self.exportImage)

        separator = Qt.QFrame()
        separator.setFrameStyle(Qt.QFrame.HLine)
        layout.addRow(separator)

        layout.addRow(_tr("Start"), self.startButton)

        self.makeConfigWidget()
        self.makeOutputWidget()
        self.createActions()
        self.makeToolBars()
        self.makeMenuBars()
        self.readSettings()

        
    def closeEvent(self, event):
        self.confirmQuit(event)

        
    def confirmQuit(self, event=None):
        # do it only if we are not running processes
        # or if the user confirm the quit
        if self.startAct.isEnabled() or \
           Qt.QMessageBox.Yes == Qt.QMessageBox.warning(self, _tr("Confirm"),
                        _tr("There are running processes.\n" \
                            "Do you want to quit without finishing the"\
                            " file conversion ?"),
                        Qt.QMessageBox.Cancel | Qt.QMessageBox.Yes):
            self.cancelConvert()
            self.writeSettings()

            if event:
                event.accept()
            self.application.quit()


    def createActions(self):
        """ Create the widget's actions """

        self.quitAct = Qt.QAction(_tr("&Quit"), self)
        self.quitAct.setIcon(Qt.QIcon('img/quit.svgz'))
        Qt.QObject.connect(self.quitAct,
            Qt.SIGNAL("triggered()"), self.confirmQuit)
        self.quitAct.setShortcut( _tr('Ctrl+Q') )

        self.cancelAct = Qt.QAction(_tr("Stop"), self)
        self.cancelAct.setIcon(Qt.QIcon('img/stop.svgz'))
        Qt.QObject.connect(self.cancelAct,
            Qt.SIGNAL("triggered()"), self.cancelConvert)
        self.cancelAct.setEnabled(False)

        self.startAct = Qt.QAction( Qt.QIcon('img/start.svgz'),
            _tr('Start'), self )
        Qt.QObject.connect( self.startAct, Qt.SIGNAL( "triggered()" ),
            self.startConvert )

        self.configureAct = Qt.QAction(self)
        self.configureAct.setIcon( Qt.QIcon('img/config.svgz') )
        self.configureAct.setText( _tr('Show options') )
        Qt.QObject.connect( self.configureAct, Qt.SIGNAL( "triggered()" ),
            lambda: self.configWidget.setVisible(True) )

    def makeToolBars( self ) :
        """Create the toolbars """
        
        self.convertToolBar = Qt.QToolBar( _tr( "Convert" ) )
        self.convertToolBar.setObjectName( "Convert tools" )
        self.convertToolBar.addAction(self.startAct)
        self.convertToolBar.addAction(self.cancelAct)
        self.convertToolBar.addSeparator()
        self.convertToolBar.addAction(self.quitAct)

        self.addToolBar( Qt.Qt.TopToolBarArea, self.convertToolBar )


        self.configToolBar = Qt.QToolBar( _tr( "Configuration") )
        self.configToolBar.setObjectName( "Configuration tools" )
        self.configToolBar.addAction( self.configureAct )

        self.addToolBar( Qt.Qt.TopToolBarArea, self.configToolBar )


    def makeMenuBars( self ) :
        """Create the windows menus """

        self.convertMenu = self.menuBar().addMenu( _tr('Convert') )
        self.convertMenu.addAction(self.startAct)
        self.convertMenu.addAction(self.cancelAct)
        self.convertMenu.addSeparator()
        self.convertMenu.addAction( self.quitAct )

        self.configMenu = self.menuBar().addMenu( _tr('Configuration') )
        self.configMenu.addAction( self.configureAct )

    def makeOutputWidget(self):
        self.outputDock = Qt.QDockWidget()
        self.outputDock.setObjectName('outputdock')
        self.addDockWidget( Qt.Qt.BottomDockWidgetArea, self.outputDock )

        self.processesListWidget = Qt.QTableWidget(0, 5)
        self.processesListWidget.setHorizontalHeaderLabels(Qt.QStringList(
            [_tr('Process'), _tr('File/Folder'), _tr('Status'),
             _tr('Detail'), _tr('Force stop')]))
        self.outputLog = Qt.QPlainTextEdit()
        self.outputDock.setWidget(self.processesListWidget)
        self.outputDock.setVisible(True)
        
    def makeConfigWidget(self):
        """Create the configuration dock"""

        self.configWidget = Qt.QDialog()
        configLayout = Qt.QFormLayout(self.configWidget)

        self.vernissageCmd = PathLineEdit()
        self.vernissageFlags = Qt.QLineEdit()
        self.vernissageFlags.setToolTip( _tr("""
Synopsis: {-path path-spec | -file file-spec}[...]\n
          [-exporter plug-in]\n
          [-outdir path-spec]"""))
        self.vernissageExporter = Qt.QLineEdit()
        configLayout.addRow(_tr('Vernissage command path'), self.vernissageCmd)
        configLayout.addRow(_tr('Vernissage flags'), self.vernissageFlags)
        configLayout.addRow(_tr('Vernissage exporter'), self.vernissageExporter)

        separator = Qt.QFrame()
        separator.setFrameStyle(Qt.QFrame.HLine)
        configLayout.addRow(separator)
        
        self.gwyexportCmd = PathLineEdit()
        self.gwyexportFlags = Qt.QLineEdit()
        self.gwyexportFlags.setToolTip( _tr("""
Usage: gwyexport -o <output-path> [Options] <filenames>

Converts any readable SPM data file to png or jpg images.
Uses the Gwyddion libraries for fileopening and processing.
If --metadata is specified, additional information is written to a text file.

Options:
 -h, --help                  Print this help and terminate.
 -v, --version               Print version info and terminate.
 -s, --silentmode            Only filenames of created images printed.
 -o, --outpath <output-path> The path, where the exported files are saved.
                             If no path is specified images will be stored in
                             the current directory.
 -f, --format <format>       The export format either 'jpg' or 'png'.
 -m, --metadata              Will dump the metadata into a text file for each
                             channel. The metadata file will have the same
                             name and outpath as the image file.
 -fl, --filters <filters>    Specifies filters applied to each image.
                             <filters> is a list, separated by `;'.
                             Filters are processed in given order.
                             Filter can be:

                               pc        - Plane correct.
                               melc      - Median line correction.
                               sr        - Remove scars.
                               poly:x,y  - Polylevel with degrees x,y.
                               mean:x    - Mean filter of x pixel.
                               any:name  - Process module <name>
                                           will be executed.
                             Example: -filters pc;melc;poly:2,2;melc
 --defaultfilters            Uses a predefined filterlist.
                             Same as `--filters pc;melc;sr;melc;pc'
 -g, --gradient <gradient>   Name of the colorgradient to be used.
                             If no gradient given, the gwyddion-default
                             will be used.
 -c, --colormap <map>        Can be: [auto|full|adaptive] for the
                             respective mapping to colors. Default is
                             `adaptive'.
        """))
        configLayout.addRow(_tr('Gwyexport command path'), self.gwyexportCmd)
        configLayout.addRow(_tr('Gwyexport flags'), self.gwyexportFlags)


        self.gwyexportFormat = Qt.QComboBox()
        self.gwyexportFormat.addItems(Qt.QStringList(('jpg','png')))
        configLayout.addRow(_tr('Image format'), self.gwyexportFormat)

        self.gwyexportGradient = Qt.QComboBox()
        self.gwyexportGradient.addItems(Qt.QStringList(('gold',
                'gray', 'gwyddion', 'rust', 'warm', 'wrappmono', 'blue')))
        configLayout.addRow(_tr('Color gradient'), self.gwyexportGradient)
        
        self.gwyexportColormap = Qt.QComboBox()
        self.gwyexportColormap.addItems(Qt.QStringList(('auto',
                                         'adaptive','full')))
        configLayout.addRow(_tr('Color map'), self.gwyexportColormap)

        self.gwyexportFilters = Qt.QLineEdit()
        self.gwyexportFilters.setToolTip("""
Specifies filters applied to each image.
        <filters> is a list, separated by `;'.
        Filters are processed in given order.
        Filter can be:

        pc        - Plane correct.
        melc      - Median line correction.
        sr        - Remove scars.
        poly:x,y  - Polylevel with degrees x,y.
        mean:x    - Mean filter of x pixel.
        any:name  - Process module <name>
                    will be executed.
        Example: pc;melc;poly:2,2;melc""")
        configLayout.addRow(_tr('Filters'), self.gwyexportFilters)
        
        separator = Qt.QFrame()
        separator.setFrameStyle(Qt.QFrame.HLine)
        configLayout.addRow(separator)
        
        self.overwrite = Qt.QCheckBox()
        configLayout.addRow(_tr('Overwrite existing files'), self.overwrite)

        separator = Qt.QFrame()
        separator.setFrameStyle(Qt.QFrame.HLine)
        configLayout.addRow(separator)

        self.maxProcesses = Qt.QSpinBox()
        self.maxProcesses.setRange(1, 10)
        configLayout.addRow(_tr('Number of simultaneous process'),
                            self.maxProcesses)

        separator = Qt.QFrame()
        separator.setFrameStyle(Qt.QFrame.HLine)
        configLayout.addRow(separator)
        
        buttonBox = Qt.QDialogButtonBox()
        acceptButton = Qt.QPushButton(_tr('Close'))
        acceptButton.setDefault(True)
        resetButton = Qt.QPushButton(_tr('Reset default value'))
        buttonBox.addButton(resetButton, Qt.QDialogButtonBox.ResetRole)
        buttonBox.addButton(acceptButton, Qt.QDialogButtonBox.AcceptRole)

        Qt.QObject.connect(acceptButton, Qt.SIGNAL("clicked()"),
                           lambda: self.configWidget.setVisible(False))
        Qt.QObject.connect(resetButton, Qt.SIGNAL("clicked()"),
                            self.resetDefault)
        configLayout.addRow(buttonBox)


        self.configWidget.setLayout(configLayout)
        self.configWidget.setVisible(False)

    def resetDefault(self):

        settings = Qt.QSettings( "Autoconvert", "pref" )
        settings.clear()

        self.readSettings()
        
    def readSettings(self):
        """ Read the stored settings. """

        settings = Qt.QSettings( "Autoconvert", "pref" )
        self.restoreGeometry( settings.value( "windowGeometry" ).toByteArray() )
        self.outputDock.restoreGeometry(
                            settings.value("outputDockGeometry").toByteArray())
        self.processesListWidget.restoreGeometry(settings.value(
                            "processesListWidgetGeometry").toByteArray())
        self.restoreState( settings.value("windowState").toByteArray() )
        self.configWidget.restoreGeometry(
                        settings.value("configDialogGeometry").toByteArray())
        self.processesListWidget.horizontalHeader().restoreState(
                        settings.value("processesListWidth").toByteArray())

        self.inputFolder.setText(settings.value(
            "inputFolder", Qt.QVariant(Qt.QDir.home().path()) ).toString() )
        self.recursive.setChecked( settings.value("recursive",
             Qt.QVariant('False')).toBool() )

        self.vernissageOutFolder.setText(settings.value(
            "vernissageOutFolder", Qt.QVariant(Qt.QDir.home().path())
            ).toString() )
        self.exportVernissage.setChecked( settings.value("exportVernissage",
             Qt.QVariant('False')).toBool() )

        self.imageOutFolder.setText(settings.value(
            "imageOutFolder", Qt.QVariant(Qt.QDir.home().path()) ).toString() )
        self.exportImage.setChecked( settings.value("exportImage",
             Qt.QVariant('False')).toBool() )

        self.vernissageCmd.setText(settings.value("vernissageCmd",
             Qt.QVariant('C:\Program Files\Omicron ' \
                         'NanoTechnology\Vernissage' \
                         '\T2.1\Bin\VernissageCmd.exe') ).toString() )

        self.vernissageFlags.setText(settings.value("vernissageFlags",
             Qt.QVariant('-path {path} -outdir {outdir} ' \
                         '-exporter {exporter}')).toString() )
        self.vernissageExporter.setText(settings.value("vernissageExporter",
             Qt.QVariant('Flattener')).toString())

        self.gwyexportCmd.setText(settings.value("gwyexportCmd",
             Qt.QVariant('''c:\gwyexport\gwyexport.exe''') ).toString() )
        self.gwyexportFlags.setText(settings.value("gwyexportFlags",
             Qt.QVariant('-f {exportformat} -m -o {outputpath} ' \
                         '--filters {filterlist} --gradient {gradient} ' \
                         '--colormap {colormap} ' \
                         '{inputfolder}')).toString())

        self.gwyexportFormat.setCurrentIndex(self.gwyexportFormat.findText(
            settings.value("gwyexportFormat", Qt.QVariant('jpg')).toString()))
        self.gwyexportGradient.setCurrentIndex(
            self.gwyexportGradient.findText(
                settings.value("gwyexportGradient", Qt.QVariant('wrappmono')
                                ).toString()))
        self.gwyexportColormap.setCurrentIndex(
            self.gwyexportColormap.findText(
                settings.value("gwyexportColormap", Qt.QVariant('adaptive')
                                ).toString()))
        self.gwyexportFilters.setText(settings.value("gwyexportFilters",
               Qt.QVariant('pc;melc;sr;melc;pc') ).toString())
        self.maxProcesses.setValue(settings.value("maxProcesses",
                          Qt.QVariant(2)).toInt()[0])
        

    def writeSettings(self):
        """ Store the settings. """

        settings = Qt.QSettings( "Autoconvert", "pref" )
        settings.setValue("inputFolder", Qt.QVariant(self.inputFolder.text()))
        settings.setValue("recursive", Qt.QVariant(self.recursive.isChecked()))

        settings.setValue("vernissageOutFolder",
                            Qt.QVariant(self.vernissageOutFolder.text()))
        settings.setValue("exportVernissage",
                            Qt.QVariant(self.exportVernissage.isChecked()))

        settings.setValue("imageOutFolder",
                            Qt.QVariant(self.imageOutFolder.text()))
        settings.setValue("exportImage",
                            Qt.QVariant(self.exportImage.isChecked()))


        settings.setValue("vernissageCmd",
                            Qt.QVariant(self.vernissageCmd.text()))
        settings.setValue("vernissageFlags",
                            Qt.QVariant(self.vernissageFlags.text()))
        settings.setValue("vernissageExporter",
                            Qt.QVariant(self.vernissageExporter.text()))
                            
        settings.setValue("gwyexportCmd",
                            Qt.QVariant(self.gwyexportCmd.text()))
        settings.setValue("gwyexportFlags",
                            Qt.QVariant(self.gwyexportFlags.text()))
        settings.setValue("gwyexportFormat",
                            Qt.QVariant(self.gwyexportFormat.currentText()))
        settings.setValue("gwyexportGradient",
                        Qt.QVariant(self.gwyexportGradient.currentText()))
        settings.setValue("gwyexportColormap",
                        Qt.QVariant(self.gwyexportColormap.currentText()))
        settings.setValue("gwyexportFilters",
                        Qt.QVariant(self.gwyexportFilters.text()))
                        
        settings.setValue("windowGeometry", Qt.QVariant(self.saveGeometry()))
        settings.setValue("windowState", Qt.QVariant(self.saveState()))
        settings.setValue("outputDockGeometry",
                          Qt.QVariant(self.outputDock.saveGeometry()))
        settings.setValue("processesListWidgetGeometry",
                          Qt.QVariant(self.processesListWidget.saveGeometry()))
        settings.setValue("processesListWidth",
           Qt.QVariant(self.processesListWidget.horizontalHeader().saveState()))
        settings.setValue("configDialogGeometry",
                          Qt.QVariant(self.configWidget.saveGeometry()))
        settings.setValue("maxProcesses",
                          Qt.QVariant(self.maxProcesses.value()))

        
    def startConvert(self):
        # since Vernissage might be blocking for Gwyexport, we create
        # two queue for the different process and start them sequentially
        maxProcesses = self.maxProcesses.value()
        self.processesQueue1 = ProcessesQueue(maxProcesses) # for vernissage
        self.processesQueue2 = ProcessesQueue(maxProcesses) # for Gwyexport

        self.startButton.setEnabled(False)
        self.startAct.setEnabled(False)
        self.cancelAct.setEnabled(True)
        Qt.QObject.connect(self.processesQueue1, Qt.SIGNAL("finished()"),
                           self.processesQueue2.start)
        Qt.QObject.connect(self.processesQueue2, Qt.SIGNAL("finished()"),
                           self.resetButtons)

        self.ifpath = os.path.abspath(unicode(self.inputFolder.text()))
        if not os.path.isdir(self.ifpath):
            mb = Qt.QMessageBox()
            mb.setWindowTitle('Error')
            mb.setIcon(Qt.QMessageBox.Critical)
            mb.setText(_tr('Error input folder is not a directory'))
            mb.setDetailedText(_tr('%s is a file or cannot '
                                   'be read.' % self.ifpath))
            mb.exec_()
            self.cancelConvert()
            return

        self.vofpath = os.path.abspath(unicode(self.vernissageOutFolder.text()))
        self.iofpath = os.path.abspath(unicode(self.imageOutFolder.text()))

        try:
            if self.recursive.isChecked():
                for dirname, subdirnames, f in os.walk(self.ifpath):
                    self.convert(os.path.join(self.ifpath, dirname))
            else:
                self.convert(self.ifpath)
        except OSError:
            self.cancelConvert()
            return
        except InvalidFlag:
            self.cancelConvert()
            return
        else:
            self.processesQueue1.start() # the queue 2 will be started
                                         # by the finished signal of 1


    def convert(self, path):
        """" dirname is an absolute path """

        if debug:
            print 'convert', path
            print '-->ifpath', self.ifpath
            print '-->iofpath', self.iofpath
            print '-->vofpath', self.vofpath

        
        currentFolder = os.path.relpath(path, start = self.ifpath)

        if self.exportVernissage.isChecked(): # Do Vernissage conversion
            if debug: print 'Export vernissage'
            vofpath = os.path.normpath(
                            os.path.join(self.vofpath, currentFolder))
            if not os.path.isdir(vofpath):
                os.mkdir(vofpath)
            elif not self.overwrite.isChecked() and currentFolder != '.' :
                # dir exist + do not overwrite
                mb = Qt.QMessageBox()
                mb.setWindowTitle('Error')
                mb.setIcon(Qt.QMessageBox.Critical)
                mb.setText(_tr('Error output folder already exists.\n'
                               'Process stopped'))
                mb.setDetailedText(_tr('Folder %s exists or cannot '
                                   'be created.' % vofpath))
                mb.exec_()
                raise OSError
                return

            ## To fix a BUG with VernissageCmd (or possibly Wine)
            ## which prevent using absolute posix path as input path
            ## we set the working directory as the current path
            ## and we run the command with the relative path '.'
            args = build_command_list(
                unicode(self.vernissageCmd.text()),
                unicode(self.vernissageFlags.text()),
                {'{path}': '.',
                '{outdir}': vofpath,
                '{exporter}': unicode(self.vernissageExporter.text())
                })
            self.createProcess(args, 'Vernissage', path, workingDirectory=path)


        if self.exportImage.isChecked(): # Do Gwyexport
            if debug: print 'Export images'
            iofpath = os.path.normpath(
                            os.path.join(self.iofpath, currentFolder))
            if not os.path.isdir(iofpath):
                os.mkdir(iofpath)
            elif not self.overwrite.isChecked() and currentFolder != '.' :
                mb = Qt.QMessageBox()
                mb.setWindowTitle('Error')
                mb.setIcon(Qt.QMessageBox.Critical)
                mb.setText(_tr('Error output folder already exists.\n'
                               'Process stopped'))
                mb.setDetailedText(_tr('Folder %s exists or cannot '
                                       'be created.' % iofpath))
                mb.exec_()
                raise OSError
                return

            # Use the flat files rather than Matrix if available
            if self.exportVernissage.isChecked() and \
                     unicode(self.vernissageExporter.text()) == 'Flattener':
                path = vofpath

            args = build_command_list(
                    unicode(self.gwyexportCmd.text()),
                    unicode(self.gwyexportFlags.text()),
                {'{exportformat}': unicode(self.gwyexportFormat.currentText()),
                 '{outputpath}': iofpath,
                 '{filterlist}': unicode(self.gwyexportFilters.text()),
                 '{gradient}': unicode(self.gwyexportGradient.currentText()),
                 '{colormap}': unicode(self.gwyexportColormap.currentText()),
                 '{inputfolder}': path,
                })
            self.createProcess(args, 'Gwyexport', path )

    def createProcess(self, args, name, folder, workingDirectory=None):

        if debug: print 'Create process'

        
        process = RetardedProcess(args, self) # self will be parent

        if workingDirectory:
            process.setWorkingDirectory(workingDirectory)
        
        row = self.processesListWidget.rowCount()
        self.processesListWidget.insertRow(row)

        processLabel = Qt.QTableWidgetItem(name)
        folderLabel = Qt.QTableWidgetItem(folder)
        statusItem = StatusItem()

        col = 0
        for i, item in enumerate([processLabel, folderLabel, statusItem]):
            item.setFlags(Qt.Qt.NoItemFlags )
            item.setFlags(Qt.Qt.ItemIsEnabled)
            self.processesListWidget.setItem(row, i, item)
            col = i

        detailButton = Qt.QPushButton(Qt.QIcon('img/detail.svgz'),
                                     _tr('Details'))
        detailButton.setCheckable(True)
        stopButton = Qt.QPushButton(Qt.QIcon('img/stop.svgz'),
                                    _tr('Stop'))
        stopButton.setEnabled(False)

        # Ugly by-pass
        stopButton.setEnabledSlot = lambda: stopButton.setEnabled(True)
        stopButton.setDisabledSlot = lambda: stopButton.setEnabled(False)
        statusItem.disconnectSlot = lambda: Qt.QObject.disconnect(self,
                Qt.SIGNAL("conversionCanceled()"), statusItem.setCanceled)

        self.processesListWidget.setCellWidget(row, col+1, detailButton)
        self.processesListWidget.setCellWidget(row, col+2, stopButton)

        detailMessageBox = DetailMessageBox(process, detailButton, self)
        if workingDirectory:
            detailMessageBox.log.append('cd %s\n' % workingDirectory)
        detailMessageBox.log.append(Qt.QString(' '.join(args) + '\n'))
        
        # Stop and kill
        Qt.QObject.connect(stopButton, Qt.SIGNAL("clicked()"), process,
                           Qt.SLOT("terminate()"))
        killTimer = Qt.QTimer()
        killTimer.setInterval(5000)
        Qt.QObject.connect(stopButton, Qt.SIGNAL("clicked()"), killTimer,
                           Qt.SLOT("start()"))
        Qt.QObject.connect(killTimer, Qt.SIGNAL("timeout()"), process,
                           Qt.SLOT("kill()"))
        Qt.QObject.connect(process, Qt.SIGNAL("started()"),
                           stopButton.setEnabledSlot)
        Qt.QObject.connect(process, Qt.SIGNAL("finished(int)"),
                           stopButton.setDisabledSlot)

        # Process state
        process.closeReadChannel(Qt.QProcess.StandardOutput)
        Qt.QObject.connect(process, Qt.SIGNAL("readyReadStandardOutput()"),
                           detailMessageBox.readOutput)
        Qt.QObject.connect(process, Qt.SIGNAL("readyReadStandardError()"),
                           detailMessageBox.readErrors)
        Qt.QObject.connect(process, Qt.SIGNAL("finished(int)"),
                           statusItem.setFinished)
        Qt.QObject.connect(process, Qt.SIGNAL("started()"),
                           statusItem.setStarted)
        Qt.QObject.connect(self, Qt.SIGNAL("conversionCanceled()"),
                           statusItem.setCanceled)
        Qt.QObject.connect(stopButton, Qt.SIGNAL("clicked()"),
                           statusItem.setCanceled)

        # Cancel action
        Qt.QObject.connect(self.cancelAct, Qt.SIGNAL("triggered()"),
                           self.processesQueue1.stop)
        Qt.QObject.connect(self.cancelAct, Qt.SIGNAL("triggered()"),
                           self.processesQueue2.stop)
        Qt.QObject.connect(self.cancelAct, Qt.SIGNAL("triggered()"),
                           stopButton.setDisabledSlot)


        # Detail
        Qt.QObject.connect(detailButton, Qt.SIGNAL("toggled(bool)"),
                           detailMessageBox.setVisible)
        Qt.QObject.connect(detailMessageBox, Qt.SIGNAL("finished(int)"),
                           detailButton.toggle)

        if 'Vernissage' == name:
            self.processesQueue1.append(process)
        elif 'Gwyexport' == name:
            self.processesQueue2.append(process)
        else: # should never occur
            self.processesQueue1.append(process)

    def resetButtons(self):
        if debug: print "Reset buttons called"
        self.startAct.setEnabled(True)
        self.startButton.setEnabled(True)
        self.cancelAct.setEnabled(False)
        
    def cancelConvert(self):
        self.emit(Qt.SIGNAL("conversionCanceled()"))
        self.resetButtons()

def main():
    app = Qt.QApplication(sys.argv)
    Qt.QObject.connect(app, Qt.SIGNAL("lastWindowClosed()"), app,
                        Qt.SLOT("quit()"))
    mainWindow = AutoconvertWindow(app)
    mainWindow.show()
    sys.exit(app.exec_())
    

if __name__ == "__main__":
    main()
