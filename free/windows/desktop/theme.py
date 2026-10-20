import sys
from pathlib import Path

BG = "#0D0A14"
CARD = "#16121F"
CARD_HOVER = "#1C1628"
DIALOG = "#1A1525"
POPOVER = "#1E1829"
TOAST = "#241C33"
TEXT = "#EEEAF7"
DIM = "rgba(238, 234, 247, 0.58)"
FAINT = "rgba(238, 234, 247, 0.45)"
BORDER = "rgba(255, 255, 255, 0.06)"
LINE = "rgba(255, 255, 255, 0.05)"
ACCENT = "#B39DFF"
LILAC = "#C4B5FD"
VIOLET = "#7C3AED"
SOFT = "#E4DBFF"
SUCCESS = "#6EE7B7"
ERROR = "#FCA5A5"

GRADIENT = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9B6DFF, stop:1 #6D28D9)"
GRADIENT_HOVER = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #AA82FF, stop:1 #7C3AED)"
GRADIENT_DOWN = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8B5CF6, stop:1 #5B21B6)"

if sys.platform == "win32":
    FONTS = ["Segoe UI Variable Text", "Segoe UI", "sans-serif"]
    MONO = "Cascadia Mono, Consolas, monospace"
else:
    FONTS = ["Inter", "Cantarell", "Noto Sans", "sans-serif"]
    MONO = "JetBrains Mono, DejaVu Sans Mono, monospace"

CHECK = (Path(__file__).resolve().parent / "icons" / "check.svg").as_posix()

STYLE = f"""
* {{ outline: none; }}
QWidget {{ color: {TEXT}; font-size: 14px; }}
QMainWindow, #root {{ background: {BG}; }}
QToolTip {{ background: {POPOVER}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 8px;
            padding: 5px 9px; }}

/* ---- Header ---- */
#title {{ font-weight: 800; font-size: 15px; letter-spacing: 0.3px; }}
#subtitle {{ color: rgba(238, 234, 247, 0.5); font-size: 12px; }}

/* ---- Scrolling ---- */
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 0.12); border-radius: 3px; min-height: 40px;
                               margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255, 255, 255, 0.22); margin: 0; border-radius: 3px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
QScrollBar:horizontal {{ height: 0; }}

/* ---- Status bar (hero) ---- */
#hero {{ border-radius: 18px; border: 1px solid {BORDER}; background: {CARD}; }}
#hero[anchored="true"] {{ border: 1px solid rgba(139, 92, 246, 0.28); background: #1B1529; }}
#heroTitle {{ font-size: 20px; font-weight: 800; }}
#heroSubtitle {{ color: rgba(238, 234, 247, 0.6); font-size: 13px; }}

/* ---- Buttons ---- */
QPushButton {{ border: none; background: transparent; }}
QPushButton[kind="cta"] {{ padding: 10px 30px; border-radius: 19px; font-size: 14px; font-weight: 800;
                          color: white; background: {GRADIENT}; }}
QPushButton[kind="cta"]:hover {{ background: {GRADIENT_HOVER}; }}
QPushButton[kind="cta"]:pressed {{ background: {GRADIENT_DOWN}; }}
QPushButton[kind="cta"]:disabled {{ background: rgba(255, 255, 255, 0.06); color: rgba(255, 255, 255, 0.32); }}
QPushButton[kind="cta-big"] {{ padding: 13px 48px; border-radius: 22px; font-size: 15px; font-weight: 800;
                              color: white; background: {GRADIENT}; }}
QPushButton[kind="cta-big"]:hover {{ background: {GRADIENT_HOVER}; }}
QPushButton[kind="cta-big"]:pressed {{ background: {GRADIENT_DOWN}; }}
QPushButton[kind="cta-big"]:disabled {{ background: rgba(255, 255, 255, 0.06); color: rgba(255, 255, 255, 0.32); }}
QPushButton[kind="release"] {{ padding: 9px 28px; border-radius: 19px; font-size: 14px; font-weight: 800;
                              color: {SOFT}; background: rgba(255, 255, 255, 0.04);
                              border: 1px solid rgba(167, 139, 250, 0.65); }}
QPushButton[kind="release"]:hover {{ background: rgba(139, 92, 246, 0.16); }}
QPushButton[kind="release"]:disabled {{ color: rgba(255, 255, 255, 0.32); border-color: rgba(255, 255, 255, 0.1); }}
QPushButton[kind="link"] {{ color: {LILAC}; font-weight: 700; font-size: 12px; border-radius: 12px;
                           padding: 4px 12px; }}
QPushButton[kind="link"]:hover {{ background: rgba(139, 92, 246, 0.14); }}
QPushButton[kind="row-anchor"] {{ border-radius: 15px; padding: 6px 0; font-weight: 800; font-size: 13px;
                                 color: white; background: {GRADIENT}; }}
QPushButton[kind="row-anchor"]:hover {{ background: {GRADIENT_HOVER}; }}
QPushButton[kind="row-anchor"]:pressed {{ background: {GRADIENT_DOWN}; }}
QPushButton[kind="row-release"] {{ border-radius: 15px; padding: 5px 0; font-weight: 800; font-size: 13px;
                                  color: {SOFT}; background: rgba(255, 255, 255, 0.04);
                                  border: 1px solid rgba(167, 139, 250, 0.65); }}
QPushButton[kind="row-release"]:hover {{ background: rgba(139, 92, 246, 0.16); }}
QPushButton[kind="row-uninstall"] {{ border-radius: 15px; padding: 6px 10px; font-weight: 800; font-size: 13px;
                                    color: {FAINT}; }}
QPushButton[kind="row-uninstall"]:hover {{ color: {ERROR}; background: rgba(248, 113, 113, 0.12); }}
QPushButton[kind="pill"] {{ border-radius: 14px; padding: 5px 14px; font-weight: 700; font-size: 12px;
                           color: {SOFT}; background: rgba(255, 255, 255, 0.04);
                           border: 1px solid rgba(167, 139, 250, 0.55); }}
QPushButton[kind="pill"]:hover {{ background: rgba(139, 92, 246, 0.16); }}
QPushButton[kind="pill-danger"] {{ border-radius: 14px; padding: 5px 14px; font-weight: 700; font-size: 12px;
                                  color: #FECACA; background: rgba(255, 255, 255, 0.04);
                                  border: 1px solid rgba(248, 113, 113, 0.6); }}
QPushButton[kind="pill-danger"]:hover {{ background: rgba(248, 113, 113, 0.14); }}
QPushButton[kind="icon"] {{ border-radius: 16px; padding: 6px; }}
QPushButton[kind="icon"]:hover {{ background: rgba(255, 255, 255, 0.07); }}
QPushButton[kind="icon-accent"] {{ border-radius: 16px; padding: 6px; background: rgba(139, 92, 246, 0.16); }}
QPushButton[kind="icon-accent"]:hover {{ background: rgba(139, 92, 246, 0.26); }}

/* Dialog buttons */
QPushButton[kind="dialog"] {{ border-radius: 12px; padding: 10px 18px; font-weight: 700; font-size: 14px;
                             background: rgba(255, 255, 255, 0.07); }}
QPushButton[kind="dialog"]:hover {{ background: rgba(255, 255, 255, 0.11); }}
QPushButton[kind="dialog-suggested"] {{ border-radius: 12px; padding: 10px 18px; font-weight: 800; font-size: 14px;
                                       color: white; background: {GRADIENT}; }}
QPushButton[kind="dialog-suggested"]:hover {{ background: {GRADIENT_HOVER}; }}
QPushButton[kind="dialog-destructive"] {{ border-radius: 12px; padding: 10px 18px; font-weight: 800;
                                         font-size: 14px; color: {ERROR}; background: rgba(248, 113, 113, 0.12); }}
QPushButton[kind="dialog-destructive"]:hover {{ background: rgba(248, 113, 113, 0.2); }}

/* Tick boxes (Never allow apps): a clear outline, violet with a white tick when ticked */
QCheckBox {{ spacing: 0; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 2px solid rgba(167, 139, 250, 0.65);
                        background: transparent; }}
QCheckBox::indicator:checked {{ border: 2px solid #8B5CF6; background: #7C3AED; image: url("{CHECK}"); }}

/* ---- Search ---- */
QLineEdit {{ min-height: 40px; border-radius: 14px; padding: 0 12px; background: {CARD};
             border: 1px solid {BORDER}; selection-background-color: {VIOLET}; font-size: 14px; }}
QLineEdit:focus {{ border: 2px solid rgba(139, 92, 246, 0.8); padding: 0 11px; }}
QLineEdit[mono="true"] {{ font-family: {MONO}; }}

/* ---- Cards, sections and rows ---- */
#card {{ background: {CARD}; border-radius: 18px; border: 1px solid {BORDER}; }}
#sectionHeader {{ border-radius: 18px; background: transparent; }}
#sectionHeader:hover {{ background: rgba(139, 92, 246, 0.07); }}
#sectionTitle {{ font-size: 15px; font-weight: 800; }}
#sectionHint, #rowSubtitle {{ color: rgba(238, 234, 247, 0.5); font-size: 12px; }}
#rowTitle {{ font-size: 14px; }}
#row {{ border-top: 1px solid {LINE}; background: transparent; }}
#row[clickable="true"]:hover {{ background: rgba(139, 92, 246, 0.07); }}
#row[last="true"] {{ border-bottom-left-radius: 18px; border-bottom-right-radius: 18px; }}
#empty {{ color: {DIM}; padding: 18px; border-top: 1px solid {LINE}; }}
#groupTitle {{ font-size: 14px; font-weight: 800; padding-left: 4px; }}
#groupDescription {{ color: {DIM}; font-size: 12px; padding-left: 4px; }}
#dim {{ color: {DIM}; }}
#caption {{ color: {DIM}; font-size: 12px; }}
#captionHeading {{ color: {DIM}; font-size: 12px; font-weight: 800; }}

/* ---- Status pages ---- */
#statusTitle {{ font-size: 26px; font-weight: 800; }}
#statusText {{ color: rgba(238, 234, 247, 0.75); font-size: 14px; }}
#pageTitle {{ font-size: 28px; font-weight: 800; }}
#stepNumber {{ min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; border-radius: 14px;
               background: rgba(139, 92, 246, 0.2); color: {LILAC}; font-weight: 800; }}

/* ---- Dialogs ---- */
#dialog {{ background: {DIALOG}; border-radius: 22px; border: 1px solid rgba(255, 255, 255, 0.07); }}
#dialogHeading {{ font-size: 18px; font-weight: 800; }}
#dialogBody {{ color: rgba(238, 234, 247, 0.72); font-size: 14px; }}
#keyLabel {{ font-family: {MONO}; font-size: 17px; letter-spacing: 1px; padding: 14px; border-radius: 14px;
             background: rgba(139, 92, 246, 0.12); color: {SOFT}; }}
#details {{ font-family: {MONO}; font-size: 11px; color: {DIM}; background: rgba(0, 0, 0, 0.25);
            border-radius: 10px; padding: 8px; }}
#nameTitle {{ font-size: 22px; font-weight: 800; }}
#versionChip {{ font-weight: 800; font-size: 12px; color: {SOFT}; background: rgba(139, 92, 246, 0.18);
                border-radius: 12px; padding: 4px 14px; }}
#timeValue {{ font-size: 22px; font-weight: 800; background: rgba(255, 255, 255, 0.05); border-radius: 12px;
              min-width: 56px; padding: 6px 0; }}
#colon {{ font-size: 22px; font-weight: 800; }}
QPushButton[kind="day"] {{ min-width: 40px; padding: 8px 2px; border-radius: 12px; font-weight: 700;
                          background: rgba(255, 255, 255, 0.06); }}
QPushButton[kind="day"]:hover {{ background: rgba(255, 255, 255, 0.1); }}
QPushButton[kind="day"]:checked {{ color: white; background: {GRADIENT}; }}

/* ---- Menu and toast ---- */
QMenu {{ background: {POPOVER}; border: 1px solid {BORDER}; border-radius: 14px; padding: 6px; }}
QMenu::item {{ padding: 8px 18px; border-radius: 9px; font-size: 14px; }}
QMenu::item:selected {{ background: rgba(139, 92, 246, 0.16); }}
QMenu::item:disabled {{ color: rgba(238, 234, 247, 0.3); }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 6px 8px; }}
#toast {{ background: {TOAST}; color: #F1ECFF; border-radius: 20px; padding: 10px 22px;
          border: 1px solid rgba(139, 92, 246, 0.35); font-size: 13px; }}
"""
