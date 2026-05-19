from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)

from ui.MainWindowUI import Ui_MainWindow
import ui.MainWindowUI

import sys


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.sourceWidget.setVisible(True)
        self.ui.mainWidget.setCurrentWidget(self.ui.pageSchedule)

        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QMainWindow {
                background-color: #0f172a;
            }

            QLabel {
                color: #e2e8f0;
                background: transparent;
                font-size: 28px;
            }

            QPushButton {
                background-color: #1e293b;
                color: #f8fafc;

                border: 1px solid #334155;
                border-radius: 12px;

                padding: 10px 18px;

                min-height: 42px;

                font-size: 15px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #334155;
                border: 1px solid #475569;
            }

            QPushButton:pressed {
                background-color: #1d4ed8;
            }

            QPushButton:checked {
                background-color: #2563eb;
                border: 1px solid #3b82f6;
            }

            QTextEdit {
                background-color: #111827;

                border: 1px solid #334155;
                border-radius: 10px;

                padding: 10px;

                font-size: 14px;
            }

            QLineEdit {
                background-color: #111827;

                border: 1px solid #334155;
                border-radius: 10px;

                padding: 8px 12px;

                min-height: 36px;

                font-size: 14px;
            }

            QSpinBox {
                background-color: #111827;

                border: 1px solid #334155;
                border-radius: 10px;

                padding: 6px 10px;

                min-height: 34px;

                font-size: 14px;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QStackedWidget {
                background: transparent;
            }

            QFrame {
                border: none;
                background: transparent;
            }

            QMenuBar {
                background-color: #111827;
                color: #e2e8f0;

                padding: 4px;

                font-size: 13px;
            }

            QMenuBar::item:selected {
                background-color: #1e293b;
                border-radius: 6px;
            }

            QMenu {
                background-color: #111827;
                color: #e2e8f0;

                border: 1px solid #334155;

                padding: 6px;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0;
            }

            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 5px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #475569;
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


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(2000, 1200)
    window.show()

    sys.exit(app.exec())


main()