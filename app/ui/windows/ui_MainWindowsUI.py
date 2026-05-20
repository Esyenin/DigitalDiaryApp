from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)
from PySide6.QtCore import Qt

from app.ui.generated.MainWindowUI import Ui_MainWindow
import app.ui.generated.MainWindowUI

import sys


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.sourceWidget.setVisible(True)
        self.ui.mainWidget.setCurrentWidget(self.ui.pageSchedule)
        self._apply_layout_visuals()

        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #07152d;
                font-family: "Segoe UI";
                font-size: 16px;
            }

            QMainWindow,
            QWidget#sourceWidget {
                background-color: #ffffff;
            }

            QStackedWidget#mainWidget,
            QWidget#pageSchedule,
            QWidget#pageGroups,
            QWidget#pageSettings {
                background-color: #eaf2ff;
            }

            QStackedWidget#settingsWidget,
            QWidget#pageSettingsSchedule,
            QWidget#pageSettingsGroups,
            QWidget#pageSettingsStudents,
            QWidget#pageSettingsSemester {
                background: transparent;
            }

            QLabel {
                color: #07152d;
                background: transparent;
                font-size: 20px;
                font-weight: 400;
            }

            QPushButton {
                background-color: #e4e7ec;
                color: #1d2d46;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                min-height: 44px;
                font-size: 18px;
                font-weight: 400;
            }

            QPushButton:hover {
                background-color: #d9dee7;
            }

            QPushButton:pressed,
            QPushButton:focus {
                background-color: #1f5cf4;
                color: #ffffff;
            }

            QPushButton#mainButtonSchedule,
            QPushButton#mainButtonGroups,
            QPushButton#mainButtonSettings {
                background-color: #e3e6eb;
                color: #1b2c46;
                min-height: 96px;
                font-size: 26px;
                border-radius: 8px;
            }

            QPushButton#mainButtonSchedule:hover,
            QPushButton#mainButtonGroups:hover,
            QPushButton#mainButtonSettings:hover {
                background-color: #d8dde5;
            }

            QPushButton#mainButtonSchedule:pressed,
            QPushButton#mainButtonGroups:pressed,
            QPushButton#mainButtonSettings:pressed,
            QPushButton#mainButtonSchedule:focus,
            QPushButton#mainButtonGroups:focus,
            QPushButton#mainButtonSettings:focus {
                background-color: #1f5cf4;
                color: #ffffff;
            }

            QPushButton#scheduleDateButtonLeft,
            QPushButton#scheduleDateButtonRight {
                background-color: #ffffff;
                color: #050b18;
                border: 1px solid #dce1ea;
                min-width: 42px;
                min-height: 38px;
                font-size: 22px;
                padding: 8px 12px;
            }

            QPushButton#scheduleDateButtonToday {
                background-color: #ffffff;
                color: #050b18;
                border: 1px solid #dce1ea;
                min-height: 38px;
                font-size: 16px;
                padding: 8px 20px;
            }

            QPushButton#scheduleDateButtonLeft:hover,
            QPushButton#scheduleDateButtonRight:hover,
            QPushButton#scheduleDateButtonToday:hover,
            QPushButton#scheduleDateButtonLeft:focus,
            QPushButton#scheduleDateButtonRight:focus,
            QPushButton#scheduleDateButtonToday:focus,
            QPushButton#scheduleDateButtonLeft:pressed,
            QPushButton#scheduleDateButtonRight:pressed,
            QPushButton#scheduleDateButtonToday:pressed {
                background-color: #f8fafc;
                color: #050b18;
                border: 1px solid #cfd6e1;
            }

            QLabel#scheduleDateLabelsDateLabelWeek {
                color: #284164;
                font-size: 16px;
            }

            QLabel#scheduleDateLabelsDateLabelDate {
                color: #000000;
                font-size: 24px;
            }

            QLabel#scheduleDateLabelsOddityLabel {
                background-color: #030416;
                color: #ffffff;
                border-radius: 9px;
                padding: 18px 30px;
                font-size: 22px;
            }

            QLabel#scheduleLessonsLessonMonday,
            QLabel#scheduleLessonLabelMonday,
            QLabel#scheduleLessonLabelTuesday,
            QLabel#scheduleLessonLabelThursday,
            QLabel#scheduleLessonLabelSaturday,
            QLabel#scheduleLessonLabelSunday {
                background-color: #ffffff;
                color: #213652;
                border: 1px solid #dfe4ec;
                border-radius: 10px;
                padding: 18px;
                min-height: 74px;
                font-size: 18px;
            }

            QLabel#scheduleLessonLabelWednessday {
                background-color: #1f5cf4;
                color: #ffffff;
                border: 1px solid #1f5cf4;
                border-radius: 10px;
                padding: 18px;
                min-height: 74px;
                font-size: 18px;
                font-weight: 700;
            }

            QLabel#groupsTip1,
            QLabel#settingsCurrentLabelTip1,
            QLabel#settingsScheduleChangeLabelTip1,
            QLabel#settingsGroupsChangeLabelTip1,
            QLabel#settingsStudentsChangeLabelTip1,
            QLabel#settingsSemesterTip1Label {
                color: #07152d;
                font-size: 30px;
            }

            QLabel#groupsTip2,
            QLabel#settingsCurrentLabelTip2,
            QLabel#settingsSemesterActionDateLabelTip2,
            QLabel#settingsSemesterActionLabelTip2,
            QLabel#settingsSemesterTip2Label {
                color: #33445f;
                font-size: 18px;
            }

            QLabel#settingsSemesterActionDateLabelTip1,
            QLabel#settingsSemesterActionLabelTip1 {
                color: #07152d;
                font-size: 20px;
            }

            QPushButton#settingsAlternativeButtonSchedule,
            QPushButton#settingsAlternativeButtonGroups,
            QPushButton#settingsAlternativeButtonStudents,
            QPushButton#settingsAlternativeButtonSemester {
                background-color: #e8e8ec;
                color: #050b18;
                min-height: 46px;
                font-size: 18px;
                border-radius: 8px;
            }

            QPushButton#settingsAlternativeButtonSchedule:hover,
            QPushButton#settingsAlternativeButtonGroups:hover,
            QPushButton#settingsAlternativeButtonStudents:hover,
            QPushButton#settingsAlternativeButtonSemester:hover {
                background-color: #f2f2f4;
            }

            QPushButton#settingsAlternativeButtonSchedule:focus,
            QPushButton#settingsAlternativeButtonGroups:focus,
            QPushButton#settingsAlternativeButtonStudents:focus,
            QPushButton#settingsAlternativeButtonSemester:focus,
            QPushButton#settingsAlternativeButtonSchedule:pressed,
            QPushButton#settingsAlternativeButtonGroups:pressed,
            QPushButton#settingsAlternativeButtonStudents:pressed,
            QPushButton#settingsAlternativeButtonSemester:pressed {
                background-color: #ffffff;
                color: #050b18;
            }

            QPushButton#settingsScheduleChangeActionButton,
            QPushButton#settingsGroupsChangeActionButton,
            QPushButton#settingsStudentsChangeActionButton,
            QPushButton#settingsSemesterActionSaveButton,
            QPushButton#settingsSemesterActionWeekChangeButtonIncrease,
            QPushButton#settingsSemesterActionWeekChangeButtonDecrease {
                background-color: #030416;
                color: #ffffff;
                border-radius: 8px;
                min-height: 40px;
                font-size: 17px;
                padding: 8px 18px;
            }

            QPushButton#settingsScheduleChangeActionButton {
                max-width: 280px;
            }

            QPushButton#settingsGroupsChangeActionButton {
                max-width: 160px;
            }

            QPushButton#settingsStudentsChangeActionButton {
                max-width: 170px;
            }

            QPushButton#settingsSemesterActionSaveButton {
                max-width: 190px;
            }

            QPushButton#settingsSemesterActionWeekChangeButtonIncrease,
            QPushButton#settingsSemesterActionWeekChangeButtonDecrease {
                min-width: 48px;
                max-width: 58px;
                font-size: 24px;
                padding: 4px 14px;
            }

            QPushButton#settingsScheduleChangeActionButton:hover,
            QPushButton#settingsGroupsChangeActionButton:hover,
            QPushButton#settingsStudentsChangeActionButton:hover,
            QPushButton#settingsSemesterActionSaveButton:hover,
            QPushButton#settingsSemesterActionWeekChangeButtonIncrease:hover,
            QPushButton#settingsSemesterActionWeekChangeButtonDecrease:hover,
            QPushButton#settingsScheduleChangeActionButton:focus,
            QPushButton#settingsGroupsChangeActionButton:focus,
            QPushButton#settingsStudentsChangeActionButton:focus,
            QPushButton#settingsSemesterActionSaveButton:focus,
            QPushButton#settingsSemesterActionWeekChangeButtonIncrease:focus,
            QPushButton#settingsSemesterActionWeekChangeButtonDecrease:focus {
                background-color: #0c1024;
                color: #ffffff;
            }

            QPushButton#settingsStudentsChangeChooseButton {
                background-color: #f2f2f4;
                color: #050b18;
                min-height: 42px;
                max-width: 210px;
                font-size: 16px;
                padding: 8px 18px;
            }

            QPushButton#settingsStudentsChangeChooseButton:hover,
            QPushButton#settingsStudentsChangeChooseButton:focus,
            QPushButton#settingsStudentsChangeChooseButton:pressed {
                background-color: #ffffff;
                color: #050b18;
            }

            QTextEdit,
            QLineEdit,
            QSpinBox {
                background-color: #ffffff;
                color: #07152d;
                border: 1px solid #dce1ea;
                border-radius: 8px;
                padding: 10px;
                font-size: 16px;
                min-height: 36px;
            }

            QTextEdit#settingsSemesterActionDateTextBox,
            QTextEdit#settingsSemesterActionTextBox {
                max-height: 44px;
            }

            QMenuBar {
                background-color: #ffffff;
                color: #07152d;
                padding: 4px;
                font-size: 13px;
            }

            QMenuBar::item:selected {
                background-color: #e8eef8;
                border-radius: 6px;
            }

            QMenu {
                background-color: #ffffff;
                color: #07152d;
                border: 1px solid #dce1ea;
                padding: 6px;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0;
            }

            QScrollBar::handle:vertical {
                background: #c8d2e4;
                border-radius: 5px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #aebbd0;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self.ui.mainButtonSchedule.clicked.connect(
            lambda: self.ui.mainWidget.setCurrentWidget(self.ui.pageSchedule)
        )
        self.ui.mainButtonGroups.clicked.connect(
            lambda: self.ui.mainWidget.setCurrentWidget(self.ui.pageGroups)
        )
        def _InitialFilteringSettings_():
            self.ui.mainWidget.setCurrentWidget(self.ui.pageSettings)
            self.ui.settingsWidget.setCurrentWidget(self.ui.pageSettingsSchedule)

        self.ui.mainButtonSettings.clicked.connect(
            _InitialFilteringSettings_
        )
        self.ui.settingsAlternativeButtonSchedule.clicked.connect(
            lambda: self.ui.settingsWidget.setCurrentWidget(self.ui.pageSettingsSchedule)
        )
        self.ui.settingsAlternativeButtonSemester.clicked.connect(
            lambda: self.ui.settingsWidget.setCurrentWidget(self.ui.pageSettingsSemester)
        )
        self.ui.settingsAlternativeButtonStudents.clicked.connect(
            lambda: self.ui.settingsWidget.setCurrentWidget(self.ui.pageSettingsStudents)
        )
        self.ui.settingsAlternativeButtonGroups.clicked.connect(
            lambda: self.ui.settingsWidget.setCurrentWidget(self.ui.pageSettingsGroups)
        )

    def _apply_layout_visuals(self):
        ui = self.ui

        ui.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        ui.verticalLayout_2.setSpacing(0)
        ui.mainLayout.setContentsMargins(0, 0, 0, 0)
        ui.mainLayout.setSpacing(0)
        ui.mainLayout.setStretch(0, 0)
        ui.mainLayout.setStretch(1, 1)

        ui.mainButtons.setContentsMargins(104, 48, 104, 28)
        ui.mainButtons.setSpacing(18)

        ui.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        ui.mainSchedule.setContentsMargins(120, 30, 120, 24)
        ui.mainSchedule.setSpacing(28)
        ui.mainSchedule.setStretch(0, 0)
        ui.mainSchedule.setStretch(1, 1)

        ui.scheduleDate.setContentsMargins(30, 28, 30, 28)
        ui.scheduleDate.setSpacing(24)
        ui.scheduleDate.setStretch(0, 0)
        ui.scheduleDate.setStretch(1, 1)
        ui.scheduleDateButton.setSpacing(14)
        ui.scheduleDate.setAlignment(ui.scheduleDateButton, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ui.scheduleDate.setAlignment(ui.scheduleDateLabels, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ui.scheduleDateLabels.setSpacing(18)
        ui.scheduleDateLabels.setStretch(0, 1)
        ui.scheduleDateLabels.setStretch(1, 0)
        ui.scheduleDateLabelsDate.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ui.scheduleDateLabelsOddity.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        ui.scheduleLessons.setContentsMargins(0, 0, 0, 0)
        ui.scheduleLessons.setAlignment(ui.scheduleLessonsLesson, Qt.AlignmentFlag.AlignTop)
        ui.scheduleLessonsLesson.setHorizontalSpacing(16)
        ui.scheduleLessonsLesson.setVerticalSpacing(16)

        ui.verticalLayout_11.setContentsMargins(0, 0, 0, 0)
        ui.mainGroups.setContentsMargins(104, 34, 104, 0)
        ui.mainGroups.setSpacing(22)
        ui.mainGroups.setStretch(0, 0)
        ui.mainGroups.setStretch(1, 1)
        ui.groupsTips.setSpacing(4)

        ui.verticalLayout_12.setContentsMargins(0, 0, 0, 0)
        ui.verticalLayout_12.setSpacing(28)
        ui.verticalLayout_12.setStretch(0, 0)
        ui.verticalLayout_12.setStretch(1, 1)
        ui.mainSettings.setContentsMargins(104, 34, 104, 0)
        ui.settingsCurrent.setSpacing(4)

        ui.settingsAlternative.setContentsMargins(104, 0, 104, 0)
        ui.settingsAlternative.setSpacing(28)
        ui.settingsAlternative.setStretch(0, 0)
        ui.settingsAlternative.setStretch(1, 1)
        ui.settingsAlternativeAction.setSpacing(0)

        for layout in (ui.verticalLayout_15, ui.verticalLayout_19, ui.verticalLayout_23, ui.verticalLayout_27):
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

        ui.settingsScheduleMain.setContentsMargins(0, 8, 0, 0)
        ui.settingsScheduleMain.setSpacing(20)
        ui.settingsScheduleMain.setStretch(0, 0)
        ui.settingsScheduleMain.setStretch(1, 1)
        ui.settingsScheduleChange.setSpacing(18)
        ui.settingsScheduleChange.setStretch(0, 1)
        ui.settingsScheduleChange.setStretch(1, 0)
        ui.settingsScheduleChangeAction.setAlignment(ui.settingsScheduleChangeActionButton, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        ui.settingsGroupsMain.setContentsMargins(0, 8, 0, 0)
        ui.settingsGroupsMain.setSpacing(20)
        ui.settingsGroupsMain.setStretch(0, 0)
        ui.settingsGroupsMain.setStretch(1, 1)
        ui.settingsGroupsChange.setSpacing(18)
        ui.settingsGroupsChange.setStretch(0, 1)
        ui.settingsGroupsChange.setStretch(1, 0)
        ui.settingsGroupsChangeAction.setAlignment(ui.settingsGroupsChangeActionButton, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        ui.settingsStudentsMain.setContentsMargins(0, 8, 0, 0)
        ui.settingsStudentsMain.setSpacing(20)
        ui.settingsStudentsMain.setStretch(0, 0)
        ui.settingsStudentsMain.setStretch(1, 1)
        ui.settingsStudentsChange.setSpacing(18)
        ui.settingsStudentsChange.setStretch(0, 0)
        ui.settingsStudentsChange.setStretch(1, 1)
        ui.settingsStudentsChange.setStretch(2, 0)
        ui.settingsStudentsChangeChoose.setAlignment(ui.settingsStudentsChangeChooseButton, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        ui.settingsStudentsChangeAction.setAlignment(ui.settingsStudentsChangeActionButton, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        ui.SettingsSemesterMain.setContentsMargins(0, 8, 0, 0)
        ui.SettingsSemesterMain.setSpacing(22)
        ui.SettingsSemesterMain.setStretch(0, 0)
        ui.SettingsSemesterMain.setStretch(1, 0)
        ui.SettingsSemesterMain.setStretch(2, 1)
        ui.settingsSemesterAction.setSpacing(18)
        ui.settingsSemesterAction.setStretch(0, 0)
        ui.settingsSemesterAction.setStretch(1, 0)
        ui.settingsSemesterAction.setStretch(2, 0)
        ui.settingsSemesterActionDate.setSpacing(8)
        ui.settingsSemesterActionDate.setStretch(0, 0)
        ui.settingsSemesterActionDate.setStretch(1, 0)
        ui.settingsSemesterActionDate.setStretch(2, 0)
        ui.settingsSemesterActionWeek.setSpacing(14)
        ui.settingsSemesterActionWeek.setStretch(0, 1)
        ui.settingsSemesterActionWeek.setStretch(1, 0)
        ui.settingsSemesterActionWeekInput.setSpacing(8)
        ui.settingsSemesterActionWeekInput.setStretch(0, 0)
        ui.settingsSemesterActionWeekInput.setStretch(1, 0)
        ui.settingsSemesterActionWeekInput.setStretch(2, 0)
        ui.settingsSemesterActionWeekChange.setSpacing(8)
        ui.settingsSemesterActionWeekChange.setAlignment(ui.settingsSemesterActionWeekChangeButtonIncrease, Qt.AlignmentFlag.AlignLeft)
        ui.settingsSemesterActionWeekChange.setAlignment(ui.settingsSemesterActionWeekChangeButtonDecrease, Qt.AlignmentFlag.AlignLeft)
        ui.settingsSemesterActionSave.setAlignment(ui.settingsSemesterActionSaveButton, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(2000, 1200)
    window.show()

    sys.exit(app.exec())


main()
