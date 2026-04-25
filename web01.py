from flask import Flask, Response, render_template_string, request, jsonify
import time
import threading
import os
import google.generativeai as genai

app = Flask(__name__)

# ================== CẤU HÌNH ==================
API_KEY = os.getenv("API_KEY")  # <--- Thay bằng API key Gemini của bạn

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction="""
    Bạn là Chatbot Điện học thông minh, hỗ trợ học sinh tìm hiểu về điện.

    Nhiệm vụ:
    - Giải thích các khái niệm: cường độ dòng điện (I), điện áp (U), công suất (P), điện trở (R)
    - Giải thích ý nghĩa các số liệu đo được từ cảm biến
    - Hướng dẫn đọc và phân tích biểu đồ dòng điện/điện áp
    - Trả lời ngắn gọn, dễ hiểu, phù hợp học sinh THPT

    Phong cách:
    - Thân thiện, dễ hiểu, có thể đưa ví dụ thực tế
    - Không dùng ký tự đặc biệt phức tạp

    Nếu không chắc: "Bạn nên kiểm tra thêm tài liệu vật lý hoặc hỏi giáo viên nhé!"
    """
)

chat_session = model.start_chat(history=[])

# ================== LƯU DỮ LIỆU ==================
latest_data = {"I": 0.0, "U": 0.0, "V": 0.0, "timestamp": ""}
history_data = {"I": [], "U": [], "V": [], "timestamps": []}
MAX_HISTORY = 60  # giữ tối đa 60 điểm
data_lock = threading.Lock()

# ================== HTML ==================
HTML = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ Đo Dòng Điện - ESP32</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        :root {
            --cyan: #00e5ff;
            --green: #00ff9d;
            --pink: #ff2d78;
            --yellow: #ffe600;
            --orange: #ff8c00;
            --bg-dark: #030a1a;
            --bg-panel: rgba(5, 15, 40, 0.92);
            --sidebar-w: 220px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background-color: var(--bg-dark);
            background-image:
                radial-gradient(ellipse at 20% 50%, rgba(0,60,120,0.4) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 20%, rgba(0,80,60,0.25) 0%, transparent 50%),
                radial-gradient(ellipse at 60% 80%, rgba(80,0,80,0.2) 0%, transparent 50%);
            color: #c8e6ff;
            font-family: 'Rajdhani', sans-serif;
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
        }

        /* ===== SIDEBAR ===== */
        #sidebar {
            width: var(--sidebar-w);
            min-height: 100vh;
            background: linear-gradient(180deg, rgba(0,10,30,0.98) 0%, rgba(0,20,50,0.95) 100%);
            border-right: 1px solid rgba(0,229,255,0.2);
            display: flex;
            flex-direction: column;
            position: fixed;
            top: 0; left: 0;
            z-index: 100;
            box-shadow: 4px 0 30px rgba(0,229,255,0.1);
        }

        .sidebar-logo {
            padding: 28px 20px 24px;
            border-bottom: 1px solid rgba(0,229,255,0.15);
            text-align: center;
        }

        .sidebar-logo .logo-icon {
            font-size: 2.5rem;
            display: block;
            margin-bottom: 8px;
            filter: drop-shadow(0 0 12px var(--yellow));
            animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); filter: drop-shadow(0 0 12px var(--yellow)); }
            50% { transform: scale(1.1); filter: drop-shadow(0 0 20px var(--yellow)); }
        }

        .sidebar-logo h2 {
            font-family: 'Orbitron', monospace;
            font-size: 0.72rem;
            font-weight: 700;
            color: var(--cyan);
            letter-spacing: 2px;
            text-transform: uppercase;
            line-height: 1.5;
        }

        .sidebar-logo p {
            font-size: 0.68rem;
            color: rgba(200,230,255,0.45);
            margin-top: 4px;
            letter-spacing: 1px;
        }

        .sidebar-nav { flex: 1; padding: 20px 0; }

        .nav-label {
            font-size: 0.6rem;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: rgba(200,230,255,0.3);
            padding: 0 20px 10px;
            margin-top: 10px;
        }

        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 20px;
            cursor: pointer;
            transition: all 0.25s ease;
            border-left: 3px solid transparent;
            color: rgba(200,230,255,0.6);
            font-size: 0.95rem;
            font-weight: 500;
            letter-spacing: 0.5px;
            text-decoration: none;
        }

        .nav-item:hover {
            background: rgba(0,229,255,0.06);
            color: var(--cyan);
            border-left-color: rgba(0,229,255,0.4);
        }

        .nav-item.active {
            background: rgba(0,229,255,0.1);
            color: var(--cyan);
            border-left-color: var(--cyan);
        }

        .nav-item .nav-icon { font-size: 1.1rem; width: 22px; text-align: center; }

        .sidebar-footer {
            padding: 16px 20px;
            border-top: 1px solid rgba(0,229,255,0.1);
            font-size: 0.65rem;
            color: rgba(200,230,255,0.3);
            text-align: center;
            letter-spacing: 1px;
        }

        /* ===== MAIN ===== */
        #main {
            margin-left: var(--sidebar-w);
            flex: 1;
            padding: 30px;
            min-height: 100vh;
        }

        .page { display: none; }
        .page.active { display: block; }

        /* ===== PAGE HEADER ===== */
        .page-header {
            margin-bottom: 28px;
            padding-bottom: 18px;
            border-bottom: 1px solid rgba(0,229,255,0.15);
        }

        .page-header h1 {
            font-family: 'Orbitron', monospace;
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--cyan);
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 4px;
            text-shadow: 0 0 20px rgba(0,229,255,0.5);
        }

        .page-header p {
            font-size: 0.85rem;
            color: rgba(200,230,255,0.45);
            letter-spacing: 1px;
        }

        /* ===== PANEL ===== */
        .panel {
            background: var(--bg-panel);
            border: 1px solid rgba(0,229,255,0.15);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
            margin-bottom: 22px;
        }

        /* ===== METRIC CARDS ===== */
        .metric-cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 28px;
        }

        .metric-card {
            background: var(--bg-panel);
            border-radius: 18px;
            padding: 28px 24px;
            border: 1px solid rgba(0,229,255,0.15);
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(10px);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .metric-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 16px 40px rgba(0,0,0,0.5);
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
        }

        .metric-card.card-I::before { background: linear-gradient(90deg, var(--cyan), transparent); }
        .metric-card.card-U::before { background: linear-gradient(90deg, var(--yellow), transparent); }
        .metric-card.card-V::before { background: linear-gradient(90deg, var(--green), transparent); }

        .metric-card .glow-bg {
            position: absolute;
            width: 120px; height: 120px;
            border-radius: 50%;
            opacity: 0.08;
            top: -20px; right: -20px;
        }

        .card-I .glow-bg { background: var(--cyan); }
        .card-U .glow-bg { background: var(--yellow); }
        .card-V .glow-bg { background: var(--green); }

        .metric-label {
            font-size: 0.75rem;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 10px;
            font-weight: 600;
        }

        .card-I .metric-label { color: var(--cyan); }
        .card-U .metric-label { color: var(--yellow); }
        .card-V .metric-label { color: var(--green); }

        .metric-name {
            font-size: 0.78rem;
            color: rgba(200,230,255,0.45);
            margin-bottom: 14px;
            letter-spacing: 1px;
        }

        .metric-value {
            font-family: 'Orbitron', monospace;
            font-size: 2.2rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 6px;
        }

        .card-I .metric-value { color: var(--cyan); text-shadow: 0 0 20px rgba(0,229,255,0.6); }
        .card-U .metric-value { color: var(--yellow); text-shadow: 0 0 20px rgba(255,230,0,0.6); }
        .card-V .metric-value { color: var(--green); text-shadow: 0 0 20px rgba(0,255,157,0.6); }

        .metric-unit {
            font-size: 0.78rem;
            color: rgba(200,230,255,0.4);
            letter-spacing: 2px;
        }

        /* ===== STATUS BAR ===== */
        .status-bar {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 14px 20px;
            background: rgba(0,229,255,0.04);
            border: 1px solid rgba(0,229,255,0.12);
            border-radius: 12px;
            margin-bottom: 22px;
        }

        .status-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 8px var(--green);
            animation: blink 1.5s ease-in-out infinite;
        }

        .status-dot.offline { background: #ff4444; box-shadow: 0 0 8px #ff4444; animation: none; }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        .status-text { font-size: 0.82rem; color: rgba(200,230,255,0.6); letter-spacing: 1px; }
        .status-time { font-family: 'Orbitron', monospace; font-size: 0.72rem; color: rgba(200,230,255,0.35); margin-left: auto; }

        /* ===== CHARTS PAGE ===== */
        .chart-wrap {
            background: var(--bg-panel);
            border: 1px solid rgba(0,229,255,0.12);
            border-radius: 16px;
            padding: 22px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }

        .chart-title {
            font-family: 'Orbitron', monospace;
            font-size: 0.78rem;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 16px;
            font-weight: 600;
        }

        .chart-I .chart-title { color: var(--cyan); }
        .chart-U .chart-title { color: var(--yellow); }
        .chart-V .chart-title { color: var(--green); }

        canvas { max-height: 180px !important; }

        /* ===== CHATBOT ===== */
        .chat-layout {
            display: grid;
            grid-template-columns: 1fr 260px;
            gap: 20px;
            height: calc(100vh - 160px);
        }

        .chat-main {
            display: flex;
            flex-direction: column;
            background: var(--bg-panel);
            border: 1px solid rgba(0,229,255,0.15);
            border-radius: 16px;
            overflow: hidden;
            backdrop-filter: blur(12px);
        }

        .chat-header {
            padding: 16px 22px;
            border-bottom: 1px solid rgba(0,229,255,0.12);
            background: rgba(0,10,30,0.6);
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .chat-header .bot-avatar {
            width: 36px; height: 36px;
            border-radius: 50%;
            background: linear-gradient(135deg, rgba(0,229,255,0.2), rgba(0,255,157,0.1));
            border: 1px solid rgba(0,229,255,0.3);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.1rem;
        }

        .chat-header .bot-name {
            font-family: 'Orbitron', monospace;
            font-size: 0.8rem;
            color: var(--cyan);
            font-weight: 700;
            letter-spacing: 1px;
        }

        .chat-header .bot-status {
            font-size: 0.68rem;
            color: var(--green);
            letter-spacing: 1px;
        }

        #chatBox {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        #chatBox::-webkit-scrollbar { width: 4px; }
        #chatBox::-webkit-scrollbar-track { background: transparent; }
        #chatBox::-webkit-scrollbar-thumb { background: rgba(0,229,255,0.2); border-radius: 2px; }

        .msg-row {
            display: flex;
            align-items: flex-end;
            gap: 10px;
        }

        .msg-row.user { flex-direction: row-reverse; }

        .msg-avatar {
            width: 30px; height: 30px;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.85rem;
            flex-shrink: 0;
        }

        .msg-avatar.bot { background: rgba(0,229,255,0.1); border: 1px solid rgba(0,229,255,0.2); }
        .msg-avatar.user-av { background: rgba(255,230,0,0.1); border: 1px solid rgba(255,230,0,0.2); }

        .bubble {
            max-width: 72%;
            padding: 12px 16px;
            border-radius: 14px;
            font-size: 0.88rem;
            line-height: 1.6;
        }

        .bubble.bot-b {
            background: rgba(0,229,255,0.07);
            border: 1px solid rgba(0,229,255,0.15);
            color: rgba(200,230,255,0.9);
            border-bottom-left-radius: 4px;
        }

        .bubble.user-b {
            background: rgba(255,230,0,0.08);
            border: 1px solid rgba(255,230,0,0.15);
            color: rgba(255,240,150,0.9);
            border-bottom-right-radius: 4px;
        }

        .typing-b { background: rgba(0,229,255,0.06); border: 1px solid rgba(0,229,255,0.12); }

        .typing-dots { display: flex; gap: 4px; align-items: center; height: 20px; }
        .typing-dots span {
            width: 6px; height: 6px;
            border-radius: 50%;
            background: var(--cyan);
            animation: typing 1.4s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }

        @keyframes typing {
            0%, 60%, 100% { opacity: 0.2; transform: scale(0.8); }
            30% { opacity: 1; transform: scale(1.1); }
        }

        .chat-input-area {
            padding: 16px 20px;
            border-top: 1px solid rgba(0,229,255,0.1);
            display: flex;
            gap: 10px;
            background: rgba(0,10,30,0.5);
        }

        #userInput {
            flex: 1;
            background: rgba(0,10,30,0.8);
            border: 1px solid rgba(0,229,255,0.2);
            border-radius: 10px;
            padding: 11px 16px;
            color: #c8e6ff;
            font-family: 'Rajdhani', sans-serif;
            font-size: 0.92rem;
            outline: none;
            transition: border-color 0.2s;
        }

        #userInput:focus { border-color: rgba(0,229,255,0.5); }
        #userInput::placeholder { color: rgba(200,230,255,0.3); }

        .send-btn {
            background: linear-gradient(135deg, rgba(0,229,255,0.15), rgba(0,229,255,0.05));
            border: 1px solid rgba(0,229,255,0.3);
            border-radius: 10px;
            padding: 11px 18px;
            color: var(--cyan);
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.2s;
        }

        .send-btn:hover { background: rgba(0,229,255,0.2); border-color: var(--cyan); }

        /* Chat sidebar */
        .chat-sidebar {
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        .quick-panel {
            background: var(--bg-panel);
            border: 1px solid rgba(0,229,255,0.12);
            border-radius: 14px;
            padding: 18px;
            backdrop-filter: blur(10px);
        }

        .quick-panel h4 {
            font-family: 'Orbitron', monospace;
            font-size: 0.7rem;
            color: var(--cyan);
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .quick-btn {
            width: 100%;
            text-align: left;
            background: rgba(0,229,255,0.04);
            border: 1px solid rgba(0,229,255,0.12);
            border-radius: 8px;
            padding: 10px 12px;
            color: rgba(200,230,255,0.7);
            font-size: 0.8rem;
            cursor: pointer;
            margin-bottom: 7px;
            transition: all 0.2s;
            font-family: 'Rajdhani', sans-serif;
            letter-spacing: 0.5px;
        }

        .quick-btn:hover {
            background: rgba(0,229,255,0.1);
            color: var(--cyan);
            border-color: rgba(0,229,255,0.3);
        }

        .context-panel {
            background: var(--bg-panel);
            border: 1px solid rgba(0,255,157,0.15);
            border-radius: 14px;
            padding: 18px;
        }

        .context-panel h4 {
            font-family: 'Orbitron', monospace;
            font-size: 0.7rem;
            color: var(--green);
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .ctx-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 7px 0;
            border-bottom: 1px solid rgba(0,229,255,0.07);
            font-size: 0.78rem;
        }

        .ctx-row:last-child { border-bottom: none; }
        .ctx-label { color: rgba(200,230,255,0.45); }
        .ctx-val { font-family: 'Orbitron', monospace; font-size: 0.72rem; color: var(--cyan); }

        /* Responsive fix */
        @media (max-width: 900px) {
            .metric-cards { grid-template-columns: 1fr; }
            .chat-layout { grid-template-columns: 1fr; height: auto; }
            #main { padding: 16px; }
        }
    </style>
</head>
<body>

<!-- ===== SIDEBAR ===== -->
<nav id="sidebar">
    <div class="sidebar-logo">
        <span class="logo-icon">⚡</span>
        <h2>Đo Dòng Điện<br>ESP32</h2>
        <p>REALTIME MONITOR</p>
    </div>

    <div class="sidebar-nav">
        <div class="nav-label">Menu</div>
        <a class="nav-item active" onclick="switchPage('home', this); return false;" href="#">
            <span class="nav-icon">🏠</span> Trang Chủ
        </a>
        <a class="nav-item" onclick="switchPage('charts', this); return false;" href="#">
            <span class="nav-icon">📈</span> Biểu Đồ
        </a>
        <a class="nav-item" onclick="switchPage('chat', this); return false;" href="#">
            <span class="nav-icon">🤖</span> Chatbot AI
        </a>
    </div>

    <div class="sidebar-footer">
        ESP32 · Flask · Cloudflare
    </div>
</nav>

<!-- ===== MAIN ===== -->
<main id="main">

    <!-- ============================
         TRANG 1: TRANG CHỦ REALTIME
         ============================ -->
    <div class="page active" id="page-home">
        <div class="page-header">
            <h1>⚡ Giám Sát Thời Gian Thực</h1>
            <p>Dữ liệu từ ESP32 · Cập nhật liên tục</p>
        </div>

        <div class="status-bar">
            <div class="status-dot" id="statusDot"></div>
            <span class="status-text" id="statusText">Đang chờ dữ liệu...</span>
            <span class="status-time" id="statusTime">--:--:--</span>
        </div>

        <div class="metric-cards">
            <!-- Cường độ dòng điện I -->
            <div class="metric-card card-I">
                <div class="glow-bg"></div>
                <div class="metric-label">⚡ Dòng điện</div>
                <div class="metric-name">Cường độ dòng điện I</div>
                <div class="metric-value" id="valI">—</div>
                <div class="metric-unit">AMPERE (A)</div>
            </div>

            <!-- Điện áp U -->
            <div class="metric-card card-U">
                <div class="glow-bg"></div>
                <div class="metric-label">🔋 Điện áp</div>
                <div class="metric-name">Hiệu điện thế U</div>
                <div class="metric-value" id="valU">—</div>
                <div class="metric-unit">VOLT (V)</div>
            </div>

            <!-- Giá trị V -->
            <div class="metric-card card-V">
                <div class="glow-bg"></div>
                <div class="metric-label">📡 Đo lường V</div>
                <div class="metric-name">Giá trị V (tính toán)</div>
                <div class="metric-value" id="valV">—</div>
                <div class="metric-unit">m/s</div>
            </div>
        </div>

        <!-- Bảng thông số phụ -->
        <div class="panel">
            <div style="font-family:'Orbitron',monospace; font-size:0.75rem; color:var(--cyan); letter-spacing:2px; text-transform:uppercase; margin-bottom:18px;">
                📊 Thông Số Tính Toán
            </div>
            <div style="display:grid; grid-template-columns: repeat(3,1fr); gap:16px;">
                <div style="background:rgba(0,229,255,0.04); border:1px solid rgba(0,229,255,0.1); border-radius:10px; padding:16px; text-align:center;">
                    <div style="font-size:0.7rem; color:rgba(200,230,255,0.4); letter-spacing:2px; text-transform:uppercase; margin-bottom:8px;">Công suất P = U×I</div>
                    <div style="font-family:'Orbitron',monospace; font-size:1.3rem; color:var(--pink);" id="calcP">—</div>
                    <div style="font-size:0.7rem; color:rgba(200,230,255,0.35); margin-top:4px;">Watt (W)</div>
                </div>
                <div style="background:rgba(0,229,255,0.04); border:1px solid rgba(0,229,255,0.1); border-radius:10px; padding:16px; text-align:center;">
                    <div style="font-size:0.7rem; color:rgba(200,230,255,0.4); letter-spacing:2px; text-transform:uppercase; margin-bottom:8px;">Điện trở R = U/I</div>
                    <div style="font-family:'Orbitron',monospace; font-size:1.3rem; color:var(--orange);" id="calcR">—</div>
                    <div style="font-size:0.7rem; color:rgba(200,230,255,0.35); margin-top:4px;">Ohm (Ω)</div>
                </div>
                <div style="background:rgba(0,229,255,0.04); border:1px solid rgba(0,229,255,0.1); border-radius:10px; padding:16px; text-align:center;">
                    <div style="font-size:0.7rem; color:rgba(200,230,255,0.4); letter-spacing:2px; text-transform:uppercase; margin-bottom:8px;">Số điểm đã nhận</div>
                    <div style="font-family:'Orbitron',monospace; font-size:1.3rem; color:var(--green);" id="calcCount">0</div>
                    <div style="font-size:0.7rem; color:rgba(200,230,255,0.35); margin-top:4px;">Samples</div>
                </div>
            </div>
        </div>
    </div>

    <!-- ============================
         TRANG 2: BIỂU ĐỒ
         ============================ -->
    <div class="page" id="page-charts">
        <div class="page-header">
            <h1>📈 Biểu Đồ Dữ Liệu</h1>
            <p>Lịch sử theo thời gian · Tối đa 60 điểm gần nhất</p>
        </div>

        <div class="chart-wrap chart-I">
            <div class="chart-title">⚡ Cường Độ Dòng Điện I (A)</div>
            <canvas id="chartI"></canvas>
        </div>

        <div class="chart-wrap chart-U">
            <div class="chart-title">🔋 Hiệu Điện Thế U (V)</div>
            <canvas id="chartU"></canvas>
        </div>

        <div class="chart-wrap chart-V">
            <div class="chart-title">📡 Giá Trị V</div>
            <canvas id="chartV"></canvas>
        </div>
    </div>

    <!-- ============================
         TRANG 3: CHATBOT
         ============================ -->
    <div class="page" id="page-chat">
        <div class="page-header">
            <h1>🤖 Chatbot Điện Học</h1>
            <p>Hỏi về điện, dòng điện, điện áp và phân tích số liệu</p>
        </div>

        <div class="chat-layout">
            <div class="chat-main">
                <div class="chat-header">
                    <div class="bot-avatar">🤖</div>
                    <div>
                        <div class="bot-name">AI Điện Học</div>
                        <div class="bot-status">● Online</div>
                    </div>
                </div>

                <div id="chatBox">
                    <div class="msg-row">
                        <div class="msg-avatar bot">🤖</div>
                        <div class="bubble bot-b">
                            Xin chào! Tôi là AI hỗ trợ điện học. Bạn có thể hỏi tôi về cường độ dòng điện, điện áp, công suất, hoặc nhờ tôi phân tích số liệu đang đo được nhé! ⚡
                        </div>
                    </div>
                </div>

                <div class="chat-input-area">
                    <input type="text" id="userInput" placeholder="Hỏi về điện học..." />
                    <button class="send-btn" onclick="sendMessage()">➤</button>
                </div>
            </div>

            <!-- Sidebar chat -->
            <div class="chat-sidebar">
                <div class="quick-panel">
                    <h4>💬 Câu Hỏi Nhanh</h4>
                    <button class="quick-btn" onclick="quickAsk('Cường độ dòng điện là gì?')">⚡ Cường độ dòng điện là gì?</button>
                    <button class="quick-btn" onclick="quickAsk('Điện áp U có ý nghĩa gì?')">🔋 Điện áp U nghĩa là gì?</button>
                    <button class="quick-btn" onclick="quickAsk('Công thức tính công suất điện?')">⚡ Công suất tính thế nào?</button>
                    <button class="quick-btn" onclick="quickAskWithData()">📊 Phân tích số liệu hiện tại</button>
                    <button class="quick-btn" onclick="quickAsk('Định luật Ohm là gì?')">📐 Định luật Ohm</button>
                    <button class="quick-btn" onclick="quickAsk('Tại sao cần đo dòng điện trong mạch?')">❓ Vì sao cần đo dòng điện?</button>
                </div>

                <div class="context-panel">
                    <h4>📡 Giá Trị Hiện Tại</h4>
                    <div class="ctx-row">
                        <span class="ctx-label">I (A)</span>
                        <span class="ctx-val" id="ctxI">—</span>
                    </div>
                    <div class="ctx-row">
                        <span class="ctx-label">U (V)</span>
                        <span class="ctx-val" id="ctxU">—</span>
                    </div>
                    <div class="ctx-row">
                        <span class="ctx-label">V</span>
                        <span class="ctx-val" id="ctxV">—</span>
                    </div>
                    <div class="ctx-row">
                        <span class="ctx-label">P (W)</span>
                        <span class="ctx-val" id="ctxP">—</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

</main>

<script>
// ===== NAVIGATION =====
function switchPage(name, el) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    el.classList.add('active');
    return false;
}

// ===== CHARTS SETUP =====
function makeChart(id, label, color) {
    const ctx = document.getElementById(id).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                backgroundColor: color + '18',
                borderWidth: 2,
                pointRadius: 3,
                pointBackgroundColor: color,
                tension: 0.4,
                fill: true,
            }]
        },
        options: {
            responsive: true,
            animation: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: 'rgba(200,230,255,0.4)', font: { size: 10 }, maxTicksLimit: 10 },
                    grid: { color: 'rgba(255,255,255,0.04)' }
                },
                y: {
                    ticks: { color: 'rgba(200,230,255,0.4)', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.06)' }
                }
            }
        }
    });
}

const chartI = makeChart('chartI', 'I (A)', '#00e5ff');
const chartU = makeChart('chartU', 'U (V)', '#ffe600');
const chartV = makeChart('chartV', 'V', '#00ff9d');

// ===== FETCH DATA =====
let sampleCount = 0;
let lastI = 0, lastU = 0, lastV = 0;

function updateChartData(chart, labels, values) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update('none');
}

async function fetchData() {
    try {
        const res = await fetch('/api/latest');
        const d = await res.json();

        lastI = d.I; lastU = d.U; lastV = d.V;
        sampleCount = d.count || 0;

        // Trang 1 cập nhật
        document.getElementById('valI').textContent = lastI.toFixed(4);
        document.getElementById('valU').textContent = lastU.toFixed(4);
        document.getElementById('valV').textContent = lastV.toExponential(4);

        const P = (lastI * lastU);
        const R = lastI !== 0 ? (lastU / lastI) : 0;

        document.getElementById('calcP').textContent = P.toFixed(4);
        document.getElementById('calcR').textContent = R.toFixed(4);
        document.getElementById('calcCount').textContent = sampleCount;

        // Status
        const dot = document.getElementById('statusDot');
        const txt = document.getElementById('statusText');
        if (d.timestamp) {
            dot.classList.remove('offline');
            txt.textContent = 'ESP32 đang gửi dữ liệu · Kết nối tốt';
            document.getElementById('statusTime').textContent = d.timestamp;
        } else {
            dot.classList.add('offline');
            txt.textContent = 'Chưa nhận được dữ liệu từ ESP32';
        }

        // Chatbot context panel
        document.getElementById('ctxI').textContent = lastI.toFixed(4);
        document.getElementById('ctxU').textContent = lastU.toFixed(4);
        document.getElementById('ctxV').textContent = lastV.toExponential(3);
        document.getElementById('ctxP').textContent = P.toFixed(4);

        // Trang 2 cập nhật biểu đồ
        updateChartData(chartI, d.timestamps, d.histI);
        updateChartData(chartU, d.timestamps, d.histU);
        updateChartData(chartV, d.timestamps, d.histV);

    } catch(e) {
        document.getElementById('statusDot').classList.add('offline');
        document.getElementById('statusText').textContent = 'Lỗi kết nối server';
    }
}

// Cập nhật mỗi 1 giây
fetchData();
setInterval(fetchData, 1000);

// ===== CHATBOT =====
function addMessage(text, isUser) {
    const chatBox = document.getElementById('chatBox');
    const row = document.createElement('div');
    row.className = 'msg-row' + (isUser ? ' user' : '');

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar ' + (isUser ? 'user-av' : 'bot');
    avatar.textContent = isUser ? '👤' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'bubble ' + (isUser ? 'user-b' : 'bot-b');
    bubble.textContent = text;

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showTyping() {
    const chatBox = document.getElementById('chatBox');
    const row = document.createElement('div');
    row.className = 'msg-row';
    row.id = 'typingIndicator';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar bot';
    avatar.textContent = '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'bubble typing-b';
    bubble.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTyping() {
    const el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

async function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, true);
    input.value = '';
    showTyping();

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await res.json();
        removeTyping();
        addMessage(data.response, false);
    } catch(e) {
        removeTyping();
        addMessage("Lỗi kết nối chatbot. Thử lại sau nhé!", false);
    }
}

function quickAsk(text) {
    document.getElementById('userInput').value = text;
    sendMessage();
}

function quickAskWithData() {
    const msg = `Hiện tại cảm biến đo được: I = ${lastI.toFixed(4)} A, U = ${lastU.toFixed(4)} V, V = ${lastV.toExponential(4)}. Bạn hãy phân tích các giá trị này giúp tôi?`;
    document.getElementById('userInput').value = msg;
    sendMessage();
}

document.getElementById('userInput').addEventListener('keypress', e => {
    if (e.key === 'Enter') sendMessage();
});
</script>
</body>
</html>
'''

# ================== ROUTES ==================

@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/data', methods=['POST'])
def receive_data():
    """ESP32 POST dữ liệu lên đây.
    Ví dụ JSON: {"I": 0.123, "U": 3.30, "V": 1.5e-5}
    """
    try:
        d = request.get_json(force=True)
        I = float(d.get('I', 0))
        U = float(d.get('U', 0))
        V = float(d.get('V', 0))
        ts = time.strftime('%H:%M:%S')

        with data_lock:
            latest_data['I'] = I
            latest_data['U'] = U
            latest_data['V'] = V
            latest_data['timestamp'] = ts

            history_data['I'].append(I)
            history_data['U'].append(U)
            history_data['V'].append(V)
            history_data['timestamps'].append(ts)

            # Giữ tối đa MAX_HISTORY điểm
            for key in ['I', 'U', 'V', 'timestamps']:
                if len(history_data[key]) > MAX_HISTORY:
                    history_data[key] = history_data[key][-MAX_HISTORY:]

        print(f"✅ [{ts}] I={I:.6f} U={U:.6f} V={V:.2e}")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"❌ Lỗi nhận data: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 400


@app.route('/api/latest')
def api_latest():
    """Trả về dữ liệu mới nhất + lịch sử cho biểu đồ"""
    with data_lock:
        return jsonify({
            "I": latest_data['I'],
            "U": latest_data['U'],
            "V": latest_data['V'],
            "timestamp": latest_data['timestamp'],
            "histI": history_data['I'][-60:],
            "histU": history_data['U'][-60:],
            "histV": history_data['V'][-60:],
            "timestamps": history_data['timestamps'][-60:],
            "count": len(history_data['I'])
        })


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({"response": "Bạn muốn hỏi gì về điện học?"})

    try:
        response = chat_session.send_message(user_message)
        return jsonify({"response": response.text})
    except Exception as e:
        print(f"Lỗi Gemini: {e}")
        return jsonify({"response": "Xin lỗi, chatbot đang bận. Kiểm tra lại API key nhé!"})


if __name__ == '__main__':
    print("⚡ Server Đo Dòng Điện đang chạy...")
    print("🌐 Truy cập: http://127.0.0.1:5000")
    print("📡 ESP32 POST data đến: http://<your-cloudflare-url>/data")
    print("   JSON format: {\"I\": 0.123, \"U\": 3.30, \"V\": 1.5e-5}")
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
