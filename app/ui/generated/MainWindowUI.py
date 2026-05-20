# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'MainWindowUI.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QMainWindow, QMenu, QMenuBar,
    QPushButton, QSizePolicy, QStackedWidget, QStatusBar,
    QTextEdit, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1043, 970)
        self.action = QAction(MainWindow)
        self.action.setObjectName(u"action")
        self.action_3 = QAction(MainWindow)
        self.action_3.setObjectName(u"action_3")
        self.action_4 = QAction(MainWindow)
        self.action_4.setObjectName(u"action_4")
        self.action_5 = QAction(MainWindow)
        self.action_5.setObjectName(u"action_5")
        self.action_6 = QAction(MainWindow)
        self.action_6.setObjectName(u"action_6")
        self.sourceWidget = QWidget(MainWindow)
        self.sourceWidget.setObjectName(u"sourceWidget")
        self.verticalLayout_2 = QVBoxLayout(self.sourceWidget)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.mainLayout = QVBoxLayout()
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainButtons = QHBoxLayout()
        self.mainButtons.setObjectName(u"mainButtons")
        self.mainButtonSchedule = QPushButton(self.sourceWidget)
        self.mainButtonSchedule.setObjectName(u"mainButtonSchedule")

        self.mainButtons.addWidget(self.mainButtonSchedule)

        self.mainButtonGroups = QPushButton(self.sourceWidget)
        self.mainButtonGroups.setObjectName(u"mainButtonGroups")

        self.mainButtons.addWidget(self.mainButtonGroups)

        self.mainButtonSettings = QPushButton(self.sourceWidget)
        self.mainButtonSettings.setObjectName(u"mainButtonSettings")

        self.mainButtons.addWidget(self.mainButtonSettings)


        self.mainLayout.addLayout(self.mainButtons)

        self.mainWidget = QStackedWidget(self.sourceWidget)
        self.mainWidget.setObjectName(u"mainWidget")
        self.pageSchedule = QWidget()
        self.pageSchedule.setObjectName(u"pageSchedule")
        self.verticalLayout_3 = QVBoxLayout(self.pageSchedule)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.mainSchedule = QVBoxLayout()
        self.mainSchedule.setObjectName(u"mainSchedule")
        self.scheduleDate = QHBoxLayout()
        self.scheduleDate.setObjectName(u"scheduleDate")
        self.scheduleDateButton = QHBoxLayout()
        self.scheduleDateButton.setObjectName(u"scheduleDateButton")
        self.scheduleDateButtonLeft = QPushButton(self.pageSchedule)
        self.scheduleDateButtonLeft.setObjectName(u"scheduleDateButtonLeft")

        self.scheduleDateButton.addWidget(self.scheduleDateButtonLeft)

        self.scheduleDateButtonToday = QPushButton(self.pageSchedule)
        self.scheduleDateButtonToday.setObjectName(u"scheduleDateButtonToday")

        self.scheduleDateButton.addWidget(self.scheduleDateButtonToday)

        self.scheduleDateButtonRight = QPushButton(self.pageSchedule)
        self.scheduleDateButtonRight.setObjectName(u"scheduleDateButtonRight")

        self.scheduleDateButton.addWidget(self.scheduleDateButtonRight)


        self.scheduleDate.addLayout(self.scheduleDateButton)

        self.scheduleDateLabels = QHBoxLayout()
        self.scheduleDateLabels.setObjectName(u"scheduleDateLabels")
        self.scheduleDateLabelsDate = QVBoxLayout()
        self.scheduleDateLabelsDate.setObjectName(u"scheduleDateLabelsDate")
        self.scheduleDateLabelsDateLabelWeek = QLabel(self.pageSchedule)
        self.scheduleDateLabelsDateLabelWeek.setObjectName(u"scheduleDateLabelsDateLabelWeek")

        self.scheduleDateLabelsDate.addWidget(self.scheduleDateLabelsDateLabelWeek)

        self.scheduleDateLabelsDateLabelDate = QLabel(self.pageSchedule)
        self.scheduleDateLabelsDateLabelDate.setObjectName(u"scheduleDateLabelsDateLabelDate")

        self.scheduleDateLabelsDate.addWidget(self.scheduleDateLabelsDateLabelDate)


        self.scheduleDateLabels.addLayout(self.scheduleDateLabelsDate)

        self.scheduleDateLabelsOddity = QVBoxLayout()
        self.scheduleDateLabelsOddity.setObjectName(u"scheduleDateLabelsOddity")
        self.scheduleDateLabelsOddityLabel = QLabel(self.pageSchedule)
        self.scheduleDateLabelsOddityLabel.setObjectName(u"scheduleDateLabelsOddityLabel")

        self.scheduleDateLabelsOddity.addWidget(self.scheduleDateLabelsOddityLabel)


        self.scheduleDateLabels.addLayout(self.scheduleDateLabelsOddity)


        self.scheduleDate.addLayout(self.scheduleDateLabels)


        self.mainSchedule.addLayout(self.scheduleDate)

        self.scheduleLessons = QVBoxLayout()
        self.scheduleLessons.setObjectName(u"scheduleLessons")
        self.scheduleLessonsLesson = QGridLayout()
        self.scheduleLessonsLesson.setObjectName(u"scheduleLessonsLesson")
        self.scheduleLessonsLessonMonday = QLabel(self.pageSchedule)
        self.scheduleLessonsLessonMonday.setObjectName(u"scheduleLessonsLessonMonday")

        self.scheduleLessonsLesson.addWidget(self.scheduleLessonsLessonMonday, 0, 5, 1, 1)

        self.scheduleLessonLabelThursday = QLabel(self.pageSchedule)
        self.scheduleLessonLabelThursday.setObjectName(u"scheduleLessonLabelThursday")

        self.scheduleLessonsLesson.addWidget(self.scheduleLessonLabelThursday, 0, 4, 1, 1)

        self.scheduleLessonLabelSunday = QLabel(self.pageSchedule)
        self.scheduleLessonLabelSunday.setObjectName(u"scheduleLessonLabelSunday")

        self.scheduleLessonsLesson.addWidget(self.scheduleLessonLabelSunday, 0, 7, 1, 1)

        self.scheduleLessonLabelMonday = QLabel(self.pageSchedule)
        self.scheduleLessonLabelMonday.setObjectName(u"scheduleLessonLabelMonday")

        self.scheduleLessonsLesson.addWidget(self.scheduleLessonLabelMonday, 0, 1, 1, 1)

        self.scheduleLessonLabelTuesday = QLabel(self.pageSchedule)
        self.scheduleLessonLabelTuesday.setObjectName(u"scheduleLessonLabelTuesday")

        self.scheduleLessonsLesson.addWidget(self.scheduleLessonLabelTuesday, 0, 2, 1, 1)

        self.scheduleLessonLabelSaturday = QLabel(self.pageSchedule)
        self.scheduleLessonLabelSaturday.setObjectName(u"scheduleLessonLabelSaturday")

        self.scheduleLessonsLesson.addWidget(self.scheduleLessonLabelSaturday, 0, 6, 1, 1)

        self.scheduleLessonLabelWednessday = QLabel(self.pageSchedule)
        self.scheduleLessonLabelWednessday.setObjectName(u"scheduleLessonLabelWednessday")

        self.scheduleLessonsLesson.addWidget(self.scheduleLessonLabelWednessday, 0, 3, 1, 1)


        self.scheduleLessons.addLayout(self.scheduleLessonsLesson)


        self.mainSchedule.addLayout(self.scheduleLessons)


        self.verticalLayout_3.addLayout(self.mainSchedule)

        self.mainWidget.addWidget(self.pageSchedule)
        self.pageGroups = QWidget()
        self.pageGroups.setObjectName(u"pageGroups")
        self.verticalLayout_11 = QVBoxLayout(self.pageGroups)
        self.verticalLayout_11.setObjectName(u"verticalLayout_11")
        self.mainGroups = QVBoxLayout()
        self.mainGroups.setObjectName(u"mainGroups")
        self.groupsTips = QVBoxLayout()
        self.groupsTips.setObjectName(u"groupsTips")
        self.groupsTip1 = QLabel(self.pageGroups)
        self.groupsTip1.setObjectName(u"groupsTip1")

        self.groupsTips.addWidget(self.groupsTip1)

        self.groupsTip2 = QLabel(self.pageGroups)
        self.groupsTip2.setObjectName(u"groupsTip2")

        self.groupsTips.addWidget(self.groupsTip2)


        self.mainGroups.addLayout(self.groupsTips)

        self.groupsFreeSpace = QFormLayout()
        self.groupsFreeSpace.setObjectName(u"groupsFreeSpace")

        self.mainGroups.addLayout(self.groupsFreeSpace)


        self.verticalLayout_11.addLayout(self.mainGroups)

        self.mainWidget.addWidget(self.pageGroups)
        self.pageSettings = QWidget()
        self.pageSettings.setObjectName(u"pageSettings")
        self.verticalLayout_12 = QVBoxLayout(self.pageSettings)
        self.verticalLayout_12.setObjectName(u"verticalLayout_12")
        self.mainSettings = QVBoxLayout()
        self.mainSettings.setObjectName(u"mainSettings")
        self.settingsCurrent = QVBoxLayout()
        self.settingsCurrent.setObjectName(u"settingsCurrent")
        self.settingsCurrentLabelTip1 = QLabel(self.pageSettings)
        self.settingsCurrentLabelTip1.setObjectName(u"settingsCurrentLabelTip1")

        self.settingsCurrent.addWidget(self.settingsCurrentLabelTip1)

        self.settingsCurrentLabelTip2 = QLabel(self.pageSettings)
        self.settingsCurrentLabelTip2.setObjectName(u"settingsCurrentLabelTip2")

        self.settingsCurrent.addWidget(self.settingsCurrentLabelTip2)


        self.mainSettings.addLayout(self.settingsCurrent)


        self.verticalLayout_12.addLayout(self.mainSettings)

        self.settingsAlternative = QVBoxLayout()
        self.settingsAlternative.setObjectName(u"settingsAlternative")
        self.settingsAlternativeAction = QHBoxLayout()
        self.settingsAlternativeAction.setObjectName(u"settingsAlternativeAction")
        self.settingsAlternativeButtonSchedule = QPushButton(self.pageSettings)
        self.settingsAlternativeButtonSchedule.setObjectName(u"settingsAlternativeButtonSchedule")

        self.settingsAlternativeAction.addWidget(self.settingsAlternativeButtonSchedule)

        self.settingsAlternativeButtonGroups = QPushButton(self.pageSettings)
        self.settingsAlternativeButtonGroups.setObjectName(u"settingsAlternativeButtonGroups")

        self.settingsAlternativeAction.addWidget(self.settingsAlternativeButtonGroups)

        self.settingsAlternativeButtonStudents = QPushButton(self.pageSettings)
        self.settingsAlternativeButtonStudents.setObjectName(u"settingsAlternativeButtonStudents")

        self.settingsAlternativeAction.addWidget(self.settingsAlternativeButtonStudents)

        self.settingsAlternativeButtonSemester = QPushButton(self.pageSettings)
        self.settingsAlternativeButtonSemester.setObjectName(u"settingsAlternativeButtonSemester")

        self.settingsAlternativeAction.addWidget(self.settingsAlternativeButtonSemester)


        self.settingsAlternative.addLayout(self.settingsAlternativeAction)

        self.settingsWidget = QStackedWidget(self.pageSettings)
        self.settingsWidget.setObjectName(u"settingsWidget")
        self.pageSettingsSchedule = QWidget()
        self.pageSettingsSchedule.setObjectName(u"pageSettingsSchedule")
        self.verticalLayout_15 = QVBoxLayout(self.pageSettingsSchedule)
        self.verticalLayout_15.setObjectName(u"verticalLayout_15")
        self.settingsScheduleMain = QVBoxLayout()
        self.settingsScheduleMain.setObjectName(u"settingsScheduleMain")
        self.settingsScheduleChange = QHBoxLayout()
        self.settingsScheduleChange.setObjectName(u"settingsScheduleChange")
        self.settingsScheduleChangeTip = QVBoxLayout()
        self.settingsScheduleChangeTip.setObjectName(u"settingsScheduleChangeTip")
        self.settingsScheduleChangeLabelTip1 = QLabel(self.pageSettingsSchedule)
        self.settingsScheduleChangeLabelTip1.setObjectName(u"settingsScheduleChangeLabelTip1")

        self.settingsScheduleChangeTip.addWidget(self.settingsScheduleChangeLabelTip1)


        self.settingsScheduleChange.addLayout(self.settingsScheduleChangeTip)

        self.settingsScheduleChangeAction = QVBoxLayout()
        self.settingsScheduleChangeAction.setObjectName(u"settingsScheduleChangeAction")
        self.settingsScheduleChangeActionButton = QPushButton(self.pageSettingsSchedule)
        self.settingsScheduleChangeActionButton.setObjectName(u"settingsScheduleChangeActionButton")

        self.settingsScheduleChangeAction.addWidget(self.settingsScheduleChangeActionButton)


        self.settingsScheduleChange.addLayout(self.settingsScheduleChangeAction)


        self.settingsScheduleMain.addLayout(self.settingsScheduleChange)

        self.settingsScheduleFreeSpace = QFormLayout()
        self.settingsScheduleFreeSpace.setObjectName(u"settingsScheduleFreeSpace")

        self.settingsScheduleMain.addLayout(self.settingsScheduleFreeSpace)


        self.verticalLayout_15.addLayout(self.settingsScheduleMain)

        self.settingsWidget.addWidget(self.pageSettingsSchedule)
        self.pageSettingsGroups = QWidget()
        self.pageSettingsGroups.setObjectName(u"pageSettingsGroups")
        self.verticalLayout_19 = QVBoxLayout(self.pageSettingsGroups)
        self.verticalLayout_19.setObjectName(u"verticalLayout_19")
        self.settingsGroupsMain = QVBoxLayout()
        self.settingsGroupsMain.setObjectName(u"settingsGroupsMain")
        self.settingsGroupsChange = QHBoxLayout()
        self.settingsGroupsChange.setObjectName(u"settingsGroupsChange")
        self.settingsGroupsChangeTip = QVBoxLayout()
        self.settingsGroupsChangeTip.setObjectName(u"settingsGroupsChangeTip")
        self.settingsGroupsChangeLabelTip1 = QLabel(self.pageSettingsGroups)
        self.settingsGroupsChangeLabelTip1.setObjectName(u"settingsGroupsChangeLabelTip1")

        self.settingsGroupsChangeTip.addWidget(self.settingsGroupsChangeLabelTip1)


        self.settingsGroupsChange.addLayout(self.settingsGroupsChangeTip)

        self.settingsGroupsChangeAction = QVBoxLayout()
        self.settingsGroupsChangeAction.setObjectName(u"settingsGroupsChangeAction")
        self.settingsGroupsChangeActionButton = QPushButton(self.pageSettingsGroups)
        self.settingsGroupsChangeActionButton.setObjectName(u"settingsGroupsChangeActionButton")

        self.settingsGroupsChangeAction.addWidget(self.settingsGroupsChangeActionButton)


        self.settingsGroupsChange.addLayout(self.settingsGroupsChangeAction)


        self.settingsGroupsMain.addLayout(self.settingsGroupsChange)

        self.settingsGroupsFreeSpace = QHBoxLayout()
        self.settingsGroupsFreeSpace.setObjectName(u"settingsGroupsFreeSpace")

        self.settingsGroupsMain.addLayout(self.settingsGroupsFreeSpace)


        self.verticalLayout_19.addLayout(self.settingsGroupsMain)

        self.settingsWidget.addWidget(self.pageSettingsGroups)
        self.pageSettingsStudents = QWidget()
        self.pageSettingsStudents.setObjectName(u"pageSettingsStudents")
        self.verticalLayout_23 = QVBoxLayout(self.pageSettingsStudents)
        self.verticalLayout_23.setObjectName(u"verticalLayout_23")
        self.settingsStudentsMain = QVBoxLayout()
        self.settingsStudentsMain.setObjectName(u"settingsStudentsMain")
        self.settingsStudentsChange = QHBoxLayout()
        self.settingsStudentsChange.setObjectName(u"settingsStudentsChange")
        self.settingsStudentsChangeTip = QVBoxLayout()
        self.settingsStudentsChangeTip.setObjectName(u"settingsStudentsChangeTip")
        self.settingsStudentsChangeLabelTip1 = QLabel(self.pageSettingsStudents)
        self.settingsStudentsChangeLabelTip1.setObjectName(u"settingsStudentsChangeLabelTip1")

        self.settingsStudentsChangeTip.addWidget(self.settingsStudentsChangeLabelTip1)


        self.settingsStudentsChange.addLayout(self.settingsStudentsChangeTip)

        self.settingsStudentsChangeChoose = QHBoxLayout()
        self.settingsStudentsChangeChoose.setObjectName(u"settingsStudentsChangeChoose")
        self.settingsStudentsChangeChooseButton = QPushButton(self.pageSettingsStudents)
        self.settingsStudentsChangeChooseButton.setObjectName(u"settingsStudentsChangeChooseButton")

        self.settingsStudentsChangeChoose.addWidget(self.settingsStudentsChangeChooseButton)


        self.settingsStudentsChange.addLayout(self.settingsStudentsChangeChoose)

        self.settingsStudentsChangeAction = QVBoxLayout()
        self.settingsStudentsChangeAction.setObjectName(u"settingsStudentsChangeAction")
        self.settingsStudentsChangeActionButton = QPushButton(self.pageSettingsStudents)
        self.settingsStudentsChangeActionButton.setObjectName(u"settingsStudentsChangeActionButton")

        self.settingsStudentsChangeAction.addWidget(self.settingsStudentsChangeActionButton)


        self.settingsStudentsChange.addLayout(self.settingsStudentsChangeAction)


        self.settingsStudentsMain.addLayout(self.settingsStudentsChange)

        self.settingsStudentsFreeSpace = QHBoxLayout()
        self.settingsStudentsFreeSpace.setObjectName(u"settingsStudentsFreeSpace")

        self.settingsStudentsMain.addLayout(self.settingsStudentsFreeSpace)


        self.verticalLayout_23.addLayout(self.settingsStudentsMain)

        self.settingsWidget.addWidget(self.pageSettingsStudents)
        self.pageSettingsSemester = QWidget()
        self.pageSettingsSemester.setObjectName(u"pageSettingsSemester")
        self.verticalLayout_27 = QVBoxLayout(self.pageSettingsSemester)
        self.verticalLayout_27.setObjectName(u"verticalLayout_27")
        self.SettingsSemesterMain = QVBoxLayout()
        self.SettingsSemesterMain.setObjectName(u"SettingsSemesterMain")
        self.settingsSemesterTip1 = QVBoxLayout()
        self.settingsSemesterTip1.setObjectName(u"settingsSemesterTip1")
        self.settingsSemesterTip1Label = QLabel(self.pageSettingsSemester)
        self.settingsSemesterTip1Label.setObjectName(u"settingsSemesterTip1Label")

        self.settingsSemesterTip1.addWidget(self.settingsSemesterTip1Label)


        self.SettingsSemesterMain.addLayout(self.settingsSemesterTip1)

        self.settingsSemesterAction = QVBoxLayout()
        self.settingsSemesterAction.setObjectName(u"settingsSemesterAction")
        self.settingsSemesterActionDate = QVBoxLayout()
        self.settingsSemesterActionDate.setObjectName(u"settingsSemesterActionDate")
        self.settingsSemesterActionDateLabelTip1 = QLabel(self.pageSettingsSemester)
        self.settingsSemesterActionDateLabelTip1.setObjectName(u"settingsSemesterActionDateLabelTip1")

        self.settingsSemesterActionDate.addWidget(self.settingsSemesterActionDateLabelTip1)

        self.settingsSemesterActionDateTextBox = QTextEdit(self.pageSettingsSemester)
        self.settingsSemesterActionDateTextBox.setObjectName(u"settingsSemesterActionDateTextBox")

        self.settingsSemesterActionDate.addWidget(self.settingsSemesterActionDateTextBox)

        self.settingsSemesterActionDateLabelTip2 = QLabel(self.pageSettingsSemester)
        self.settingsSemesterActionDateLabelTip2.setObjectName(u"settingsSemesterActionDateLabelTip2")

        self.settingsSemesterActionDate.addWidget(self.settingsSemesterActionDateLabelTip2)

        self.settingsSemesterActionDate.setStretch(0, 1)
        self.settingsSemesterActionDate.setStretch(1, 1)
        self.settingsSemesterActionDate.setStretch(2, 1)

        self.settingsSemesterAction.addLayout(self.settingsSemesterActionDate)

        self.settingsSemesterActionWeek = QHBoxLayout()
        self.settingsSemesterActionWeek.setObjectName(u"settingsSemesterActionWeek")
        self.settingsSemesterActionWeekInput = QVBoxLayout()
        self.settingsSemesterActionWeekInput.setObjectName(u"settingsSemesterActionWeekInput")
        self.settingsSemesterActionLabelTip1 = QLabel(self.pageSettingsSemester)
        self.settingsSemesterActionLabelTip1.setObjectName(u"settingsSemesterActionLabelTip1")

        self.settingsSemesterActionWeekInput.addWidget(self.settingsSemesterActionLabelTip1)

        self.settingsSemesterActionTextBox = QTextEdit(self.pageSettingsSemester)
        self.settingsSemesterActionTextBox.setObjectName(u"settingsSemesterActionTextBox")

        self.settingsSemesterActionWeekInput.addWidget(self.settingsSemesterActionTextBox)

        self.settingsSemesterActionLabelTip2 = QLabel(self.pageSettingsSemester)
        self.settingsSemesterActionLabelTip2.setObjectName(u"settingsSemesterActionLabelTip2")

        self.settingsSemesterActionWeekInput.addWidget(self.settingsSemesterActionLabelTip2)

        self.settingsSemesterActionWeekInput.setStretch(0, 1)
        self.settingsSemesterActionWeekInput.setStretch(1, 1)
        self.settingsSemesterActionWeekInput.setStretch(2, 1)

        self.settingsSemesterActionWeek.addLayout(self.settingsSemesterActionWeekInput)

        self.settingsSemesterActionWeekChange = QVBoxLayout()
        self.settingsSemesterActionWeekChange.setObjectName(u"settingsSemesterActionWeekChange")
        self.settingsSemesterActionWeekChangeButtonIncrease = QPushButton(self.pageSettingsSemester)
        self.settingsSemesterActionWeekChangeButtonIncrease.setObjectName(u"settingsSemesterActionWeekChangeButtonIncrease")

        self.settingsSemesterActionWeekChange.addWidget(self.settingsSemesterActionWeekChangeButtonIncrease)

        self.settingsSemesterActionWeekChangeButtonDecrease = QPushButton(self.pageSettingsSemester)
        self.settingsSemesterActionWeekChangeButtonDecrease.setObjectName(u"settingsSemesterActionWeekChangeButtonDecrease")

        self.settingsSemesterActionWeekChange.addWidget(self.settingsSemesterActionWeekChangeButtonDecrease)


        self.settingsSemesterActionWeek.addLayout(self.settingsSemesterActionWeekChange)

        self.settingsSemesterActionWeek.setStretch(0, 5)
        self.settingsSemesterActionWeek.setStretch(1, 1)

        self.settingsSemesterAction.addLayout(self.settingsSemesterActionWeek)

        self.settingsSemesterActionSave = QVBoxLayout()
        self.settingsSemesterActionSave.setObjectName(u"settingsSemesterActionSave")
        self.settingsSemesterActionSaveButton = QPushButton(self.pageSettingsSemester)
        self.settingsSemesterActionSaveButton.setObjectName(u"settingsSemesterActionSaveButton")

        self.settingsSemesterActionSave.addWidget(self.settingsSemesterActionSaveButton)


        self.settingsSemesterAction.addLayout(self.settingsSemesterActionSave)

        self.settingsSemesterAction.setStretch(0, 2)
        self.settingsSemesterAction.setStretch(1, 2)
        self.settingsSemesterAction.setStretch(2, 1)

        self.SettingsSemesterMain.addLayout(self.settingsSemesterAction)

        self.settingsSemesterTip2 = QVBoxLayout()
        self.settingsSemesterTip2.setObjectName(u"settingsSemesterTip2")
        self.settingsSemesterTip2Label = QLabel(self.pageSettingsSemester)
        self.settingsSemesterTip2Label.setObjectName(u"settingsSemesterTip2Label")

        self.settingsSemesterTip2.addWidget(self.settingsSemesterTip2Label)


        self.SettingsSemesterMain.addLayout(self.settingsSemesterTip2)

        self.SettingsSemesterMain.setStretch(0, 1)
        self.SettingsSemesterMain.setStretch(1, 5)
        self.SettingsSemesterMain.setStretch(2, 1)

        self.verticalLayout_27.addLayout(self.SettingsSemesterMain)

        self.settingsWidget.addWidget(self.pageSettingsSemester)

        self.settingsAlternative.addWidget(self.settingsWidget)


        self.verticalLayout_12.addLayout(self.settingsAlternative)

        self.mainWidget.addWidget(self.pageSettings)

        self.mainLayout.addWidget(self.mainWidget)


        self.verticalLayout_2.addLayout(self.mainLayout)

        MainWindow.setCentralWidget(self.sourceWidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1043, 33))
        self.menu = QMenu(self.menubar)
        self.menu.setObjectName(u"menu")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menu.menuAction())
        self.menu.addAction(self.action)
        self.menu.addSeparator()
        self.menu.addAction(self.action_3)
        self.menu.addAction(self.action_4)
        self.menu.addAction(self.action_5)
        self.menu.addAction(self.action_6)

        self.retranslateUi(MainWindow)

        self.mainWidget.setCurrentIndex(2)
        self.settingsWidget.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.action.setText(QCoreApplication.translate("MainWindow", u"\u0418\u043c\u043f\u043e\u0440\u0442", None))
        self.action_3.setText(QCoreApplication.translate("MainWindow", u"\u042d\u043a\u0441\u043f\u043e\u0440\u0442", None))
        self.action_4.setText(QCoreApplication.translate("MainWindow", u"\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c", None))
        self.action_5.setText(QCoreApplication.translate("MainWindow", u"\u0420\u0435\u0437\u044e\u043c\u0438\u0440\u043e\u0432\u0430\u0442\u044c", None))
        self.action_6.setText(QCoreApplication.translate("MainWindow", u"\u041d\u0438\u0447\u0435\u0433\u043e", None))
        self.mainButtonSchedule.setText(QCoreApplication.translate("MainWindow", u"Schedule", None))
        self.mainButtonGroups.setText(QCoreApplication.translate("MainWindow", u"Groups", None))
        self.mainButtonSettings.setText(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.scheduleDateButtonLeft.setText(QCoreApplication.translate("MainWindow", u"<", None))
        self.scheduleDateButtonToday.setText(QCoreApplication.translate("MainWindow", u"Today", None))
        self.scheduleDateButtonRight.setText(QCoreApplication.translate("MainWindow", u">", None))
        self.scheduleDateLabelsDateLabelWeek.setText(QCoreApplication.translate("MainWindow", u"Week", None))
        self.scheduleDateLabelsDateLabelDate.setText(QCoreApplication.translate("MainWindow", u"xx/xx/xxxx - xx/xx/xxxx.", None))
        self.scheduleDateLabelsOddityLabel.setText(QCoreApplication.translate("MainWindow", u"Odd? Week", None))
        self.scheduleLessonsLessonMonday.setText(QCoreApplication.translate("MainWindow", u"Friday", None))
        self.scheduleLessonLabelThursday.setText(QCoreApplication.translate("MainWindow", u"Thursday", None))
        self.scheduleLessonLabelSunday.setText(QCoreApplication.translate("MainWindow", u"Sunday", None))
        self.scheduleLessonLabelMonday.setText(QCoreApplication.translate("MainWindow", u"Monday", None))
        self.scheduleLessonLabelTuesday.setText(QCoreApplication.translate("MainWindow", u"Tuesday", None))
        self.scheduleLessonLabelSaturday.setText(QCoreApplication.translate("MainWindow", u"Saturday", None))
        self.scheduleLessonLabelWednessday.setText(QCoreApplication.translate("MainWindow", u"Wednessday", None))
        self.groupsTip1.setText(QCoreApplication.translate("MainWindow", u"All Groups", None))
        self.groupsTip2.setText(QCoreApplication.translate("MainWindow", u"Click on a group to view detailed information", None))
        self.settingsCurrentLabelTip1.setText(QCoreApplication.translate("MainWindow", u"Management & Settings", None))
        self.settingsCurrentLabelTip2.setText(QCoreApplication.translate("MainWindow", u"Manage schedules, students, groups, and semester settings", None))
        self.settingsAlternativeButtonSchedule.setText(QCoreApplication.translate("MainWindow", u"Schedules Template", None))
        self.settingsAlternativeButtonGroups.setText(QCoreApplication.translate("MainWindow", u"Groups", None))
        self.settingsAlternativeButtonStudents.setText(QCoreApplication.translate("MainWindow", u"Students", None))
        self.settingsAlternativeButtonSemester.setText(QCoreApplication.translate("MainWindow", u"Semester Settings", None))
        self.settingsScheduleChangeLabelTip1.setText(QCoreApplication.translate("MainWindow", u"Schedule Templates", None))
        self.settingsScheduleChangeActionButton.setText(QCoreApplication.translate("MainWindow", u"Add Schedule Template", None))
        self.settingsGroupsChangeLabelTip1.setText(QCoreApplication.translate("MainWindow", u"Groups", None))
        self.settingsGroupsChangeActionButton.setText(QCoreApplication.translate("MainWindow", u"Add Group", None))
        self.settingsStudentsChangeLabelTip1.setText(QCoreApplication.translate("MainWindow", u"Students", None))
        self.settingsStudentsChangeChooseButton.setText(QCoreApplication.translate("MainWindow", u"All Groups", None))
        self.settingsStudentsChangeActionButton.setText(QCoreApplication.translate("MainWindow", u"Add Student", None))
        self.settingsSemesterTip1Label.setText(QCoreApplication.translate("MainWindow", u"Semester Settings", None))
        self.settingsSemesterActionDateLabelTip1.setText(QCoreApplication.translate("MainWindow", u"Semester Start Date (First Monday)", None))
        self.settingsSemesterActionDateLabelTip2.setText(QCoreApplication.translate("MainWindow", u"Select the first Monday of the semester. This will be Week 1.", None))
        self.settingsSemesterActionLabelTip1.setText(QCoreApplication.translate("MainWindow", u"Total Weeks in Semester", None))
        self.settingsSemesterActionLabelTip2.setText(QCoreApplication.translate("MainWindow", u"Default is 17 weeks. The schedule will only show weeks within this range.", None))
        self.settingsSemesterActionWeekChangeButtonIncrease.setText(QCoreApplication.translate("MainWindow", u"+", None))
        self.settingsSemesterActionWeekChangeButtonDecrease.setText(QCoreApplication.translate("MainWindow", u"-", None))
        self.settingsSemesterActionSaveButton.setText(QCoreApplication.translate("MainWindow", u"Save settings", None))
        self.settingsSemesterTip2Label.setText(QCoreApplication.translate("MainWindow", u"Current Semester Information\n"
"\n"
"Start Date: Monday, February 2, 2026\n"
"\n"
"End Date: Sunday, May 31, 2026\n"
"\n"
"Total Weeks: 17", None))
        self.menu.setTitle(QCoreApplication.translate("MainWindow", u"\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", None))
    # retranslateUi

