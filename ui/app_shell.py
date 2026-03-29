from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)
from ui.mtr import MTRWidget
from ui.scanner_view import ScannerView
from ui.sip_alg_view import SipAlgView
from ui.traceroute_view import TracerouteView


class AppShellWindow(QMainWindow):
    _PAGE_TITLES: dict[str, str] = {
        "dashboard": "Welcome to Advanced Network Tool",
        "ip_scanner": "Welcome to IP Scanner",
        "mtr": "Welcome to MTR",
        "traceroute": "Welcome to Traceroute",
        "sip_alg_detector": "Welcome to SIP ALG Detector",
        "system_info": "Welcome to System Info",
        "full_report": "Welcome to Full Report",
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Network Tool Dashboard")
        self.resize(1200, 750)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = self._build_sidebar()
        content = self._build_content_area()

        root.addWidget(sidebar)
        root.addWidget(content, 1)

        self._apply_styles()
        self._set_active_nav("dashboard")

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame(self)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(12)

        logo_label = QLabel(sidebar)
        logo_label.setFixedWidth(160)
        logo_label.setFixedHeight(120)
        logo_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setContentsMargins(0, 0, 0, 0)

        logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
        logo_pixmap = QPixmap(str(logo_path))
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaled(
                logo_label.width(),
                logo_label.height(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            logo_label.setPixmap(
                scaled_logo
            )
        else:
            logo_label.setText("Network Tool")
            logo_label.setObjectName("sidebarTitle")

        layout.addWidget(logo_label)
        layout.addSpacing(20)

        self.nav_buttons: dict[str, QPushButton] = {}
        nav_items = [
            ("dashboard", "Dashboard"),
            ("ip_scanner", "IP Scanner"),
            ("mtr", "MTR"),
            ("traceroute", "Traceroute"),
            ("sip_alg_detector", "SIP ALG Detector"),
            ("system_info", "System Info"),
            ("full_report", "Full Report"),
        ]
        for nav_key, nav_label in nav_items:
            btn = QPushButton(nav_label, sidebar)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setMinimumHeight(44)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setProperty("navRole", "item")
            layout.addWidget(btn)
            self.nav_buttons[nav_key] = btn

        layout.addStretch(1)

        self.nav_buttons["dashboard"].clicked.connect(
            lambda: self._switch_page(0, "dashboard")
        )
        self.nav_buttons["ip_scanner"].clicked.connect(
            lambda: self._switch_page(1, "ip_scanner")
        )
        self.nav_buttons["mtr"].clicked.connect(lambda: self._switch_page(2, "mtr"))
        self.nav_buttons["traceroute"].clicked.connect(
            lambda: self._switch_page(3, "traceroute")
        )
        self.nav_buttons["sip_alg_detector"].clicked.connect(
            lambda: self._switch_page(4, "sip_alg_detector")
        )
        self.nav_buttons["system_info"].clicked.connect(
            lambda: self._switch_page(5, "system_info")
        )
        self.nav_buttons["full_report"].clicked.connect(
            lambda: self._switch_page(6, "full_report")
        )
        return sidebar

    def _build_content_area(self) -> QWidget:
        content_wrap = QWidget(self)
        content_wrap.setObjectName("contentWrap")
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(16)

        self.header_bar = self._build_header_bar(content_wrap)
        content_layout.addWidget(self.header_bar)

        pages_widget = QWidget(content_wrap)
        self.pages = QStackedLayout(pages_widget)
        self.pages.setContentsMargins(0, 0, 0, 0)

        dashboard_page = self._build_dashboard_page()
        ip_scanner_page = self._build_ip_scanner_page()
        mtr_page = self._build_mtr_page()
        traceroute_page = self._build_traceroute_page()
        sip_alg_page = self._build_sip_alg_page()
        system_info_page = self._build_placeholder_page("System Info")
        full_report_page = self._build_placeholder_page("Full Report")
        self.pages.addWidget(dashboard_page)
        self.pages.addWidget(ip_scanner_page)
        self.pages.addWidget(mtr_page)
        self.pages.addWidget(traceroute_page)
        self.pages.addWidget(sip_alg_page)
        self.pages.addWidget(system_info_page)
        self.pages.addWidget(full_report_page)
        self.pages.setCurrentIndex(0)

        content_layout.addWidget(pages_widget, 1)
        return content_wrap

    def _build_header_bar(self, parent: QWidget) -> QWidget:
        self.header_bar = QWidget(parent)
        self.header_bar.setObjectName("headerBar")
        self.header_bar.setFixedHeight(70)
        self.header_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self.header_bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(15)

        self.header_label = QLabel(self._PAGE_TITLES["dashboard"], self.header_bar)
        self.header_label.setStyleSheet(
            """
            QLabel {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3fb8c9,
                    stop: 1 #5b7cff
                );
                color: white;
                border-radius: 18px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 600;
            }
            """
        )

        self.search_bar = QLineEdit(self.header_bar)
        self.search_bar.setPlaceholderText("Search")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setFixedHeight(32)
        self.search_bar.setStyleSheet(
            """
            QLineEdit {
                background-color: #2c356b;
                color: #e8edff;
                border: 1px solid #3a4581;
                border-radius: 15px;
                padding: 6px 12px;
            }
            """
        )

        icon_style = """
            QPushButton {
                background-color: #2c356b;
                border-radius: 15px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
                border: 1px solid #3a4581;
                color: #d8ddf7;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #35417a;
            }
        """
        self.header_icon_bell = QPushButton("\u25cb", self.header_bar)
        self.header_icon_bell.setCursor(Qt.PointingHandCursor)
        self.header_icon_bell.setStyleSheet(icon_style)
        self.header_icon_user = QPushButton("\u25cf", self.header_bar)
        self.header_icon_user.setCursor(Qt.PointingHandCursor)
        self.header_icon_user.setStyleSheet(icon_style)

        layout.addWidget(self.header_label)
        layout.addWidget(self.search_bar, 1)
        layout.addWidget(self.header_icon_bell)
        layout.addWidget(self.header_icon_user)

        return self.header_bar

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget(self)
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        for col in range(3):
            grid.setColumnStretch(col, 1)
        for row in range(2):
            grid.setRowStretch(row, 1)
        return page

    def _build_ip_scanner_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("ipScannerPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scanner_view = ScannerView()
        layout.addWidget(self.scanner_view, 1)
        return page

    def _build_mtr_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mtr_view = MTRWidget()
        layout.addWidget(self.mtr_view, 1)
        return page

    def _build_traceroute_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("traceroutePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.traceroute_view = TracerouteView()
        layout.addWidget(self.traceroute_view, 1)
        return page

    def _build_sip_alg_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("sipAlgPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.sip_alg_view = SipAlgView()
        layout.addWidget(self.sip_alg_view, 1)
        return page

    def _build_placeholder_page(self, page_title: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = QFrame(page)
        card.setObjectName("dashCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(8)

        label = QLabel(page_title, card)
        label.setObjectName("placeholderPageLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        card_layout.addWidget(label)
        card_layout.addStretch(1)

        layout.addWidget(card, 1)
        return page

    def _create_card(self, title: str, subtitle: str) -> QWidget:
        card = QFrame(self)
        card.setObjectName("dashCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        title_label = QLabel(title, card)
        title_label.setObjectName("cardTitle")
        subtitle_label = QLabel(subtitle, card)
        subtitle_label.setObjectName("cardSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addStretch(1)
        return card

    def _switch_page(self, index: int, nav: str) -> None:
        self.pages.setCurrentIndex(index)
        self._set_active_nav(nav)

    def _set_active_nav(self, nav: str) -> None:
        for nav_key, btn in self.nav_buttons.items():
            btn.setChecked(nav_key == nav)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.header_label.setText(self._PAGE_TITLES.get(nav, "Welcome"))

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #171c3a;
            }
            #sidebar {
                background: #252c5a;
                border-right: 1px solid #2e376d;
            }
            #sidebarTitle {
                color: #f4f6ff;
                font-size: 28px;
                font-weight: 700;
                padding: 8px 0;
            }
            QPushButton[navRole="item"] {
                text-align: left;
                color: #d6dcff;
                background: #2e376d;
                border: 1px solid #39437b;
                border-radius: 20px;
                padding: 11px 14px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton[navRole="item"]:hover {
                background: #384381;
            }
            QPushButton[navRole="item"]:checked {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3ec9d3, stop: 1 #5d85ff
                );
                color: #ffffff;
                border: none;
            }
            #contentWrap {
                background: #1d2450;
            }
            #headerBar {
                background: #212959;
                border-radius: 14px;
                border: 1px solid #2c356b;
            }
            #dashCard {
                background: #252d61;
                border: 1px solid #313b75;
                border-radius: 14px;
            }
            #cardTitle {
                color: #eef2ff;
                font-size: 15px;
                font-weight: 700;
            }
            #cardSubtitle {
                color: #aab3de;
                font-size: 13px;
            }
            #placeholderPageLabel {
                color: #dde3ff;
                font-size: 24px;
                font-weight: 600;
            }
            #ipScannerPage {
                background: transparent;
            }
            #traceroutePage {
                background: transparent;
            }
            #sipAlgPage {
                background: transparent;
            }
            """
        )


if __name__ == "__main__":
    app = QApplication([])
    window = AppShellWindow()
    window.show()
    raise SystemExit(app.exec())
