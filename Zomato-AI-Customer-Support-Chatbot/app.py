import base64
import html
import re
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components

from src.agents.prompts import LIVE_STATUSES, order_timing, to_datetime
from src.database.queries import (
    get_live_orders,
    get_open_tickets,
    get_order_details,
    get_tickets_for_order,
    get_user_orders_with_items,
    get_user_profile,
)

CANCELLABLE_STATUSES = ("placed", "preparing")
PAGE_SIZE = 4  # recent orders shown per "Show more" step

st.set_page_config(
    page_title="Zomato Support",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# ARTWORK (original SVG drawings, embedded so no image files are needed)
# =========================================================
ROBOT_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' "
    "stroke-linecap='round' stroke-linejoin='round'><rect x='4' y='8' width='16' height='11' rx='3'/>"
    "<path d='M12 8V4.8'/><circle cx='12' cy='3.6' r='1.3' fill='white'/>"
    "<circle cx='9' cy='13' r='1.3' fill='white' stroke='none'/><circle cx='15' cy='13' r='1.3' fill='white' stroke='none'/>"
    "<path d='M9.5 16.3h5'/><path d='M2 12.5v3M22 12.5v3'/></svg>"
)

HERO_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 600 420' preserveAspectRatio='xMidYMid slice'>
<defs>
<linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#EC4458'/><stop offset='1' stop-color='#B31B32'/></linearGradient>
<pattern id='chk' width='44' height='44' patternUnits='userSpaceOnUse'>
<rect width='22' height='22' fill='#fff' opacity='.09'/><rect x='22' y='22' width='22' height='22' fill='#fff' opacity='.09'/></pattern>
</defs>
<rect width='600' height='420' fill='url(#g)'/><rect width='600' height='420' fill='url(#chk)'/>
<g fill='#fff' opacity='.55'>
<circle cx='150' cy='60' r='3'/><circle cx='235' cy='30' r='2.5'/><circle cx='380' cy='48' r='3'/><circle cx='300' cy='110' r='2.5'/>
<circle cx='180' cy='250' r='3'/><circle cx='420' cy='265' r='2.5'/><circle cx='330' cy='300' r='3'/><circle cx='40' cy='200' r='2.5'/>
<circle cx='560' cy='215' r='3'/><rect x='260' y='70' width='10' height='4' rx='2' transform='rotate(25 265 72)'/>
<rect x='355' y='130' width='10' height='4' rx='2' transform='rotate(-30 360 132)'/>
<rect x='120' y='150' width='10' height='4' rx='2' transform='rotate(40 125 152)'/></g>
<g><circle cx='70' cy='85' r='54' fill='#fff'/><circle cx='70' cy='85' r='44' fill='#2E8B57'/><circle cx='70' cy='85' r='34' fill='none' stroke='#fff' stroke-width='3'/>
<ellipse cx='70' cy='75' rx='9' ry='13' fill='#fff'/><rect x='67' y='86' width='6' height='24' rx='3' fill='#fff'/></g>
<g transform='rotate(-18 200 110)'><rect x='185' y='28' width='5' height='46' rx='2.5' fill='#fff'/><rect x='196' y='28' width='5' height='46' rx='2.5' fill='#fff'/>
<rect x='207' y='28' width='5' height='46' rx='2.5' fill='#fff'/><rect x='185' y='64' width='27' height='14' rx='7' fill='#fff'/><rect x='194' y='74' width='9' height='90' rx='4.5' fill='#fff'/></g>
<g><circle cx='505' cy='85' r='80' fill='#fff'/><circle cx='505' cy='85' r='64' fill='#F08A24'/><circle cx='505' cy='85' r='50' fill='#F5A94B'/>
<path d='M470 85 q 18 -22 36 0 t 36 0' fill='none' stroke='#fff' stroke-width='5' stroke-linecap='round'/>
<circle cx='488' cy='62' r='5' fill='#3E8E41'/><circle cx='526' cy='108' r='5' fill='#3E8E41'/><circle cx='520' cy='60' r='4' fill='#3E8E41'/></g>
<g><circle cx='105' cy='372' r='102' fill='#fff'/><circle cx='105' cy='372' r='86' fill='none' stroke='#F3D5D9' stroke-width='3'/>
<rect x='52' y='352' width='106' height='24' rx='11' fill='#D98A3D'/><rect x='46' y='334' width='118' height='22' rx='11' fill='#5A2E1B'/>
<polygon points='46,334 164,334 146,350 64,350' fill='#F8C630'/>
<path d='M44 328 q 9 -13 18 0 t 18 0 t 18 0 t 18 0 t 18 0 t 18 0 v6 h-108z' fill='#6CB33F'/>
<rect x='56' y='318' width='98' height='9' rx='4' fill='#E0412F'/>
<path d='M52 318 a53 48 0 0 1 106 0 z' fill='#E59A47'/>
<ellipse cx='85' cy='294' rx='5' ry='2.5' fill='#FCE8C2'/><ellipse cx='108' cy='286' rx='5' ry='2.5' fill='#FCE8C2'/><ellipse cx='130' cy='296' rx='5' ry='2.5' fill='#FCE8C2'/></g>
<g><circle cx='498' cy='372' r='112' fill='#fff'/><circle cx='498' cy='372' r='94' fill='#E7A23B'/><circle cx='498' cy='372' r='80' fill='#F7C85A'/>
<g fill='#C73A2B'><circle cx='468' cy='346' r='13'/><circle cx='522' cy='338' r='13'/><circle cx='538' cy='384' r='13'/><circle cx='490' cy='408' r='13'/><circle cx='452' cy='388' r='13'/><circle cx='500' cy='372' r='12'/></g>
<g fill='#3E8E41'><ellipse cx='482' cy='360' rx='7' ry='3.5' transform='rotate(30 482 360)'/><ellipse cx='520' cy='362' rx='7' ry='3.5' transform='rotate(-20 520 362)'/><ellipse cx='470' cy='404' rx='7' ry='3.5'/></g>
<g stroke='#E7A23B' stroke-width='3'><line x1='498' y1='372' x2='498' y2='292'/><line x1='498' y1='372' x2='568' y2='332'/><line x1='498' y1='372' x2='428' y2='332'/></g></g>
<text x='300' y='214' text-anchor='middle' font-family='Arial, Helvetica, sans-serif' font-size='92' font-style='italic' font-weight='800' letter-spacing='-4' fill='#fff'>zomato</text>
</svg>"""


SQUARE_SVG = """<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink' viewBox='0 0 300 300'>
<defs>
<linearGradient id='g' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#FFF8F9'/><stop offset='1' stop-color='#FDECEE'/></linearGradient>
</defs>
<rect width='300' height='300' fill='url(#g)'/>
<image x='75' y='28' width='150' height='130' href='data:image/webp;base64,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'/>
<text x='150' y='203' text-anchor='middle' font-family='Arial, Helvetica, sans-serif' font-size='16' fill='#4A5060'>Need help with your order?</text>
<text x='150' y='246' text-anchor='middle' font-family='Arial, Helvetica, sans-serif' font-size='30' font-weight='800' fill='#1C1C1C'>Ask Zomato AI</text>
</svg>"""

def rider_svg(night: bool) -> str:
    if night:
        sky1, sky2, city, sun, road, dash, win = "#2A1822", "#4B2230", "#3A2230", "#F2E6C4", "#150E10", "#6B5A5E", "#F5C86A"
    else:
        sky1, sky2, city, sun, road, dash, win = "#FFEBED", "#FFD0D6", "#F7B9C1", "#FFFFFF", "#3B2A2E", "#FFFFFF", "#FFFFFF"
    return f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 260' preserveAspectRatio='xMidYMax slice'>
<defs><linearGradient id='s' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{sky1}'/><stop offset='1' stop-color='{sky2}'/></linearGradient></defs>
<rect width='400' height='260' fill='url(#s)'/>
<circle cx='62' cy='56' r='30' fill='{sun}' opacity='.85'/>
<g fill='{city}'><rect x='10' y='140' width='38' height='80'/><rect x='52' y='110' width='34' height='110'/><rect x='92' y='150' width='44' height='70'/>
<rect x='250' y='120' width='40' height='100'/><rect x='296' y='94' width='36' height='126'/><rect x='338' y='132' width='52' height='88'/></g>
<g fill='{win}' opacity='.55'><rect x='60' y='122' width='6' height='6'/><rect x='72' y='122' width='6' height='6'/><rect x='60' y='140' width='6' height='6'/><rect x='72' y='140' width='6' height='6'/>
<rect x='304' y='108' width='6' height='6'/><rect x='318' y='108' width='6' height='6'/><rect x='304' y='128' width='6' height='6'/><rect x='318' y='128' width='6' height='6'/><rect x='258' y='136' width='6' height='6'/><rect x='272' y='136' width='6' height='6'/></g>
<path d='M340 112 c-17 -21 -28 -32 -28 -47 a28 28 0 0 1 56 0 c0 15 -11 26 -28 47z' fill='#E23744'/><circle cx='340' cy='65' r='10' fill='#fff'/>
<rect y='212' width='400' height='48' fill='{road}'/>
<g fill='{dash}' opacity='.7'><rect x='10' y='234' width='34' height='4' rx='2'/><rect x='84' y='234' width='34' height='4' rx='2'/><rect x='158' y='234' width='34' height='4' rx='2'/><rect x='232' y='234' width='34' height='4' rx='2'/><rect x='306' y='234' width='34' height='4' rx='2'/></g>
<g stroke='#fff' stroke-width='4' stroke-linecap='round' opacity='.75'><line x1='14' y1='160' x2='62' y2='160'/><line x1='4' y1='182' x2='46' y2='182'/><line x1='24' y1='138' x2='56' y2='138'/></g>
<g>
<circle cx='150' cy='208' r='27' fill='#2B2B2E'/><circle cx='150' cy='208' r='13' fill='#D9D9DE'/><circle cx='150' cy='208' r='4' fill='#2B2B2E'/>
<circle cx='282' cy='208' r='27' fill='#2B2B2E'/><circle cx='282' cy='208' r='13' fill='#D9D9DE'/><circle cx='282' cy='208' r='4' fill='#2B2B2E'/>
<path d='M118 200 q-6 -34 28 -38 h58 v38 z' fill='#E23744'/>
<rect x='160' y='186' width='86' height='14' rx='7' fill='#C21F31'/>
<path d='M246 202 L262 150 L284 140' fill='none' stroke='#2B2B2E' stroke-width='8' stroke-linecap='round' stroke-linejoin='round'/>
<path d='M236 188 q10 -40 44 -34 l8 40 h-52z' fill='#E23744'/>
<line x1='258' y1='140' x2='296' y2='134' stroke='#2B2B2E' stroke-width='7' stroke-linecap='round'/>
<rect x='108' y='116' width='66' height='60' rx='9' fill='#E23744' stroke='#B31B32' stroke-width='3'/>
<text x='141' y='160' text-anchor='middle' font-family='Arial, Helvetica, sans-serif' font-size='44' font-style='italic' font-weight='800' fill='#fff'>z</text>
<rect x='176' y='118' width='34' height='58' rx='15' fill='#1F2937' transform='rotate(8 193 147)'/>
<path d='M196 128 L270 144' stroke='#1F2937' stroke-width='12' stroke-linecap='round'/>
<path d='M190 170 L214 182 L240 198' stroke='#374151' stroke-width='13' stroke-linecap='round' stroke-linejoin='round' fill='none'/>
<ellipse cx='246' cy='202' rx='11' ry='5' fill='#111827'/>
<circle cx='200' cy='100' r='17' fill='#F1C27D'/>
<path d='M183 98 a17 17 0 0 1 34 0 z' fill='#fff'/><rect x='183' y='95' width='34' height='4' fill='#E23744'/>
<rect x='205' y='99' width='13' height='7' rx='3' fill='#2B2B2E' opacity='.8'/>
</g></svg>"""


def _b64(svg: str) -> str:
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def asset_css(theme: str) -> str:
    night = theme == "dark"
    return (
        ".wa-av, .z-agent-avatar, .sb-av { background:#E23744 url(data:image/svg+xml;base64," + _b64(ROBOT_SVG) + ") center/58% no-repeat; }"
        ".z-hero { background:url(data:image/svg+xml;base64," + _b64(HERO_SVG) + ") center/cover no-repeat; }"
        ".sb-sq { background:url(data:image/svg+xml;base64," + _b64(SQUARE_SVG) + ") center/cover no-repeat; }"
        ".ord-img { background:url(data:image/svg+xml;base64," + _b64(rider_svg(night)) + ") center bottom/cover no-repeat; }"
    )


# =========================================================
# THEMES (all colours come from CSS variables, so light / dark never clash)
# =========================================================
LIGHT = {
    "bg": "#FFFFFF", "canvas": "#F2F0EE", "surface": "#FFFFFF", "soft": "#FAFAFA", "dots": "rgba(0,0,0,.045)",
    "text": "#1C1C1C", "sub": "#6B6B6B", "line": "#E6E6E6", "line2": "#CFCFCF",
    "red": "#E23744", "red-dark": "#CB202D", "red-soft": "#FFF0F1", "opt": "#E23744",
    "input": "#FFFFFF", "track": "#E5E5E5", "shadow": "rgba(0,0,0,.08)",
    "warn-bg": "#FEF3C7", "warn": "#B45309", "ok-bg": "#E8F5E9", "ok": "#1E8E3E",
    "muted-bg": "#F1F1F1", "muted": "#555555",
}
DARK = {
    "bg": "#121214", "canvas": "#0B0B0D", "surface": "#1D1D20", "soft": "#242428", "dots": "rgba(255,255,255,.035)",
    "text": "#F1F1F3", "sub": "#A3A3AB", "line": "#2C2C31", "line2": "#3C3C43",
    "red": "#E23744", "red-dark": "#CB202D", "red-soft": "rgba(226,55,68,.16)", "opt": "#FF7C88",
    "input": "#1D1D20", "track": "#36363C", "shadow": "rgba(0,0,0,.5)",
    "warn-bg": "rgba(245,158,11,.16)", "warn": "#FBBF6B", "ok-bg": "rgba(52,168,83,.16)", "ok": "#6FD08C",
    "muted-bg": "#2A2A2E", "muted": "#B5B5BC",
}

FONT_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');"

BASE_CSS = """
html, body, .stApp, .stApp p, .stApp label, .stApp button, .stApp input, .stApp textarea,
.stApp [data-testid="stMarkdownContainer"] { font-family:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
.stApp { background:var(--bg) !important; color:var(--text); overflow-x:hidden; }
header[data-testid="stHeader"], footer, #MainMenu, [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stDecoration"] { display:none !important; }
.block-container { padding:0 1.5rem 0 1.5rem !important; }

.stApp [data-testid="stMarkdownContainer"] p, .stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stMarkdownContainer"] strong, .stApp label p { color:var(--text); }

/* ---------- Navbar ---------- */
.st-key-nav { padding:10px 0; margin:0 0 6px 0; }
.z-logo { color:var(--red); font-size:1.9rem; font-weight:800; font-style:italic; letter-spacing:-1.5px; line-height:1; margin:0; padding:0; }
.nav-row { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.z-nav-mid { color:var(--sub); font-size:.9rem; font-weight:500; padding-left:4px; }
.z-user { display:flex; align-items:center; gap:10px; font-size:.9rem; font-weight:500; color:var(--text); padding-right:18px; }
.z-avatar { width:32px; height:32px; border-radius:50%; background:var(--red); color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.85rem; flex-shrink:0; }
.st-key-nav button { min-height:36px !important; padding:0 12px !important; }

/* ---------- Buttons ---------- */
.stApp .stButton > button { border-radius:10px; border:1px solid var(--line2); background:var(--surface); min-height:38px; box-shadow:none; padding:0 14px; }
.stApp .stButton > button p { color:var(--text) !important; font-size:.85rem; font-weight:600; }
.stApp .stButton > button span[data-testid="stIconMaterial"] { color:var(--text) !important; }
.stApp .stButton > button:hover { border-color:var(--red); background:var(--red-soft); }
.stApp .stButton > button:hover p, .stApp .stButton > button:hover span[data-testid="stIconMaterial"] { color:var(--red) !important; }
.stApp [data-testid="stFormSubmitButton"] > button { background:var(--red); border:1px solid var(--red); border-radius:12px; min-height:46px; }
.stApp [data-testid="stFormSubmitButton"] > button p { color:#fff !important; font-weight:600; }
.stApp [data-testid="stFormSubmitButton"] > button:hover { background:var(--red-dark); border-color:var(--red-dark); }

/* ---------- Login ---------- */
.st-key-logincard { background:var(--surface); border-radius:22px; padding:0; min-height:max(80vh, 540px); overflow:hidden; gap:0 !important; box-shadow:0 24px 60px rgba(0,0,0,.30); margin-top:1vh; }
.z-hero { height:calc(80vh - 335px); min-height:190px; border-radius:0 0 40px 40px; }
.st-key-loginbody { padding:20px 30px 16px; }
.st-key-loginbody [data-testid="stForm"] { border:none; padding:0; }
.z-h1 { font-size:1.5rem; font-weight:700; margin:0 0 4px 0; letter-spacing:-.3px; color:var(--text); text-align:center; }
.z-sub { color:var(--sub); font-size:.92rem; margin:0 0 14px 0; text-align:center; }
.z-login-note { color:var(--sub); font-size:.76rem; text-align:center; margin-top:10px; }
.stApp [data-testid="stTextInputRootElement"], .stApp [data-testid="stTextInputRootElement"] > div, .stApp [data-baseweb="input"], .stApp [data-baseweb="input"] > div, .stApp [data-baseweb="base-input"] { background:var(--input) !important; background-color:var(--input) !important; border-color:var(--line2) !important; border-radius:12px !important; }
.stApp [data-testid="InputInstructions"] { display:none !important; }
.stApp [data-baseweb="input"]:focus-within { border-color:var(--red) !important; box-shadow:0 0 0 1px var(--red) !important; }
.stApp [data-testid="stTextInput"] input { background:var(--input) !important; color:var(--text) !important; padding:12px 14px !important; -webkit-text-fill-color:var(--text); }
.stApp [data-testid="stTextInput"] input::placeholder { color:var(--sub) !important; opacity:1; -webkit-text-fill-color:var(--sub); }
.stApp [data-testid="stTextInput"] label p { color:var(--sub) !important; font-size:.8rem !important; font-weight:600 !important; }
.stApp [data-testid="stAlert"] { background:var(--red-soft) !important; border:1px solid var(--red) !important; border-radius:10px !important; }
.stApp [data-testid="stAlert"] * { color:var(--text) !important; }

/* ---------- Sidebar ---------- */
.st-key-sidebar { border:1px solid var(--line); border-radius:16px; background:var(--surface); padding:18px 16px; box-shadow:0 2px 14px var(--shadow); min-height:calc(100vh - 128px); gap:1.1rem; overflow-y:auto; }
.st-key-sidebar [data-testid="stMarkdown"], .st-key-sidebar [data-testid="stMarkdownContainer"] { margin-bottom:0 !important; }
.st-key-sb_btns { gap:.6rem; }
.sb-profile { display:flex; align-items:center; gap:14px; padding-bottom:16px; border-bottom:1px solid var(--line); }
.sb-profile .z-avatar { width:46px; height:46px; font-size:1.1rem; }
.sb-lines { display:flex; flex-direction:column; align-items:flex-start; text-align:left; gap:2px; min-width:0; }
.sb-name { font-weight:700; font-size:1rem; color:var(--text); line-height:1.25; }
.sb-sub { font-size:.8rem; color:var(--sub); line-height:1.35; }
.sb-sq { width:min(100%, 34vh); aspect-ratio:1/1; border-radius:16px; margin:2px auto 0; box-shadow:0 4px 16px var(--shadow); }
.sb-title { font-size:.7rem; letter-spacing:.8px; text-transform:uppercase; color:var(--sub); font-weight:600; margin:12px 0 0; }
.sb-foot { font-size:.76rem; color:var(--sub); line-height:1.55; padding-top:14px; border-top:1px solid var(--line); }
.st-key-sidebar .stButton > button { justify-content:flex-start; border-radius:12px; }
.st-key-sidebar .stButton > button > div { justify-content:flex-start; width:100%; }

/* ---------- Chat card ---------- */
.st-key-chatcard { border:1px solid var(--line); border-radius:16px; background-color:var(--canvas); background-image:radial-gradient(var(--dots) 1.2px, transparent 1.2px); background-size:22px 22px; overflow:hidden; gap:0 !important; box-shadow:0 2px 14px var(--shadow); }
.st-key-chathead { padding:10px 16px; border-bottom:1px solid var(--line); background:var(--surface); }
.z-agent { display:flex; align-items:center; gap:12px; }
.z-agent-avatar { width:40px; height:40px; border-radius:50%; flex-shrink:0; }
.z-agent-name { font-weight:600; line-height:1.2; font-size:.95rem; color:var(--text); }
.z-agent-status { color:var(--ok); font-size:.76rem; display:flex; align-items:center; gap:5px; }
.z-dot { width:7px; height:7px; background:#3AB757; border-radius:50%; display:inline-block; }
.st-key-msgbox { scroll-behavior:smooth; }

/* ---------- WhatsApp style bubbles ---------- */
.wa { display:flex; flex-direction:column; gap:4px; padding:10px 14px 4px; }
.wa-day { text-align:center; margin:2px 0 8px; }
.wa-day span { background:var(--surface); color:var(--sub); font-size:.7rem; font-weight:600; padding:4px 12px; border-radius:999px; box-shadow:0 1px 1px var(--shadow); }
.wa-row { display:flex; align-items:flex-end; gap:8px; }
.wa-row.me { justify-content:flex-end; }
.wa-row.first { margin-top:6px; }
.wa-av { width:30px; height:30px; border-radius:50%; flex-shrink:0; }
.wa-av.ghost { background:transparent !important; }
.wa-bubble { max-width:75%; width:fit-content; padding:8px 13px 6px; border-radius:18px; font-size:.93rem; line-height:1.45; word-wrap:break-word; overflow-wrap:anywhere; box-shadow:0 1px 1px var(--shadow); }
.wa-row.bot .wa-bubble { background:var(--surface); border:1px solid var(--line); color:var(--text); }
.wa-row.me .wa-bubble { background:var(--red); color:#fff; }
.wa-row.bot .wa-bubble.first { border-top-left-radius:5px; }
.wa-row.me .wa-bubble.first { border-top-right-radius:5px; }
.wa-bubble.err { background:var(--warn-bg) !important; border-color:var(--warn) !important; color:var(--warn) !important; }
.wa-bubble a { color:var(--red); font-weight:600; }
.wa-row.me .wa-bubble a { color:#fff; }
.wa-time { display:block; text-align:right; font-size:.66rem; opacity:.7; margin-top:3px; line-height:1; }
.wa-tick { margin-left:4px; letter-spacing:-2px; }
.wa-typing { display:flex; gap:4px; padding:5px 2px 3px; }
.wa-typing i { width:7px; height:7px; border-radius:50%; background:var(--sub); opacity:.5; animation:zbounce 1.2s infinite; }
.wa-typing i:nth-child(2) { animation-delay:.15s; }
.wa-typing i:nth-child(3) { animation-delay:.3s; }
@keyframes zbounce { 0%,60%,100% { transform:translateY(0); opacity:.4; } 30% { transform:translateY(-5px); opacity:1; } }

/* Options under the last bot message (WhatsApp style quick replies) */
.st-key-opts { gap:0 !important; max-width:70%; margin:4px 0 10px 56px; border:1px solid var(--line); border-radius:16px; background:var(--surface); overflow:hidden; box-shadow:0 1px 3px var(--shadow); }
.st-key-opts .stButton > button { border:none !important; border-top:1px solid var(--line) !important; border-radius:0 !important; background:transparent !important; min-height:46px; width:100%; padding:0 16px; }
.st-key-opts .stButton > button > div { justify-content:flex-start !important; width:100%; }
.st-key-opts [data-testid="stElementContainer"]:first-child .stButton > button { border-top:none !important; }
.st-key-opts .stButton > button p { color:var(--opt) !important; font-weight:600; text-align:left; width:100%; }
.st-key-opts .stButton > button span[data-testid="stIconMaterial"] { color:var(--opt) !important; }
.st-key-opts .stButton > button:hover { background:var(--red-soft) !important; }

/* Message box: one outer line only, the inside blends with the background */
[data-testid="stChatInput"] { background:var(--input) !important; border:1px solid var(--line2) !important; border-radius:999px !important; box-shadow:none !important; margin:8px 14px 12px !important; width:auto !important; padding:0 6px 0 10px !important; }
[data-testid="stChatInput"]:focus-within { border-color:var(--red) !important; box-shadow:0 0 0 1px var(--red) !important; }
[data-testid="stChatInput"] * { background:transparent !important; border:none !important; box-shadow:none !important; outline:none !important; color:var(--text) !important; }
[data-testid="stChatInput"] textarea::placeholder { color:var(--sub) !important; opacity:1; }
[data-testid="stChatInput"] button { background:var(--red) !important; border-radius:50% !important; }
[data-testid="stChatInput"] button svg { fill:#fff !important; color:#fff !important; }

/* ---------- Order panel ---------- */
.st-key-ordercard { border:1px solid var(--line); border-radius:16px; background:var(--surface); padding:18px 18px 16px; box-shadow:0 2px 14px var(--shadow); min-height:calc(100vh - 128px); overflow-y:auto; gap:0; }
.st-key-ordercard > [data-testid="stElementContainer"]:last-child { margin-top:auto; padding-top:16px; }
.ord-img { height:clamp(120px, 26vh, 250px); border-radius:12px; }
.ord-empty { text-align:center; padding:30px 10px 8px; color:var(--sub); font-size:.88rem; line-height:1.6; }
.ord-empty b { display:block; color:var(--text); font-size:1rem; margin-bottom:6px; }
@media (max-height:760px) { .ord-img { display:none; } }
.z-title { font-size:.7rem; color:var(--sub); letter-spacing:.7px; font-weight:600; margin-bottom:6px; text-transform:uppercase; display:flex; align-items:center; gap:6px; }
.z-row { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }
.z-rest { font-size:1.05rem; font-weight:700; line-height:1.25; color:var(--text); }
.z-meta { font-size:.8rem; color:var(--sub); margin-top:2px; }
.z-sep { border:none; border-top:1px solid var(--line); margin:14px 0 10px; }
.z-line { display:flex; justify-content:space-between; font-size:.85rem; line-height:1.8; color:var(--text); }
.z-line.total { font-weight:700; border-top:1px dashed var(--line2); margin-top:6px; padding-top:6px; }
.z-banner { background:var(--warn-bg); color:var(--warn); border-radius:8px; padding:8px 12px; font-size:.8rem; font-weight:500; margin-top:12px; }
.z-banner.muted { background:var(--muted-bg); color:var(--muted); }
.z-eta { background:var(--red-soft); border-radius:8px; padding:8px 12px; margin-top:12px; font-size:.8rem; color:var(--sub); display:flex; justify-content:space-between; align-items:center; }
.z-eta b { color:var(--red); font-size:1rem; }
.z-steps { display:flex; margin:14px 0 2px; }
.z-step { flex:1; text-align:center; position:relative; font-size:.66rem; color:var(--sub); }
.z-step .c { width:16px; height:16px; border-radius:50%; background:var(--track); margin:0 auto 5px; position:relative; z-index:2; border:3px solid var(--surface); box-shadow:0 0 0 1px var(--track); }
.z-step::before { content:""; position:absolute; top:7px; left:-50%; width:100%; height:3px; background:var(--track); z-index:1; }
.z-step:first-child::before { display:none; }
.z-step.done { color:var(--text); font-weight:600; }
.z-step.done .c { background:var(--red); box-shadow:0 0 0 1px var(--red); }
.z-step.done::before { background:var(--red); }
.z-partner { background:var(--soft); border:1px solid var(--line); border-radius:10px; padding:9px 12px; margin-top:12px; display:flex; justify-content:space-between; align-items:center; font-size:.85rem; color:var(--text); }
.z-partner small { color:var(--sub); display:block; font-size:.72rem; }
.z-partner .ph { color:var(--sub); font-size:.8rem; margin-top:2px; }
.z-call { background:var(--red); color:#fff !important; text-decoration:none !important; padding:6px 14px; border-radius:8px; font-weight:600; font-size:.8rem; }

/* Badges */
.z-b { display:inline-block; padding:3px 9px; border-radius:6px; font-size:.7rem; font-weight:600; letter-spacing:.2px; white-space:nowrap; margin-left:6px; }
.z-b.live { background:var(--red-soft); color:var(--red); }
.z-b.ok { background:var(--ok-bg); color:var(--ok); }
.z-b.bad { background:var(--muted-bg); color:var(--muted); }
.z-b.warn { background:var(--warn-bg); color:var(--warn); }

/* Hidden helper iframe (fits the chat height and scrolls to the latest message) */
[data-testid="stElementContainer"]:has(iframe[height="0"]) { position:absolute; width:0; height:0; overflow:hidden; margin:0; }

@media (max-width: 900px) {
  .wa-bubble { max-width:86%; }
  .st-key-opts { max-width:92%; margin-left:14px; }
  .st-key-sidebar { display:none; }
  .st-key-ordercard { min-height:0; }
}
"""

LOGIN_BG_LIGHT = "linear-gradient(155deg,#E23744 0%,#C21F31 55%,#9E1424 100%)"
LOGIN_BG_DARK = "linear-gradient(155deg,#B3202E 0%,#7D1420 55%,#40090F 100%)"


def inject_css(stage: str, theme: str) -> None:
    palette = DARK if theme == "dark" else LIGHT
    scheme = "dark" if theme == "dark" else "light"
    variables = ":root{color-scheme:" + scheme + ";" + ";".join(f"--{k}:{v}" for k, v in palette.items()) + "}"
    if stage == "login":
        bg = LOGIN_BG_DARK if theme == "dark" else LOGIN_BG_LIGHT
        extra = (
            f".stApp {{ background:{bg} !important; }}"
            ".block-container { max-width:1180px !important; }"
            ".stApp .z-logo { color:#fff !important; }"
        )
    else:
        extra = ".block-container { max-width:1400px !important; }"
    st.markdown(f"<style>{FONT_IMPORT}{variables}{asset_css(theme)}{BASE_CSS}{extra}</style>", unsafe_allow_html=True)


# =========================================================
# LABELS & SMALL HELPERS
# =========================================================
STATUS_LABEL = {
    "placed": "Order placed",
    "preparing": "Preparing",
    "out_for_delivery": "On the way",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}
STATUS_CLASS = {"placed": "live", "preparing": "live", "out_for_delivery": "live", "delivered": "ok", "cancelled": "bad"}
ISSUE_LABEL = {
    "order_delay": "Order delay",
    "missing_item": "Missing item",
    "food_quality": "Food quality",
    "cancellation": "Cancellation",
    "agent_escalation": "Agent escalation",
}
TICKET_LABEL = {"open": "Open", "resolved_bot": "Resolved", "escalated_to_agent": "With support agent"}
STEPS = [("placed", "Placed"), ("preparing", "Preparing"), ("out_for_delivery", "On the way"), ("delivered", "Delivered")]


def esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def fmt_text(text: str) -> str:
    """Escapes the text, then allows **bold**, bullet lists and line breaks."""
    out = esc(text).replace("$", "&#36;")
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"(?m)^\s*[-*] ", "• ", out)
    return out.replace("\r", "").replace("\n", "<br>")


def now_label() -> str:
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def fmt_dt(value: Any) -> str:
    d = to_datetime(value)
    return d.strftime("%d %b, %I:%M %p").lstrip("0") if d else ""


def human_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} mins"
    hours, rest = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} hr {rest} min" if rest else f"{hours} hr"
    days = hours // 24
    return f"{days} day{'s' if days > 1 else ''}"


def badges(order: Dict[str, Any]) -> str:
    status = order["order_status"]
    _, delayed = order_timing(order)
    out = f'<span class="z-b {STATUS_CLASS.get(status, "bad")}">{esc(STATUS_LABEL.get(status, status)).upper()}</span>'
    if delayed:
        out += '<span class="z-b warn">DELAYED</span>'
    return out


def order_panel_html(o: Dict[str, Any]) -> str:
    status = o["order_status"]
    elapsed, delayed = order_timing(o)

    timeline = ""
    if status != "cancelled":
        cur = [k for k, _ in STEPS].index(status)
        timeline = '<div class="z-steps">' + "".join(
            f'<div class="z-step{" done" if i <= cur else ""}"><div class="c"></div>{label}</div>'
            for i, (_, label) in enumerate(STEPS)
        ) + "</div>"

    banner = ""
    if delayed:
        banner = f'<div class="z-banner">Running late. This order was placed {human_duration(elapsed)} ago.</div>'

    eta = ""
    if status in LIVE_STATUSES and o.get("eta_minutes"):
        eta = f'<div class="z-eta"><span>Estimated arrival</span><b>{int(o["eta_minutes"])} mins</b></div>'

    cancel_note = ""
    if status == "cancelled" and o.get("cancellation_reason"):
        cancel_note = f'<div class="z-banner muted">Reason: {esc(o["cancellation_reason"])}</div>'

    lines = "".join(
        f'<div class="z-line"><span>{it["quantity"]} x {esc(it["item_name"])}</span>'
        f'<span>₹{it["unit_price"] * it["quantity"]:.2f}</span></div>'
        for it in o.get("items", [])
    )
    lines += f'<div class="z-line total"><span>Order total</span><span>₹{o["total_amount"]:.2f}</span></div>'

    partner = ""
    if status == "out_for_delivery" and o.get("delivery_partner_name"):
        call, phone = "", ""
        if o.get("delivery_partner_phone"):
            p = esc(o["delivery_partner_phone"])
            call = f'<a class="z-call" href="tel:{p}">Call</a>'
            phone = f'<div class="ph">{p}</div>'
        partner = (
            f'<div class="z-partner"><div><small>Delivery partner</small><strong>{esc(o["delivery_partner_name"])}</strong>{phone}</div>{call}</div>'
        )

    return (
        '<div class="z-title">Order details</div>'
        f'<div class="z-row"><div><div class="z-rest">{esc(o["restaurant_name"])}</div>'
        f'<div class="z-meta">Order #{o["order_id"]} &nbsp;•&nbsp; {esc(fmt_dt(o["placed_at"]))}</div></div>'
        f'<div>{badges(o)}</div></div>'
        f"{timeline}{banner}{eta}{cancel_note}"
        f'<hr class="z-sep"/><div class="z-title">🛒 Ordered items</div>{lines}{partner}'
    )


def order_placeholder_html() -> str:
    return (
        '<div class="z-title">Order details</div>'
        '<div class="ord-empty"><b>No order selected yet</b>'
        'Pick an order in the chat and its live status, items and delivery partner will show up here.</div>'
    )


# ---------------------------------------------------------
# Quick actions depend on the real order status
# ---------------------------------------------------------
PILL_DEFS = {
    "where":   {"label": "Where is my order?",    "text": "Where is my order right now?",                          "icon": ":material/location_on:"},
    "delay":   {"label": "Order is delayed",      "text": "My order is delayed. Please help.",                      "icon": ":material/schedule:"},
    "call":    {"label": "Call delivery partner", "text": None,                                                     "icon": ":material/call:"},
    "cancel":  {"label": "Cancel order",          "text": "I want to cancel my order and get a refund.",            "icon": ":material/cancel:"},
    "missing": {"label": "Item missing",          "text": "An item is missing from my order.",                      "icon": ":material/shopping_bag:"},
    "quality": {"label": "Food quality issue",    "text": "I have a food quality issue with my order.",             "icon": ":material/thumb_down:"},
    "refund":  {"label": "Refund status",         "text": "What is the status of my refund?",                       "icon": ":material/payments:"},
    "ticket":  {"label": "Ticket status",         "text": "What is the status of my support ticket for this order?", "icon": ":material/confirmation_number:"},
    "human":   {"label": "Talk to an agent",      "text": "I would like to talk to a human agent.",                 "icon": ":material/support_agent:"},
}


def get_pills(order: Dict[str, Any], tickets: List[Dict[str, Any]]) -> List[str]:
    status = order["order_status"]
    _, delayed = order_timing(order)
    has_open_ticket = any(t["ticket_status"] in ("open", "escalated_to_agent") for t in tickets)

    pills: List[str] = []
    if status in LIVE_STATUSES:
        pills.append("where")
        if delayed:
            pills.append("delay")
        if status == "out_for_delivery" and order.get("delivery_partner_phone"):
            pills.append("call")
        if status in CANCELLABLE_STATUSES:  # no cancel once the food is on its way
            pills.append("cancel")
        if has_open_ticket:
            pills.append("ticket")
        pills.append("human")
    elif status == "delivered":
        pills += ["missing", "quality"]
        if has_open_ticket:
            pills.append("ticket")
        pills.append("human")
    else:  # cancelled
        pills.append("refund")
        if has_open_ticket:
            pills.append("ticket")
        pills.append("human")

    if len(pills) > 4 and "ticket" in pills:
        pills.remove("ticket")
    return pills[:4]


def order_intro(order: Dict[str, Any]) -> str:
    status = order["order_status"]
    base = f"Your order #{order['order_id']} from {order['restaurant_name']}"
    _, delayed = order_timing(order)
    if delayed:
        return f"{base} is taking longer than expected, and I'm sorry about that. What would you like to do?"
    if status == "out_for_delivery":
        return f"{base} is on the way. What would you like to do?"
    if status in ("placed", "preparing"):
        return f"{base} is being prepared. What would you like to do?"
    if status == "delivered":
        return f"{base} was delivered. Is something wrong with it?"
    return f"{base} was cancelled. How can I help?"


# =========================================================
# STATE
# =========================================================
defaults = {
    "stage": "login",          # login | chat
    "theme": "light",
    "user_profile": None,
    "login_error": "",
    "order": None,             # order the customer picked (None until they choose one)
    "order_tickets": [],
    "messages": [],            # {role, content, html, local, error, display, time}
    "choices": [],             # quick replies shown under the last bot message
    "choice_gen": 0,
    "pending": None,           # text waiting to be answered by the agent
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)


@st.cache_resource(show_spinner=False)
def get_agent():
    from src.agents.support_agent import SupportAgent
    return SupportAgent()


def add_msg(role: str, content: str = "", *, html_: Optional[str] = None, local: bool = False,
            error: bool = False, display: Optional[str] = None) -> None:
    st.session_state.messages.append({
        "role": role, "content": content, "html": html_, "local": local,
        "error": error, "display": display, "time": now_label(),
    })


def set_choices(choices: List[Dict[str, Any]]) -> None:
    st.session_state.choices = choices
    st.session_state.choice_gen += 1


def toggle_theme() -> None:
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"


def logout() -> None:
    theme = st.session_state.theme
    for key, value in defaults.items():
        st.session_state[key] = value
    st.session_state.theme = theme


# ---------------------------------------------------------
# Choice builders
# ---------------------------------------------------------
def order_label(o: Dict[str, Any], with_date: bool = False) -> str:
    parts = [o["restaurant_name"], f"#{o['order_id']}", STATUS_LABEL.get(o["order_status"], o["order_status"])]
    _, delayed = order_timing(o)
    if delayed:
        parts.append("Delayed")
    if with_date:
        parts.append(fmt_dt(o["placed_at"]))
    return " · ".join(parts)


def order_choice(o: Dict[str, Any], with_date: bool = False) -> Dict[str, Any]:
    return {"kind": "order", "order_id": o["order_id"], "label": order_label(o, with_date), "icon": ":material/receipt_long:"}


MORE_CHOICE = {"kind": "more", "label": "More options", "icon": ":material/more_horiz:"}
MENU_CHOICE = {"kind": "menu", "label": "Back to main menu", "icon": ":material/arrow_back:"}
SWITCH_CHOICE = {"kind": "switch", "label": "Choose another order", "icon": ":material/swap_horiz:"}


def recent_content(offset: int, intro: str):
    uid = st.session_state.user_profile["user_id"]
    rows = get_user_orders_with_items(uid, limit=PAGE_SIZE + 1, offset=offset)
    more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    if not rows:
        text = "I couldn't find any orders on your account yet." if offset == 0 else "That's all your orders."
        return text, [MORE_CHOICE]
    choices = [order_choice(o, with_date=True) for o in rows]
    if more:
        choices.append({"kind": "recent", "offset": offset + PAGE_SIZE, "label": "Show more orders", "icon": ":material/expand_more:"})
    choices.append(MORE_CHOICE)
    return intro, choices


def entry_content():
    """Bot text and options for the 'which order do you need help with?' step."""
    uid = st.session_state.user_profile["user_id"]
    live = get_live_orders(uid)[:3]
    if live:
        text = (
            "I can see you have a live order. Do you need help with it?"
            if len(live) == 1
            else f"I can see you have {len(live)} live orders. Which one do you need help with?"
        )
        choices = [order_choice(o) for o in live]
        choices.append({"kind": "recent", "offset": 0, "label": "Other orders", "icon": ":material/history:"})
        choices.append(MORE_CHOICE)
        return text, choices
    return recent_content(0, "Which order do you need help with? Here are your most recent orders.")


def order_choices() -> List[Dict[str, Any]]:
    order = st.session_state.order
    choices = [
        {"kind": "pill", "key": k, "label": PILL_DEFS[k]["label"], "icon": PILL_DEFS[k]["icon"]}
        for k in get_pills(order, st.session_state.order_tickets)
    ]
    choices.append(SWITCH_CHOICE)
    return choices


# ---------------------------------------------------------
# Conversation flow
# ---------------------------------------------------------
def start_conversation() -> None:
    st.session_state.order = None
    st.session_state.order_tickets = []
    st.session_state.messages = []
    st.session_state.pending = None
    first = st.session_state.user_profile["name"].split()[0]
    add_msg("assistant", f"Hi {first}! 👋 I'm Zomato's support assistant. How can I help you today?", local=True)
    try:
        text, choices = entry_content()
    except Exception:
        traceback.print_exc()
        text, choices = "I'm having trouble loading your orders right now. You can still type your question below.", []
    add_msg("assistant", text, local=True)
    set_choices(choices)


def go_to_menu(label: str, intro: str) -> None:
    add_msg("user", label, local=True)
    st.session_state.order = None
    st.session_state.order_tickets = []
    text, choices = entry_content()
    add_msg("assistant", f"{intro} {text}".strip(), local=True)
    set_choices(choices)


def select_order(order_id: int, label: str) -> None:
    uid = st.session_state.user_profile["user_id"]
    add_msg("user", label, local=True)
    order = get_order_details(order_id)
    if not order or int(order["user_id"]) != int(uid):
        add_msg("assistant", "Sorry, I couldn't open that order. Please pick another one.", local=True, error=True)
        set_choices([MENU_CHOICE])
        return
    st.session_state.order = order
    st.session_state.order_tickets = get_tickets_for_order(order_id, uid)
    add_msg("assistant", order_intro(order), local=True)
    set_choices(order_choices())


def show_tickets(label: str) -> None:
    uid = st.session_state.user_profile["user_id"]
    add_msg("user", label, local=True)
    tickets = get_open_tickets(uid)
    if not tickets:
        add_msg("assistant", "You don't have any open support tickets right now.", local=True)
        set_choices([MENU_CHOICE])
        return
    lines = [
        f"- **#{t['ticket_id']}** · {ISSUE_LABEL.get(t['issue_type'], t['issue_type'])} · "
        f"{TICKET_LABEL.get(t['ticket_status'], t['ticket_status'])} · "
        f"{t.get('restaurant_name') or 'Order'} (#{t['order_id']})"
        for t in tickets
    ]
    add_msg("assistant", "Here are your open tickets:\n" + "\n".join(lines), local=True)
    choices, seen = [], set()
    for t in tickets:
        if t["order_id"] in seen or len(choices) >= 3:
            continue
        seen.add(t["order_id"])
        choices.append({
            "kind": "order", "order_id": t["order_id"], "icon": ":material/receipt_long:",
            "label": f"Get help with {t.get('restaurant_name') or 'order'} · #{t['order_id']}",
        })
    choices.append(MENU_CHOICE)
    set_choices(choices)


def queue_agent(text: str, display: Optional[str] = None) -> None:
    add_msg("user", text, display=display)
    st.session_state.pending = text
    set_choices([])


def handle_choice(choice: Dict[str, Any]) -> None:
    """Runs when a quick reply or sidebar shortcut is tapped (before the page re-renders)."""
    kind = choice["kind"]
    try:
        if kind == "order":
            select_order(choice["order_id"], choice["label"])
        elif kind == "recent":
            add_msg("user", choice["label"], local=True)
            intro = "Here are your recent orders. Pick the one you need help with." if choice["offset"] == 0 else "Here are some earlier orders."
            text, choices = recent_content(choice["offset"], intro)
            add_msg("assistant", text, local=True)
            set_choices(choices)
        elif kind == "more":
            add_msg("user", choice["label"], local=True)
            add_msg("assistant", "Here's what else I can help with.", local=True)
            set_choices([
                {"kind": "tickets", "label": "My support tickets", "icon": ":material/confirmation_number:"},
                {"kind": "recent", "offset": 0, "label": "Recent orders", "icon": ":material/history:"},
                MENU_CHOICE,
            ])
        elif kind == "tickets":
            show_tickets(choice["label"])
        elif kind == "menu":
            go_to_menu(choice["label"], "Sure.")
        elif kind == "switch":
            go_to_menu(choice["label"], "No problem.")
        elif kind == "pill":
            key = choice["key"]
            order = st.session_state.order
            if key == "call":
                add_msg("user", PILL_DEFS["call"]["label"], local=True)
                if order and order.get("delivery_partner_name") and order.get("delivery_partner_phone"):
                    add_msg(
                        "assistant", local=True,
                        html_=(
                            f'You can reach <b>{esc(order["delivery_partner_name"])}</b> here: '
                            f'<a href="tel:{esc(order["delivery_partner_phone"])}">{esc(order["delivery_partner_phone"])}</a>'
                        ),
                    )
                else:
                    add_msg("assistant", "A delivery partner hasn't been assigned to your order yet.", local=True)
                set_choices(order_choices())
            else:
                queue_agent(PILL_DEFS[key]["text"], display=PILL_DEFS[key]["label"])
    except Exception:
        traceback.print_exc()
        add_msg("assistant", "Sorry, something went wrong on our side. Please try again.", local=True, error=True)
        set_choices([MENU_CHOICE])


def build_history(msgs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Only real question / answer pairs go to the agent (not the menu clicks, greetings or errors)."""
    history, i = [], 0
    while i < len(msgs) - 1:
        a, b = msgs[i], msgs[i + 1]
        if a["role"] == "user" and not a["local"] and b["role"] == "assistant" and not b["local"] and not b["error"]:
            history += [{"role": "user", "content": a["content"]}, {"role": "assistant", "content": b["content"]}]
            i += 2
        else:
            i += 1
    return history


def refresh_order() -> None:
    """Re-reads the order and its tickets (the agent may have cancelled it or raised a ticket)."""
    order = st.session_state.order
    if not order:
        return
    uid = st.session_state.user_profile["user_id"]
    try:
        fresh = get_order_details(order["order_id"])
        if fresh:
            st.session_state.order = fresh
        st.session_state.order_tickets = get_tickets_for_order(order["order_id"], uid)
    except Exception:
        traceback.print_exc()


def ask_agent(message: str, history: List[Dict[str, str]]):
    try:
        reply = get_agent().chat(
            user_message=message,
            chat_history=history,
            user_profile=st.session_state.user_profile,
            active_order=st.session_state.order,
        )
        return reply, False
    except Exception:
        traceback.print_exc()
        return "Sorry, I'm having trouble right now. Please try again in a moment.", True


def do_login(raw: str) -> None:
    raw = (raw or "").strip()
    st.session_state.login_error = ""
    if not raw:
        st.session_state.login_error = "Please enter your user ID."
        return
    if not raw.isdigit():
        st.session_state.login_error = "Your user ID should contain digits only."
        return
    try:
        user = get_user_profile(int(raw))
        if not user:
            st.session_state.login_error = "We couldn't find an account with that user ID. Please check and try again."
            return
        st.session_state.user_profile = user
        start_conversation()
        st.session_state.stage = "chat"
    except Exception:
        traceback.print_exc()
        st.session_state.user_profile = None
        st.session_state.login_error = "We're having trouble reaching our servers right now. Please try again in a moment."


# ---------------------------------------------------------
# Rendering
# ---------------------------------------------------------
TYPING_HTML = (
    '<div class="wa"><div class="wa-row bot first"><div class="wa-av"></div>'
    '<div class="wa-bubble first"><div class="wa-typing"><i></i><i></i><i></i></div></div></div></div>'
)


def messages_html(msgs: List[Dict[str, Any]]) -> str:
    """The whole conversation as one block of WhatsApp style bubbles (single line: no blank lines)."""
    parts = ['<div class="wa"><div class="wa-day"><span>Today</span></div>']
    prev = None
    for m in msgs:
        role = "me" if m["role"] == "user" else "bot"
        first = role != prev
        body = m["html"] if m.get("html") else fmt_text(m.get("display") or m["content"])
        tick = '<span class="wa-tick">✓✓</span>' if role == "me" else ""
        stamp = f'<span class="wa-time">{esc(m.get("time", ""))}{tick}</span>'
        cls = ("first " if first else "") + ("err" if m.get("error") else "")
        avatar = ""
        if role == "bot":
            avatar = '<div class="wa-av"></div>' if first else '<div class="wa-av ghost"></div>'
        parts.append(
            f'<div class="wa-row {role}{" first" if first else ""}">{avatar}'
            f'<div class="wa-bubble {cls.strip()}">{body}{stamp}</div></div>'
        )
        prev = role
    parts.append("</div>")
    return "".join(parts)


def render_choices() -> None:
    gen = st.session_state.choice_gen
    with st.container(key="opts"):
        for i, c in enumerate(st.session_state.choices):
            st.button(
                c["label"], key=f"opt_{gen}_{i}", icon=c.get("icon"),
                use_container_width=True, on_click=handle_choice, args=(c,),
            )


FIT_JS = """<script>/*__STAMP__*/
(function () {
  const w = window.parent, doc = w.document;
  const find = () => {
    const el = doc.querySelector('.st-key-msgbox'); if (!el) return null;
    let s = el, n = 0;
    while (s && !s.style.height && n < 5) { s = s.parentElement; n++; }
    return (s && s.style.height) ? s : el;
  };
  const fit = () => {
    const s = find(); if (!s) return;
    const top = s.getBoundingClientRect().top;
    const inp = doc.querySelector('[data-testid="stChatInput"]');
    const reserve = (inp ? inp.getBoundingClientRect().height : 56) + 62;
    const h = Math.max(260, w.innerHeight - top - reserve);
    s.style.height = h + 'px'; s.style.maxHeight = h + 'px'; s.style.overflowY = 'auto';
    const card = doc.querySelector('.st-key-chatcard');
    if (card && w.innerWidth > 900) {
      const ch = card.getBoundingClientRect().height;
      ['.st-key-sidebar', '.st-key-ordercard'].forEach((sel) => {
        const e = doc.querySelector(sel);
        if (e) { e.style.height = ch + 'px'; e.style.minHeight = ch + 'px'; e.style.maxHeight = ch + 'px'; e.style.overflowY = 'auto'; }
      });
    }
  };
  const down = () => { const s = find(); if (s) s.scrollTop = s.scrollHeight; };
  fit(); down();
  setTimeout(() => { fit(); down(); }, 120);
  setTimeout(() => { fit(); down(); }, 450);
  if (w.__zFit) w.removeEventListener('resize', w.__zFit);
  w.__zFit = () => fit();
  w.addEventListener('resize', w.__zFit);
})();
</script>"""


def fit_and_scroll() -> None:
    """Sizes the chat to the window and scrolls to the latest message (new stamp = script runs every time)."""
    components.html(FIT_JS.replace("__STAMP__", str(time.time_ns())), height=0)


def render_nav(user: Optional[Dict[str, Any]]) -> None:
    dark = st.session_state.theme == "dark"
    theme_label = "Light mode" if dark else "Dark mode"
    theme_icon = ":material/light_mode:" if dark else ":material/dark_mode:"
    with st.container(key="nav"):
        if user:
            # same column widths as the page body, so the name lines up with the chat card's right edge
            c1, c2, c3 = st.columns([1.15, 2.95, 1.45], gap="medium", vertical_alignment="center")
            c1.markdown('<div class="z-logo">zomato</div>', unsafe_allow_html=True)
            c2.markdown(
                '<div class="nav-row"><div class="z-nav-mid">Help &amp; Support</div>'
                f'<div class="z-user"><div class="z-avatar">{esc(user["name"][:1].upper())}</div><span>{esc(user["name"])}</span></div></div>',
                unsafe_allow_html=True,
            )
            with c3:
                b1, b2 = st.columns(2, gap="small")
                b1.button(theme_label, icon=theme_icon, key="theme_btn", on_click=toggle_theme, use_container_width=True)
                b2.button("Log out", icon=":material/logout:", key="logout_btn", on_click=logout, use_container_width=True)
        else:
            c1, c2 = st.columns([8, 1.6], vertical_alignment="center")
            c1.markdown('<div class="z-logo">zomato</div>', unsafe_allow_html=True)
            c2.button(theme_label, icon=theme_icon, key="theme_btn", on_click=toggle_theme, use_container_width=True)


def render_sidebar(user: Dict[str, Any]) -> None:
    with st.container(key="sidebar"):
        st.markdown(
            f'<div class="sb-profile"><div class="z-avatar">{esc(user["name"][:1].upper())}</div>'
            f'<div class="sb-lines"><div class="sb-name">{esc(user["name"])}</div>'
            f'<div class="sb-sub">Customer ID: {esc(user["user_id"])}</div>'
            f'<div class="sb-sub">{esc(user.get("phone") or "")}</div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="sb-sq"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-title">Shortcuts</div>', unsafe_allow_html=True)
        with st.container(key="sb_btns"):
            st.button("My orders", icon=":material/receipt_long:", key="sb_orders", use_container_width=True,
                      on_click=handle_choice, args=({"kind": "recent", "offset": 0, "label": "My orders"},))
            st.button("My support tickets", icon=":material/confirmation_number:", key="sb_tickets", use_container_width=True,
                      on_click=handle_choice, args=({"kind": "tickets", "label": "My support tickets"},))
            st.button("Main menu", icon=":material/home:", key="sb_menu", use_container_width=True,
                      on_click=handle_choice, args=({"kind": "menu", "label": "Main menu"},))
        st.markdown(
            '<div class="sb-foot">Support is available 24×7. For urgent delivery issues, pick your order and tap '
            '<b>Talk to an agent</b>.</div>',
            unsafe_allow_html=True,
        )


# =========================================================
# PAGE
# =========================================================
inject_css(st.session_state.stage, st.session_state.theme)

# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------
if st.session_state.stage == "login":
    render_nav(None)
    _, mid, _ = st.columns([1, 1.05, 1])
    with mid:
        with st.container(key="logincard"):
            st.markdown('<div class="z-hero"></div>', unsafe_allow_html=True)
            with st.container(key="loginbody"):
                st.markdown('<div class="z-h1">Help &amp; Support</div>', unsafe_allow_html=True)
                st.markdown('<div class="z-sub">Enter your user ID and we will find your orders.</div>', unsafe_allow_html=True)
                with st.form("login_form", border=False):
                    uid_input = st.text_input("User ID", placeholder="Enter your user ID")
                    submitted = st.form_submit_button("Continue", use_container_width=True)
                if submitted:
                    do_login(uid_input)
                    if st.session_state.stage == "chat":
                        st.rerun()
                if st.session_state.login_error:
                    st.error(st.session_state.login_error)
                st.markdown('<div class="z-login-note">Your user ID is linked to the phone number on your Zomato account.</div>', unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------
# CHAT
# ---------------------------------------------------------
profile = st.session_state.user_profile
render_nav(profile)

order = st.session_state.order
side_area, chat_area, order_area = st.columns([1.15, 2.95, 1.45], gap="medium")

with side_area:
    render_sidebar(profile)

with chat_area:
    with st.container(key="chatcard"):
        with st.container(key="chathead"):
            h1, h2 = st.columns([4, 1.4], vertical_alignment="center")
            status_line = "typing…" if st.session_state.pending else "Online"
            h1.markdown(
                '<div class="z-agent"><div class="z-agent-avatar"></div><div>'
                '<div class="z-agent-name">Zomato Support</div>'
                f'<div class="z-agent-status"><span class="z-dot"></span>{status_line}</div></div></div>',
                unsafe_allow_html=True,
            )
            h2.button("Clear chat", icon=":material/refresh:", key="clear_btn", on_click=start_conversation, use_container_width=True)

        # native scrolling box; the helper script below resizes it to fit the window
        msg_box = st.container(height=520, border=False, key="msgbox")

        typed = st.chat_input("Type your message here...")
        if typed and typed.strip() and not st.session_state.pending:
            queue_agent(typed.strip())

        with msg_box:
            st.markdown(messages_html(st.session_state.messages), unsafe_allow_html=True)

            if st.session_state.pending:
                st.markdown(TYPING_HTML, unsafe_allow_html=True)
                text = st.session_state.pending
                history = build_history(st.session_state.messages[:-1])
                reply, failed = ask_agent(text, history)
                add_msg("assistant", reply, error=failed)
                st.session_state.pending = None
                refresh_order()
                try:
                    if st.session_state.order:
                        set_choices(order_choices())
                    else:
                        set_choices(entry_content()[1])
                except Exception:
                    traceback.print_exc()
                    set_choices([])
                st.rerun()
            elif st.session_state.choices:
                render_choices()

with order_area:
    with st.container(key="ordercard"):
        st.markdown(order_panel_html(order) if order else order_placeholder_html(), unsafe_allow_html=True)
        st.markdown('<div class="ord-img"></div>', unsafe_allow_html=True)

fit_and_scroll()