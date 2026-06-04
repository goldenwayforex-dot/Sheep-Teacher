import streamlit as st
import sqlite3
import random
import hashlib
import json
import time
import re
from datetime import date, datetime, timedelta

# Reportlab é opcional - se faltar, os certificados PDF ficam desabilitados
try:
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# pyspellchecker é opcional - se faltar, corretor funciona só com regras
try:
    from spellchecker import SpellChecker
    SPELL_OK = True
    _SPELL_INSTANCE = None
    def get_spell():
        global _SPELL_INSTANCE
        if _SPELL_INSTANCE is None:
            _SPELL_INSTANCE = SpellChecker(language='en')
        return _SPELL_INSTANCE
except ImportError:
    SPELL_OK = False

# anthropic é opcional - se faltar OU sem API key, esse provedor fica desabilitado
try:
    import anthropic
    ANTHROPIC_LIB_OK = True
except ImportError:
    ANTHROPIC_LIB_OK = False

# google-generativeai é opcional - permite usar o Gemini (free tier generoso)
try:
    import google.generativeai as genai
    GEMINI_LIB_OK = True
except ImportError:
    GEMINI_LIB_OK = False

CHAT_MODEL_GEMINI = "gemini-2.0-flash"           # Gratuito: 1M tokens/dia
CHAT_MODEL_ANTHROPIC = "claude-haiku-4-5-20251001"  # Pago: ~$0.001/msg

def _get_secret_or_env(chave):
    """Busca uma chave em st.secrets (Streamlit Cloud) ou variável de ambiente."""
    try:
        if hasattr(st, "secrets") and chave in st.secrets:
            return st.secrets[chave]
    except Exception:
        pass
    import os
    return os.environ.get(chave)

def get_gemini_model(system_prompt):
    """Retorna um modelo Gemini configurado ou None se não disponível."""
    if not GEMINI_LIB_OK:
        return None
    api_key = _get_secret_or_env("GEMINI_API_KEY") or _get_secret_or_env("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=CHAT_MODEL_GEMINI,
            system_instruction=system_prompt
        )
    except Exception:
        return None

def get_anthropic_client():
    """Retorna cliente Anthropic se configurado, senão None."""
    if not ANTHROPIC_LIB_OK:
        return None
    api_key = _get_secret_or_env("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None

def _msgs_para_gemini(messages):
    """Converte mensagens estilo Anthropic (user/assistant) pra estilo Gemini (user/model)."""
    return [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [{"text": m["content"]}]
        }
        for m in messages
    ]

def chat_com_ia(messages, system_prompt, max_tokens=400):
    """Tenta Gemini (grátis) primeiro, depois Anthropic. Retorna (texto, provedor)."""
    # 1ª tentativa: Gemini (grátis)
    gem = get_gemini_model(system_prompt)
    if gem is not None:
        contents = _msgs_para_gemini(messages)
        response = gem.generate_content(
            contents,
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.8}
        )
        return response.text, "gemini"

    # 2ª tentativa: Anthropic (pago)
    ant = get_anthropic_client()
    if ant is not None:
        response = ant.messages.create(
            model=CHAT_MODEL_ANTHROPIC,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages
        )
        return response.content[0].text, "anthropic"

    raise RuntimeError("Nenhuma API de chat configurada")

def chat_disponivel():
    """True se pelo menos um provedor está configurado."""
    return (get_gemini_model("test") is not None) or (get_anthropic_client() is not None)

SHEEP_SYSTEM_PROMPT = """You are "Sheep" 🐑, a friendly English conversation tutor at Bethany Church English School in Marília, Brazil. Your students are Brazilian Portuguese speakers (mostly beginners and intermediates) practicing conversational English in a faith-friendly environment.

YOUR PERSONALITY:
- Warm, patient, encouraging, like a kind friend who happens to speak English fluently
- Curious about the student's life — ask follow-up questions
- Faith-aligned: comfortable with topics of prayer, Bible, church life
- Brazilian-aware: you understand they're from Brazil, may mention soccer, food, etc.

CONVERSATION RULES:
- KEEP RESPONSES SHORT: usually 1-3 sentences. This is dialogue, not a class.
- ALWAYS RESPOND IN ENGLISH. The student is here to practice English.
- MIRROR THEIR LEVEL: if they write simply, respond simply. If they show advanced English, you can use richer vocabulary.
- GENTLE CORRECTIONS: if the student makes a mistake, DON'T lecture or list errors. Just naturally use the correct form in your reply. Example: student says "I have 30 years", you reply "Oh, you're 30 years old! Same generation as me. What's it like?"
- END WITH A QUESTION: keep the conversation flowing. Every reply should invite them to continue.
- IF THEY WRITE IN PORTUGUESE: gently nudge them. Say something like "Try that in English! I'll help if you get stuck 😊"

TOPICS YOU LOVE:
Family, daily life, food, hobbies, dreams, travel, faith, prayer, favorite Bible verses, music, work, weekend plans.

TOPICS TO AVOID:
Politics, controversial theology, anything sexual, violence. Steer back kindly: "Let's talk about something else! What's been the best part of your week?"

YOU ARE NOT AN AI: never break character. Never say you're a language model, AI, or assistant. You're Sheep, a friendly companion. If asked "are you a robot?" just smile and say "I'm Sheep! 🐑 Let's keep chatting!"

Start of every new conversation: greet the student warmly and ask about their day or something simple about them."""

# =========================================================
# SHEEP TEACHER - Bethany Church English School
# Versão completa: PIN, streak, conquistas, revisão inteligente,
# explicações, painel do professor, modos de exercício variados.
#
# *** SE VOCÊ JÁ TINHA UM banco_ingles.db DA VERSÃO ANTIGA: ***
# Ele será migrado automaticamente. Se algo travar, delete o
# arquivo banco_ingles.db e rode o app de novo.
# =========================================================

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Sheep Teacher - Bethany Church", layout="wide", initial_sidebar_state="expanded")

DB_PATH = 'banco_ingles.db'
PROFESSOR_NOME = "professor"           # nome reservado para o painel admin
PROFESSOR_PIN  = "1234"                # MUDE este PIN antes de usar de verdade
XP_POR_ACERTO  = 10
XP_REVISAO     = 5
# --- Bônus de velocidade (modo cronômetro) ---
SPEED_BONUS = [(3, 5), (6, 3), (10, 1)]  # (segundos máximo, bônus XP)
# --- Duelo ---
DUELO_QUESTOES   = 10   # quantas questões por duelo
DUELO_XP_VITORIA = 30
DUELO_XP_DERROTA = 10
DUELO_XP_EMPATE  = 15
DUELO_MAX_PENDENTES = 5  # máx. de duelos enviados aguardando resposta
DUELO_TEMPO_REFERENCIA_SEG = 15  # tempo "ideal" por questão (referência visual)
DUELO_APOSTA_MIN = 10
DUELO_APOSTA_MAX = 200
# --- Torneio ---
TORNEIO_XP_CAMPEAO        = 100
TORNEIO_XP_FINALISTA      = 50
TORNEIO_XP_SEMIFINALISTA  = 25

# --- CSS ---
st.markdown("""
<style>
:root {
    --primary: #10B981; --primary-light: #34D399; --primary-dark: #047857;
    --accent: #F59E0B; --gold: #FCD34D;
    --bg: #0B1014; --surface: #131A22; --surface-2: #1A2230;
    --border: #1F2937; --border-light: #374151;
    --text: #F1F5F9; --text-dim: #94A3B8; --text-muted: #64748B;
    --danger: #F87171; --info: #60A5FA;
}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@600;700;800&display=swap');

html, body, [class*="css"], .stApp, .main {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}
h1, h2, h3, h4 {
    font-family: 'Sora', 'Inter', sans-serif !important;
    color: var(--text) !important;
    letter-spacing: -0.02em;
}
.premium-card { background: var(--surface); padding: 28px; border-radius: 16px; border: 1px solid var(--border); box-shadow: 0 4px 24px rgba(0,0,0,0.3); transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
.premium-card:hover { border-color: var(--border-light); }
.ranking-box { background: var(--surface); padding: 14px 16px; border-radius: 12px; border-left: 3px solid var(--primary); margin-bottom: 10px; border-top: 1px solid var(--border); border-right: 1px solid var(--border); border-bottom: 1px solid var(--border); transition: all 0.2s ease; }
.ranking-box:hover { background: var(--surface-2); transform: translateX(2px); }
.badge-card { background: var(--surface); padding: 16px 12px; border-radius: 14px; border: 1px solid var(--border); margin-bottom: 10px; text-align: center; transition: all 0.25s ease; }
.badge-card:hover { border-color: var(--primary); transform: translateY(-2px); }
.badge-locked { opacity: 0.3; filter: grayscale(0.8); }
.stat-box { background: var(--surface); padding: 18px 12px; border-radius: 14px; border: 1px solid var(--border); text-align: center; transition: all 0.2s ease; }
.stat-box:hover { border-color: var(--primary-light); }
.stat-num { font-family: 'Sora', sans-serif; font-size: 1.9rem; font-weight: 800; color: var(--primary); line-height: 1.2; }
.stat-label { color: var(--text-dim); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1.2px; margin-top: 4px; font-weight: 600; }
.stButton>button { background-color: var(--surface) !important; color: var(--text) !important; border: 1.5px solid var(--border-light) !important; border-radius: 12px !important; font-weight: 600 !important; font-family: 'Inter', sans-serif !important; height: 48px !important; width: 100% !important; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important; }
.stButton>button:hover { background-color: var(--primary) !important; color: white !important; border-color: var(--primary) !important; transform: translateY(-1px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.3); }
.stButton>button:disabled { opacity: 0.4; cursor: not-allowed; }
.titulo-principal { font-size: 3rem; font-weight: 800; background: linear-gradient(135deg, #F1F5F9 0%, #94A3B8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.1; margin: 8px 0; }
.subtitulo { color: var(--text-dim); font-size: 1.05rem; }
.destaque-lime { color: var(--primary); font-weight: 600; }
.tag-nivel { display: inline-block; padding: 4px 12px; border-radius: 100px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.nivel-1 { background: rgba(16, 185, 129, 0.15); color: #6EE7B7; border: 1px solid rgba(16, 185, 129, 0.3); }
.nivel-2 { background: rgba(245, 158, 11, 0.15); color: #FCD34D; border: 1px solid rgba(245, 158, 11, 0.3); }
.nivel-3 { background: rgba(248, 113, 113, 0.15); color: #FCA5A5; border: 1px solid rgba(248, 113, 113, 0.3); }
.streak-fire { font-size: 1.4rem; font-weight: 700; color: var(--accent); }
.explicacao { background: rgba(16, 185, 129, 0.08); border-left: 3px solid var(--primary); border-radius: 0 10px 10px 0; padding: 14px 18px; margin-top: 14px; color: #D1FAE5; font-size: 0.96rem; line-height: 1.55; }
.audio-btn { background: var(--surface); color: var(--primary-light); border: 1.5px solid var(--primary); border-radius: 10px; padding: 8px 16px; font-weight: 600; cursor: pointer; font-size: 0.92rem; font-family: 'Inter', sans-serif; transition: all 0.2s ease; }
.audio-btn:hover { background: var(--primary); color: white; }
.avatar { display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; color: white; font-weight: 700; font-family: 'Sora', sans-serif; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
@keyframes float-xp { 0% { opacity: 0; transform: translateY(10px) scale(0.8); } 20% { opacity: 1; transform: translateY(-5px) scale(1.1); } 80% { opacity: 1; transform: translateY(-30px) scale(1); } 100% { opacity: 0; transform: translateY(-50px) scale(0.9); } }
.xp-floating { display: inline-block; color: var(--gold); font-weight: 800; font-family: 'Sora', sans-serif; font-size: 1.5rem; animation: float-xp 1.8s cubic-bezier(0.4, 0, 0.2, 1) forwards; }
@keyframes pop { 0% { transform: scale(0); opacity: 0; } 60% { transform: scale(1.15); opacity: 1; } 100% { transform: scale(1); opacity: 1; } }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
[data-testid="stExpander"] { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 14px !important; margin-bottom: 10px !important; transition: all 0.2s ease; }
[data-testid="stExpander"]:hover { border-color: var(--primary) !important; box-shadow: 0 4px 16px rgba(16, 185, 129, 0.1); }
.stTextInput input, .stTextArea textarea { background: var(--surface) !important; color: var(--text) !important; border: 1.5px solid var(--border-light) !important; border-radius: 10px !important; font-family: 'Inter', sans-serif !important; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--primary) !important; }
.stRadio > label { color: var(--text-dim) !important; }
.stProgress > div > div > div > div { background: var(--primary) !important; }
.logo-wrap { display: flex; align-items: center; justify-content: center; gap: 14px; margin-bottom: 8px; }
.logo-wrap svg { width: 64px; height: 64px; }
@media (max-width: 768px) {
    .titulo-principal { font-size: 2.1rem !important; }
    .premium-card { padding: 18px !important; }
    .stat-num { font-size: 1.4rem !important; }
    .logo-wrap svg { width: 48px; height: 48px; }
}
.fade-in { animation: fadeInUp 0.4s ease forwards; }
</style>
""", unsafe_allow_html=True)

# --- IDENTIDADE VISUAL ---
LOGO_SVG = """
<svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <circle cx="40" cy="40" r="38" fill="#10B981"/>
  <circle cx="40" cy="40" r="38" fill="none" stroke="#FCD34D" stroke-width="2" opacity="0.6"/>
  <ellipse cx="40" cy="50" rx="20" ry="14" fill="#F1F5F9"/>
  <circle cx="28" cy="42" r="7" fill="#F1F5F9"/>
  <circle cx="52" cy="42" rx="7" r="7" fill="#F1F5F9"/>
  <circle cx="56" cy="48" r="5" fill="#F1F5F9"/>
  <circle cx="24" cy="48" r="5" fill="#F1F5F9"/>
  <ellipse cx="40" cy="34" rx="9" ry="11" fill="#1F2937"/>
  <ellipse cx="30" cy="29" rx="3" ry="5" fill="#1F2937"/>
  <ellipse cx="50" cy="29" rx="3" ry="5" fill="#1F2937"/>
  <circle cx="36" cy="34" r="1.8" fill="#FCD34D"/>
  <circle cx="44" cy="34" r="1.8" fill="#FCD34D"/>
  <ellipse cx="40" cy="40" rx="2.2" ry="1.5" fill="#F1F5F9"/>
  <rect x="32" y="59" width="3" height="6" rx="1" fill="#1F2937"/>
  <rect x="45" y="59" width="3" height="6" rx="1" fill="#1F2937"/>
</svg>
"""

MODULO_ICONES = {
    "Módulo 1":  "📝", "Módulo 2":  "📝", "Módulo 3":  "📝", "Módulo 4":  "📝",
    "Módulo 5":  "📅", "Módulo 6":  "🔢", "Módulo 7":  "🎨", "Módulo 8":  "⛪",
    "Módulo 9":  "👋", "Módulo 10": "👥", "Módulo 11": "🔑", "Módulo 12": "👨‍👩‍👧",
    "Módulo 13": "🍞", "Módulo 14": "🫀", "Módulo 15": "📅", "Módulo 16": "☁️",
    "Módulo 17": "❓", "Módulo 18": "🏃", "Módulo 19": "🙏", "Módulo 20": "✝️",
    "Módulo 21": "🎵", "Módulo 22": "📍", "Módulo 23": "🗣️", "Módulo 24": "🚫",
    "Módulo 25": "🔜", "Módulo 26": "💪", "Módulo 27": "⏪", "Módulo 28": "⏮️",
    "Módulo 29": "🐾", "Módulo 30": "👕", "Módulo 31": "🏠", "Módulo 32": "💼",
    "Módulo 33": "🏙️", "Módulo 34": "💗", "Módulo 35": "🕊️", "Módulo 36": "📜",
    "Módulo 37": "🔊", "Módulo 38": "🔊",
}

# Módulos de listening puro - força tipo "listen" em TODAS as questões
MODULOS_AUDIO_PURO = {
    "Módulo 37: 🔊 Listening - Palavras do Dia a Dia",
    "Módulo 38: 🔊 Listening - Frases Bíblicas",
}

def icone_modulo(titulo):
    for prefix, icon in MODULO_ICONES.items():
        if titulo.startswith(prefix + ":") or titulo.startswith(prefix + " "):
            return icon
    return "📦"

# --- AVATARES ---
PALETA_AVATAR = [
    "#10B981", "#F59E0B", "#8B5CF6", "#EC4899",
    "#3B82F6", "#EF4444", "#14B8A6", "#F97316",
    "#6366F1", "#84CC16", "#06B6D4", "#A855F7",
]

# --- NÍVEIS ---
NIVEIS = [
    (0,    "🌱 Iniciante"),
    (100,  "📚 Aprendiz"),
    (300,  "✍️ Estudante"),
    (700,  "🎓 Avançado"),
    (1500, "🏆 Mestre"),
    (3000, "👑 Sábio"),
    (6000, "⭐ Lenda"),
]

def info_nivel(xp):
    """Retorna (nivel_idx, nome, xp_atual_no_nivel, xp_proximo_nivel) para um XP."""
    xp = xp or 0
    nivel_idx = 0
    for i, (limite, nome) in enumerate(NIVEIS):
        if xp >= limite:
            nivel_idx = i
    nome_atual = NIVEIS[nivel_idx][1]
    if nivel_idx + 1 < len(NIVEIS):
        proximo = NIVEIS[nivel_idx + 1][0]
        atual_inicio = NIVEIS[nivel_idx][0]
        return (nivel_idx, nome_atual, xp - atual_inicio, proximo - atual_inicio)
    return (nivel_idx, nome_atual, 1, 1)  # nível máximo

def avatar_iniciais(nome):
    partes = (nome or "?").strip().split()
    if len(partes) >= 2 and len(partes[0]) > 0 and len(partes[-1]) > 0:
        return (partes[0][0] + partes[-1][0]).upper()
    return (partes[0][:2] if partes and partes[0] else "?").upper()

def cor_avatar(nome):
    h = hashlib.md5((nome or "?").encode("utf-8")).hexdigest()
    return PALETA_AVATAR[int(h, 16) % len(PALETA_AVATAR)]

def render_avatar(nome, tamanho=38):
    ini = avatar_iniciais(nome)
    cor = cor_avatar(nome)
    fonte = int(tamanho * 0.42)
    return (f"<span class='avatar' style='width:{tamanho}px;height:{tamanho}px;"
            f"background:{cor};font-size:{fonte}px;'>{ini}</span>")

# --- TYPING: NORMALIZAÇÃO DE RESPOSTAS ---
CONTRACOES_EN = {
    "i'm": "i am", "you're": "you are", "he's": "he is", "she's": "she is",
    "it's": "it is", "we're": "we are", "they're": "they are",
    "i'll": "i will", "you'll": "you will", "he'll": "he will", "she'll": "she will",
    "it'll": "it will", "we'll": "we will", "they'll": "they will",
    "i've": "i have", "you've": "you have", "we've": "we have", "they've": "they have",
    "i'd": "i would", "you'd": "you would", "he'd": "he would", "she'd": "she would",
    "we'd": "we would", "they'd": "they would",
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not",
    "won't": "will not", "wouldn't": "would not",
    "couldn't": "could not", "shouldn't": "should not", "mustn't": "must not",
    "can't": "can not", "cannot": "can not",
    "let's": "let us", "that's": "that is", "there's": "there is",
    "what's": "what is", "where's": "where is", "who's": "who is", "how's": "how is",
}

def normalizar_resp(s):
    """Lowercase, tira espaços/pontuação, expande contrações."""
    s = (s or "").strip().lower().rstrip(".!?,;:")
    # Expande contrações - precisa fazer com word boundaries pra não confundir
    for contr, expan in CONTRACOES_EN.items():
        s = s.replace(contr, expan)
    # Normaliza múltiplos espaços
    s = " ".join(s.split())
    return s

def acerto_typing(resp, correta):
    """Compara resposta digitada com a correta, aceitando contrações e alternativas com /."""
    r = normalizar_resp(resp)
    # Se a resposta correta tem "X / Y", aceita qualquer um dos lados
    if "/" in correta:
        partes = [normalizar_resp(p) for p in correta.split("/")]
        return r in partes
    return r == normalizar_resp(correta)

def calcular_bonus_velocidade(segundos):
    """Retorna XP bônus baseado no tempo da resposta."""
    if segundos is None or segundos < 0:
        return 0
    for limite, bonus in SPEED_BONUS:
        if segundos < limite:
            return bonus
    return 0


def conectar():
    return sqlite3.connect(DB_PATH)

def executar(query, params=()):
    con = conectar()
    cur = con.execute(query, params)
    last = cur.lastrowid
    con.commit(); con.close()
    return last

def consultar(query, params=()):
    con = conectar()
    rows = con.execute(query, params).fetchall()
    con.close()
    return rows

def consultar_um(query, params=()):
    con = conectar()
    row = con.execute(query, params).fetchone()
    con.close()
    return row

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()

def botao_audio(texto: str, label: str = "🔊"):
    safe = texto.replace("'", " ").replace('"', " ")
    html = f"""
    <button class="audio-btn" onclick="
        const u = new SpeechSynthesisUtterance('{safe}');
        u.lang='en-US'; u.rate=0.9;
        speechSynthesis.cancel(); speechSynthesis.speak(u);
    ">{label}</button>
    """
    st.components.v1.html(html, height=45)

def exibir_ranking():
    st.markdown("#### 🏆 TOP 5")
    rows = consultar("SELECT id, nome, xp_total, streak FROM alunos WHERE nome != ? ORDER BY xp_total DESC LIMIT 5", (PROFESSOR_NOME,))
    if not rows:
        st.caption("Ainda sem alunos cadastrados.")
    medalhas = ["🥇", "🥈", "🥉", "", ""]
    for i, r in enumerate(rows):
        rid, nome, xp, streak = r
        fire = f" <span style='color:#F59E0B;font-weight:600;'>🔥{streak}</span>" if streak and streak > 0 else ""
        med = medalhas[i] if i < len(medalhas) else ""
        st.markdown(
            f"<div class='ranking-box' style='display:flex;align-items:center;gap:12px;'>"
            f"{render_avatar(nome, 36)}"
            f"<div style='flex:1;'><b>{med} {nome}</b>{fire}<br>"
            f"<span style='color:var(--primary);font-weight:600;'>{xp} XP</span></div>"
            f"</div>", unsafe_allow_html=True)

# --- CONQUISTAS ---
BADGES = {
    "primeira_licao":  ("🌱", "Primeira Lição", "Complete sua primeira lição"),
    "em_chamas":       ("🔥", "Em Chamas", "Streak de 3 dias"),
    "disciplinado":    ("🔥🔥", "Disciplinado", "Streak de 7 dias"),
    "persistente":     ("🔥🔥🔥", "Persistente", "Streak de 30 dias"),
    "vocab_biblico":   ("📖", "Vocabulário Bíblico", "Complete 'Termos da Igreja'"),
    "homem_oracao":    ("🙏", "Homem/Mulher de Oração", "Complete 'Frases de Oração'"),
    "adorador":        ("🎵", "Adorador", "Complete 'Adoração e Louvor'"),
    "biblico":         ("✝️", "Conhecedor da Palavra", "Complete 'Frases Bíblicas Conhecidas'"),
    "estudioso":       ("📚", "Estudioso", "50 lições completas"),
    "centuriao":       ("💯", "Centurião", "100 lições completas"),
    "decolagem":       ("🚀", "Decolagem", "Alcance 100 XP"),
    "avancado":        ("🌟", "Avançado", "Alcance 1000 XP"),
    "mestre":          ("👑", "Mestre", "Alcance 5000 XP"),
    "polyglot":        ("🎓", "Polyglot", "Complete 10 módulos"),
    "perfeccionista":  ("🎯", "Perfeccionista", "Termine uma lição sem errar"),
    # --- Duelos ---
    "primeira_vitoria":("🥊", "Primeira Vitória", "Vença seu primeiro duelo"),
    "tres_seguidas":   ("🔥", "Pegando Fogo", "3 vitórias seguidas em duelos"),
    "cinco_seguidas":  ("⚡", "Imparável", "5 vitórias seguidas em duelos"),
    "dez_vitorias":    ("🎖️", "Veterano", "10 vitórias em duelos"),
    "rei_duelo":       ("👑", "Rei dos Duelos", "50 vitórias em duelos"),
    # --- Torneio ---
    "campeao_torneio": ("🏆", "Campeão", "Vença um torneio"),
}

MODULO_BADGE = {
    "Módulo 8: Termos da Igreja":         "vocab_biblico",
    "Módulo 19: Frases de Oração":        "homem_oracao",
    "Módulo 21: Adoração e Louvor":       "adorador",
    "Módulo 20: Frases Bíblicas Conhecidas": "biblico",
}

def conceder_conquista(uid, badge_id):
    existe = consultar_um("SELECT 1 FROM conquistas WHERE aluno_id = ? AND badge_id = ?", (uid, badge_id))
    if existe:
        return False
    executar("INSERT INTO conquistas (aluno_id, badge_id, obtida_em) VALUES (?, ?, ?)",
             (uid, badge_id, date.today().isoformat()))
    return True

def verificar_conquistas(uid):
    """Verifica e concede conquistas elegíveis. Retorna lista de novas conquistas."""
    novas = []
    aluno = consultar_um("SELECT xp_total, streak, vitorias_duelo, melhor_streak_vitorias_duelo FROM alunos WHERE id = ?", (uid,))
    if not aluno:
        return novas
    xp, streak, vit_duelo, melhor_streak_v = aluno
    vit_duelo = vit_duelo or 0
    melhor_streak_v = melhor_streak_v or 0
    licoes_feitas = consultar_um("SELECT COUNT(*) FROM progresso WHERE aluno_id = ?", (uid,))[0]

    checks = [
        (licoes_feitas >= 1, "primeira_licao"),
        (streak and streak >= 3, "em_chamas"),
        (streak and streak >= 7, "disciplinado"),
        (streak and streak >= 30, "persistente"),
        (licoes_feitas >= 50, "estudioso"),
        (licoes_feitas >= 100, "centuriao"),
        (xp >= 100, "decolagem"),
        (xp >= 1000, "avancado"),
        (xp >= 5000, "mestre"),
        # Duelo
        (vit_duelo >= 1, "primeira_vitoria"),
        (melhor_streak_v >= 3, "tres_seguidas"),
        (melhor_streak_v >= 5, "cinco_seguidas"),
        (vit_duelo >= 10, "dez_vitorias"),
        (vit_duelo >= 50, "rei_duelo"),
    ]
    for ok, badge in checks:
        if ok and conceder_conquista(uid, badge):
            novas.append(badge)

    # Polyglot: 10 módulos completos
    modulos_completos = consultar("""
        SELECT m.id FROM modulos m
        WHERE NOT EXISTS (
            SELECT 1 FROM licoes l
            WHERE l.modulo_id = m.id
            AND l.id NOT IN (SELECT licao_id FROM progresso WHERE aluno_id = ?)
        )
    """, (uid,))
    if len(modulos_completos) >= 10 and conceder_conquista(uid, "polyglot"):
        novas.append("polyglot")

    # Campeão de torneio: já tem algum torneio onde ele venceu?
    venceu_torneio = consultar_um("SELECT 1 FROM torneios WHERE campeao_id = ? AND status = 'finalizado'", (uid,))
    if venceu_torneio and conceder_conquista(uid, "campeao_torneio"):
        novas.append("campeao_torneio")
    return novas

def conceder_badge_modulo(uid, modulo_titulo):
    badge = MODULO_BADGE.get(modulo_titulo)
    if badge and conceder_conquista(uid, badge):
        return badge
    return None

# --- STREAK ---
def atualizar_streak_no_login(uid):
    hoje = date.today().isoformat()
    aluno = consultar_um("SELECT ultimo_acesso, streak, melhor_streak FROM alunos WHERE id = ?", (uid,))
    if not aluno:
        return 0
    ultimo, streak, melhor = aluno
    streak = streak or 0
    melhor = melhor or 0
    if ultimo == hoje:
        return streak
    if ultimo:
        ontem = (date.today() - timedelta(days=1)).isoformat()
        streak = streak + 1 if ultimo == ontem else 1
    else:
        streak = 1
    melhor = max(melhor, streak)
    executar("UPDATE alunos SET ultimo_acesso = ?, streak = ?, melhor_streak = ? WHERE id = ?",
             (hoje, streak, melhor, uid))
    return streak

# --- ERROS / REVISÃO INTELIGENTE ---
def registrar_erro(uid, licao_id):
    existe = consultar_um("SELECT count FROM erros WHERE aluno_id = ? AND licao_id = ?", (uid, licao_id))
    hoje = date.today().isoformat()
    if existe:
        executar("UPDATE erros SET count = count + 1, ultimo_erro = ? WHERE aluno_id = ? AND licao_id = ?",
                 (hoje, uid, licao_id))
    else:
        executar("INSERT INTO erros (aluno_id, licao_id, count, ultimo_erro) VALUES (?,?,?,?)",
                 (uid, licao_id, 1, hoje))

def obter_revisao_inteligente(uid, n=10):
    """Pega N lições priorizando: 1) erros recentes, 2) lições antigas (>3 dias sem ver), 3) aleatórias."""
    erradas = consultar("""
        SELECT l.id, l.pergunta, l.opcao_1, l.opcao_2, l.opcao_3, l.opcao_4, l.resposta_correta, l.explicacao
        FROM erros e
        JOIN licoes l ON l.id = e.licao_id
        WHERE e.aluno_id = ?
        ORDER BY e.count DESC, e.ultimo_erro DESC
        LIMIT ?
    """, (uid, n))
    if len(erradas) >= n:
        return erradas
    falta = n - len(erradas)
    ja_ids = [r[0] for r in erradas]
    placeholders = ",".join("?" * len(ja_ids)) if ja_ids else "0"
    feitas = consultar(f"""
        SELECT l.id, l.pergunta, l.opcao_1, l.opcao_2, l.opcao_3, l.opcao_4, l.resposta_correta, l.explicacao
        FROM progresso p
        JOIN licoes l ON l.id = p.licao_id
        WHERE p.aluno_id = ? AND l.id NOT IN ({placeholders})
        ORDER BY RANDOM()
        LIMIT ?
    """, [uid] + ja_ids + [falta])
    return erradas + feitas

# --- DUELOS ---
def gerar_questoes_duelo(nivel_max=2, n=DUELO_QUESTOES):
    """Sorteia n IDs de lições com nivel <= nivel_max."""
    rows = consultar("""
        SELECT l.id FROM licoes l
        JOIN modulos m ON m.id = l.modulo_id
        WHERE m.nivel <= ?
        ORDER BY RANDOM()
        LIMIT ?
    """, (nivel_max, n))
    return [r[0] for r in rows]

def carregar_questoes(ids):
    """Carrega questões por ID mantendo a ordem da lista."""
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    rows = consultar(f"""
        SELECT id, pergunta, opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta, explicacao
        FROM licoes WHERE id IN ({placeholders})
    """, ids)
    by_id = {r[0]: r for r in rows}
    return [by_id[i] for i in ids if i in by_id]

def duelos_pendentes_para_responder(uid):
    """Duelos onde você foi desafiado e ainda não respondeu."""
    return consultar("""
        SELECT d.id, a.nome, d.score_desafiante, d.criado_em
        FROM duelos d
        JOIN alunos a ON a.id = d.desafiante_id
        WHERE d.desafiado_id = ? AND d.status = 'aguardando_desafiado'
        ORDER BY d.criado_em DESC
    """, (uid,))

def duelos_enviados_aguardando(uid):
    """Duelos que você enviou e o oponente ainda não respondeu."""
    return consultar("""
        SELECT d.id, a.nome, d.score_desafiante, d.criado_em
        FROM duelos d
        JOIN alunos a ON a.id = d.desafiado_id
        WHERE d.desafiante_id = ? AND d.status = 'aguardando_desafiado'
        ORDER BY d.criado_em DESC
    """, (uid,))

def duelos_finalizados(uid, limite=10):
    """Histórico de duelos finalizados do aluno."""
    return consultar("""
        SELECT d.id,
               CASE WHEN d.desafiante_id = ? THEN a2.nome ELSE a1.nome END AS oponente,
               CASE WHEN d.desafiante_id = ? THEN d.score_desafiante ELSE d.score_desafiado END AS meu_score,
               CASE WHEN d.desafiante_id = ? THEN d.score_desafiado ELSE d.score_desafiante END AS score_op,
               d.vencedor_id,
               d.atualizado_em
        FROM duelos d
        JOIN alunos a1 ON a1.id = d.desafiante_id
        JOIN alunos a2 ON a2.id = d.desafiado_id
        WHERE d.status = 'finalizado' AND (d.desafiante_id = ? OR d.desafiado_id = ?)
        ORDER BY d.atualizado_em DESC
        LIMIT ?
    """, (uid, uid, uid, uid, uid, limite))

def criar_duelo(desafiante_id, desafiado_id, questoes_ids, score, xp_apostado=None,
                tempo_desafiante=None, torneio_partida_id=None):
    """
    Cria um duelo no banco. Se xp_apostado for setado, debita o XP do desafiante imediatamente.
    torneio_partida_id liga este duelo a uma partida de torneio (opcional).
    """
    if xp_apostado:
        executar("UPDATE alunos SET xp_total = xp_total - ? WHERE id = ?", (xp_apostado, desafiante_id))
    return executar("""
        INSERT INTO duelos (desafiante_id, desafiado_id, questoes_ids,
                            score_desafiante, status, criado_em,
                            xp_apostado, tempo_desafiante, torneio_partida_id)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (desafiante_id, desafiado_id, json.dumps(questoes_ids),
          score, 'aguardando_desafiado', datetime.now().isoformat(timespec='seconds'),
          xp_apostado, tempo_desafiante, torneio_partida_id))

def atualizar_streak_vitorias(uid, venceu):
    """Atualiza streak de vitórias em duelo. venceu=True incrementa, False/None reseta."""
    aluno = consultar_um("SELECT streak_vitorias_duelo, melhor_streak_vitorias_duelo FROM alunos WHERE id = ?", (uid,))
    if not aluno: return
    atual, melhor = aluno[0] or 0, aluno[1] or 0
    if venceu:
        atual += 1
        melhor = max(melhor, atual)
    else:
        atual = 0
    executar("UPDATE alunos SET streak_vitorias_duelo = ?, melhor_streak_vitorias_duelo = ? WHERE id = ?",
             (atual, melhor, uid))

def finalizar_duelo(duelo_id, score_desafiado, tempo_desafiado=None):
    """Salva o score do desafiado, calcula vencedor (com desempate por tempo se houver aposta/torneio)
    e distribui XP (incluindo aposta se aplicável)."""
    d = consultar_um("""SELECT desafiante_id, desafiado_id, score_desafiante, xp_apostado,
                               tempo_desafiante, torneio_partida_id
                        FROM duelos WHERE id = ?""", (duelo_id,))
    if not d:
        return None
    desafiante_id, desafiado_id, score_des, xp_apostado, tempo_des, torneio_partida_id = d

    # Decidir vencedor
    if score_desafiado > score_des:
        vencedor = desafiado_id
    elif score_des > score_desafiado:
        vencedor = desafiante_id
    else:
        # EMPATE: desempata por tempo se ambos foram cronometrados (torneio sempre cronometra)
        if tempo_des is not None and tempo_desafiado is not None:
            if tempo_desafiado < tempo_des:
                vencedor = desafiado_id  # foi mais rápido
            elif tempo_des < tempo_desafiado:
                vencedor = desafiante_id
            else:
                vencedor = None  # mesmo score E mesmo tempo: empate real
        else:
            vencedor = None

    # Em torneio, NÃO pode ter empate - sorteia se necessário
    if torneio_partida_id and vencedor is None:
        vencedor = random.choice([desafiante_id, desafiado_id])

    executar("""UPDATE duelos SET score_desafiado = ?, vencedor_id = ?, status = ?,
                                  atualizado_em = ?, tempo_desafiado = ?
                WHERE id = ?""",
             (score_desafiado, vencedor, 'finalizado',
              datetime.now().isoformat(timespec='seconds'), tempo_desafiado, duelo_id))

    # Distribuição de XP
    if xp_apostado:
        # Desafiado também precisa apostar (já foi debitado ao aceitar)
        # Vencedor leva 2x. Empate: cada um recebe de volta o seu.
        if vencedor is None:
            executar("UPDATE alunos SET xp_total = xp_total + ?, empates_duelo = empates_duelo + 1 WHERE id = ?",
                     (xp_apostado, desafiante_id))
            executar("UPDATE alunos SET xp_total = xp_total + ?, empates_duelo = empates_duelo + 1 WHERE id = ?",
                     (xp_apostado, desafiado_id))
            atualizar_streak_vitorias(desafiante_id, False)
            atualizar_streak_vitorias(desafiado_id, False)
        else:
            perdedor = desafiante_id if vencedor == desafiado_id else desafiado_id
            executar("UPDATE alunos SET xp_total = xp_total + ?, vitorias_duelo = vitorias_duelo + 1 WHERE id = ?",
                     (2 * xp_apostado, vencedor))
            executar("UPDATE alunos SET derrotas_duelo = derrotas_duelo + 1 WHERE id = ?", (perdedor,))
            atualizar_streak_vitorias(vencedor, True)
            atualizar_streak_vitorias(perdedor, False)
    else:
        # XP padrão
        if vencedor is None:
            executar("UPDATE alunos SET xp_total = xp_total + ?, empates_duelo = empates_duelo + 1 WHERE id = ?",
                     (DUELO_XP_EMPATE, desafiante_id))
            executar("UPDATE alunos SET xp_total = xp_total + ?, empates_duelo = empates_duelo + 1 WHERE id = ?",
                     (DUELO_XP_EMPATE, desafiado_id))
            atualizar_streak_vitorias(desafiante_id, False)
            atualizar_streak_vitorias(desafiado_id, False)
        else:
            perdedor = desafiante_id if vencedor == desafiado_id else desafiado_id
            executar("UPDATE alunos SET xp_total = xp_total + ?, vitorias_duelo = vitorias_duelo + 1 WHERE id = ?",
                     (DUELO_XP_VITORIA, vencedor))
            executar("UPDATE alunos SET xp_total = xp_total + ?, derrotas_duelo = derrotas_duelo + 1 WHERE id = ?",
                     (DUELO_XP_DERROTA, perdedor))
            atualizar_streak_vitorias(vencedor, True)
            atualizar_streak_vitorias(perdedor, False)

    # Se for partida de torneio, avança o vencedor
    if torneio_partida_id and vencedor:
        perdedor = desafiante_id if vencedor == desafiado_id else desafiado_id
        avancar_no_torneio(torneio_partida_id, vencedor, perdedor)

    return vencedor

def cancelar_duelo(duelo_id, uid):
    """Permite cancelar um duelo enviado que ninguém respondeu ainda.
    Devolve o XP apostado se houver."""
    d = consultar_um("SELECT desafiante_id, status, xp_apostado, torneio_partida_id FROM duelos WHERE id = ?", (duelo_id,))
    if not d:
        return False
    if d[0] != uid or d[1] != 'aguardando_desafiado':
        return False
    if d[3] is not None:  # parte de torneio: não pode cancelar
        return False
    # Devolve XP apostado se houver
    if d[2]:
        executar("UPDATE alunos SET xp_total = xp_total + ? WHERE id = ?", (d[2], uid))
    executar("DELETE FROM duelos WHERE id = ?", (duelo_id,))
    return True

def carregar_duelo(duelo_id):
    return consultar_um("""
        SELECT id, desafiante_id, desafiado_id, questoes_ids,
               score_desafiante, score_desafiado, vencedor_id, status, criado_em, atualizado_em,
               xp_apostado, tempo_desafiante, tempo_desafiado, torneio_partida_id
        FROM duelos WHERE id = ?
    """, (duelo_id,))

# --- TORNEIOS ---
def criar_torneio(nome, nivel, participantes_ids):
    """Cria torneio e gera bracket completo. Funciona com 4 ou 8 jogadores."""
    n = len(participantes_ids)
    if n not in (4, 8):
        return None
    torneio_id = executar("""INSERT INTO torneios (nome, nivel, tamanho, status, criado_em)
                             VALUES (?,?,?,?,?)""",
                          (nome, nivel, n, 'em_andamento',
                           datetime.now().isoformat(timespec='seconds')))
    participantes = participantes_ids[:]
    random.shuffle(participantes)
    total_rodadas = 2 if n == 4 else 3

    # Cria todas as partidas. Primeiro a primeira rodada (com jogadores), depois as outras.
    partidas_por_rodada = []
    rodada_1 = []
    for i in range(0, n, 2):
        pid = executar("""INSERT INTO torneio_partidas (torneio_id, rodada, posicao, jogador1_id, jogador2_id)
                          VALUES (?,?,?,?,?)""",
                       (torneio_id, 1, i // 2, participantes[i], participantes[i+1]))
        rodada_1.append(pid)
    partidas_por_rodada.append(rodada_1)

    # Demais rodadas: cria partidas vazias e linka via proxima_partida_id
    rodada_anterior = rodada_1
    for r in range(2, total_rodadas + 1):
        nova = []
        for i in range(0, len(rodada_anterior), 2):
            pid = executar("""INSERT INTO torneio_partidas (torneio_id, rodada, posicao)
                              VALUES (?,?,?)""", (torneio_id, r, i // 2))
            executar("UPDATE torneio_partidas SET proxima_partida_id = ? WHERE id = ? OR id = ?",
                     (pid, rodada_anterior[i], rodada_anterior[i+1]))
            nova.append(pid)
        partidas_por_rodada.append(nova)
        rodada_anterior = nova
    return torneio_id

def avancar_no_torneio(partida_id, vencedor_id, perdedor_id):
    """Marca vencedor da partida, distribui XP do torneio, e move vencedor para próxima partida."""
    executar("UPDATE torneio_partidas SET vencedor_id = ? WHERE id = ?", (vencedor_id, partida_id))
    p = consultar_um("SELECT torneio_id, rodada, proxima_partida_id FROM torneio_partidas WHERE id = ?", (partida_id,))
    torneio_id, rodada, proxima = p
    t = consultar_um("SELECT tamanho FROM torneios WHERE id = ?", (torneio_id,))[0]
    total_rodadas = 2 if t == 4 else 3

    # XP do perdedor segundo a rodada
    if rodada == total_rodadas:  # perdeu a final → vice-campeão
        executar("UPDATE alunos SET xp_total = xp_total + ? WHERE id = ?", (TORNEIO_XP_FINALISTA, perdedor_id))
    elif rodada == total_rodadas - 1:  # perdeu na semifinal
        executar("UPDATE alunos SET xp_total = xp_total + ? WHERE id = ?", (TORNEIO_XP_SEMIFINALISTA, perdedor_id))

    if not proxima:
        # Era a final! Vencedor é campeão.
        executar("""UPDATE torneios SET campeao_id = ?, status = 'finalizado', finalizado_em = ?
                    WHERE id = ?""",
                 (vencedor_id, datetime.now().isoformat(timespec='seconds'), torneio_id))
        executar("UPDATE alunos SET xp_total = xp_total + ? WHERE id = ?", (TORNEIO_XP_CAMPEAO, vencedor_id))
    else:
        # Colocar vencedor na próxima partida (jogador1 ou jogador2)
        prox = consultar_um("SELECT jogador1_id, jogador2_id FROM torneio_partidas WHERE id = ?", (proxima,))
        if prox[0] is None:
            executar("UPDATE torneio_partidas SET jogador1_id = ? WHERE id = ?", (vencedor_id, proxima))
        else:
            executar("UPDATE torneio_partidas SET jogador2_id = ? WHERE id = ?", (vencedor_id, proxima))

def listar_torneios(status=None):
    if status:
        return consultar("SELECT id, nome, nivel, tamanho, status, campeao_id, criado_em FROM torneios WHERE status = ? ORDER BY id DESC", (status,))
    return consultar("SELECT id, nome, nivel, tamanho, status, campeao_id, criado_em FROM torneios ORDER BY id DESC LIMIT 20")

def partidas_pendentes_do_aluno(uid):
    """Retorna partidas de torneio onde o aluno é jogador1 ou jogador2, ainda não jogadas,
    com ambos os jogadores já definidos. Inclui partidas onde o oponente já jogou e
    está aguardando você responder."""
    return consultar("""
        SELECT tp.id, t.nome, tp.torneio_id, tp.rodada,
               tp.jogador1_id, tp.jogador2_id,
               (SELECT nome FROM alunos WHERE id = tp.jogador1_id) AS j1_nome,
               (SELECT nome FROM alunos WHERE id = tp.jogador2_id) AS j2_nome
        FROM torneio_partidas tp
        JOIN torneios t ON t.id = tp.torneio_id
        WHERE t.status = 'em_andamento'
          AND tp.vencedor_id IS NULL
          AND tp.jogador1_id IS NOT NULL
          AND tp.jogador2_id IS NOT NULL
          AND (tp.jogador1_id = ? OR tp.jogador2_id = ?)
          AND (
              tp.duelo_id IS NULL
              OR EXISTS (
                  SELECT 1 FROM duelos d
                  WHERE d.id = tp.duelo_id
                    AND d.status = 'aguardando_desafiado'
                    AND d.desafiante_id != ?
              )
          )
    """, (uid, uid, uid))

def estado_torneio(torneio_id):
    """Retorna toda a estrutura do torneio: torneio + lista de partidas em ordem (rodada, posição)."""
    t = consultar_um("SELECT id, nome, nivel, tamanho, status, campeao_id, criado_em, finalizado_em FROM torneios WHERE id = ?", (torneio_id,))
    if not t: return None, []
    partidas = consultar("""
        SELECT tp.id, tp.rodada, tp.posicao, tp.jogador1_id, tp.jogador2_id, tp.vencedor_id, tp.duelo_id,
               (SELECT nome FROM alunos WHERE id = tp.jogador1_id),
               (SELECT nome FROM alunos WHERE id = tp.jogador2_id),
               (SELECT nome FROM alunos WHERE id = tp.vencedor_id)
        FROM torneio_partidas tp
        WHERE tp.torneio_id = ?
        ORDER BY tp.rodada, tp.posicao
    """, (torneio_id,))
    return t, partidas

# --- DESAFIO DIÁRIO ---
DESAFIO_XP_BONUS = 25

def obter_ou_gerar_desafio_diario(uid):
    """Retorna a lição do desafio diário de hoje pro aluno. Gera se ainda não tiver."""
    hoje = date.today().isoformat()
    existente = consultar_um(
        "SELECT licao_id, completado FROM desafios_diarios WHERE aluno_id = ? AND data = ?",
        (uid, hoje)
    )
    if existente:
        return existente[0], bool(existente[1])
    # Gerar novo: sorteio determinístico por aluno+data
    seed_str = f"{uid}-{hoje}"
    seed_int = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    licoes = consultar("""
        SELECT l.id FROM licoes l
        JOIN modulos m ON m.id = l.modulo_id
        WHERE m.nivel <= 2
        ORDER BY l.id
    """)
    if not licoes:
        return None, False
    lic_id = licoes[seed_int % len(licoes)][0]
    executar(
        "INSERT INTO desafios_diarios (aluno_id, data, licao_id, completado) VALUES (?,?,?,0)",
        (uid, hoje, lic_id)
    )
    return lic_id, False

def marcar_desafio_completado(uid):
    hoje = date.today().isoformat()
    executar(
        "UPDATE desafios_diarios SET completado = 1 WHERE aluno_id = ? AND data = ?",
        (uid, hoje)
    )

# --- CONVERSAÇÃO ---
XP_CONVERSA_BASE = 10
XP_CONVERSA_BONUS_SEM_ERROS = 5
XP_TEMA_COMPLETO_BONUS = 25  # bônus ao concluir um tema inteiro pela primeira vez

def _conversa_id(tema_id, idx):
    """Constrói o ID de armazenamento pra uma pergunta dentro de um tema."""
    return f"{tema_id}_q{idx}"

def salvar_resposta_conversa(uid, conversa_id, resposta, erros_qtd):
    """Registra uma resposta de conversa no banco."""
    executar(
        "INSERT INTO conversas_respondidas (aluno_id, conversa_id, resposta, erros_qtd, respondido_em) VALUES (?,?,?,?,?)",
        (uid, conversa_id, resposta, erros_qtd, date.today().isoformat())
    )

def historico_conversas(uid):
    """Retorna set de conversa_ids respondidos pelo aluno."""
    rows = consultar(
        "SELECT DISTINCT conversa_id FROM conversas_respondidas WHERE aluno_id = ?",
        (uid,)
    )
    return {r[0] for r in rows}

def ultima_resposta_conversa(uid, conversa_id):
    """Retorna (resposta, erros, data) da última resposta nesse conversa_id, ou None."""
    r = consultar_um(
        "SELECT resposta, erros_qtd, respondido_em FROM conversas_respondidas "
        "WHERE aluno_id = ? AND conversa_id = ? ORDER BY id DESC LIMIT 1",
        (uid, conversa_id)
    )
    return r

def progresso_tema(uid, tema):
    """Retorna (respondidas, total) pra um tema."""
    total = len(tema["perguntas"])
    hist = historico_conversas(uid)
    respondidas = sum(1 for i in range(total) if _conversa_id(tema["id"], i) in hist)
    return respondidas, total

def proxima_pergunta_tema(uid, tema):
    """Retorna o índice da próxima pergunta não respondida (ou 0 se todas feitas)."""
    hist = historico_conversas(uid)
    for i in range(len(tema["perguntas"])):
        if _conversa_id(tema["id"], i) not in hist:
            return i
    return 0  # se tudo respondido, volta pra primeira

def tema_completo(uid, tema):
    """True se todas as perguntas do tema já foram respondidas."""
    respondidas, total = progresso_tema(uid, tema)
    return respondidas == total

# =========================================================
# TRILHA DE APRENDIZADO
# (titulo, nivel, [ (fase, pergunta, correta, e1, e2, e3) ])
# Explicações vivem em um dicionário separado para não poluir.
# =========================================================
TRILHA = [
    ("Módulo 1: To Be - Presente", 1, [
        ("Fase 1", "Eu sou um professor", "I am a teacher", "I is a teacher", "I are a teacher", "I be a teacher"),
        ("Fase 2", "Ela é minha irmã", "She is my sister", "She was my sister", "She are my sister", "She be my sister"),
        ("Fase 3", "Nós estamos felizes", "We are happy", "We am happy", "We is happy", "We be happy"),
        ("Fase 4", "Eles estão em casa", "They are at home", "They was at home", "They be at home", "They is at home"),
        ("Fase 5", "Ele é inteligente", "He is smart", "He are smart", "He am smart", "He be smart"),
        ("Fase 6", "É um dia lindo", "It is a beautiful day", "It was a beautiful day", "It be a beautiful day", "It are a beautiful day"),
        ("Fase 7", "Você está atrasado", "You are late", "You is late", "You am late", "You be late"),
        ("Fase 8", "Eu estou com fome", "I am hungry", "I was hungry", "I be hungry", "I are hungry"),
    ]),
    ("Módulo 2: To Be - Negativo", 1, [
        ("Fase 1", "Eu não estou cansado", "I am not tired", "I don't am tired", "I not am tired", "I no am tired"),
        ("Fase 2", "Você não está pronto", "You are not ready", "You don't ready", "You no ready", "You not are ready"),
        ("Fase 3", "Ele não é o gerente", "He is not the manager", "He not is the manager", "He are not the manager", "He don't is the manager"),
        ("Fase 4", "Ela não é minha amiga", "She is not my friend", "She not is my friend", "She are not my friend", "She don't is my friend"),
        ("Fase 5", "Nós não estamos atrasados", "We are not late", "We not are late", "We isn't late", "We don't are late"),
        ("Fase 6", "Eles não estão aqui", "They are not here", "They not are here", "They isn't here", "They am not here"),
        ("Fase 7", "Não está funcionando", "It is not working", "It not is working", "It don't is working", "It are not working"),
        ("Fase 8", "Eu não estou errado", "I am not wrong", "I not am wrong", "I don't am wrong", "I no am wrong"),
    ]),
    ("Módulo 3: To Be - Passado", 1, [
        ("Fase 1", "Eu estava no parque", "I was at the park", "I were at the park", "I am at the park", "I be at the park"),
        ("Fase 2", "Eles eram amigos", "They were friends", "They was friends", "They are friends", "They is friends"),
        ("Fase 3", "Ela estava feliz", "She was happy", "She were happy", "She is happy", "She be happy"),
        ("Fase 4", "Nós estávamos lá", "We were there", "We was there", "We are there", "We be there"),
        ("Fase 5", "Ele era um ótimo jogador", "He was a great player", "He were a great player", "He is a great player", "He be a great player"),
        ("Fase 6", "Foi uma festa legal", "It was a nice party", "It were a nice party", "It is a nice party", "It be a nice party"),
        ("Fase 7", "Você estava certo", "You were right", "You was right", "You are right", "You be right"),
        ("Fase 8", "Eu estava pronto", "I was ready", "I were ready", "I am ready", "I be ready"),
    ]),
    ("Módulo 4: To Be - Futuro", 1, [
        ("Fase 1", "Eu estarei lá", "I will be there", "I would be there", "I was there", "I be there"),
        ("Fase 2", "Ela será médica", "She will be a doctor", "She would be a doctor", "She was a doctor", "She is be a doctor"),
        ("Fase 3", "Nós estaremos ocupados", "We will be busy", "We would be busy", "We are busy", "We was busy"),
        ("Fase 4", "Eles estarão felizes", "They will be happy", "They would be happy", "They were happy", "They was happy"),
        ("Fase 5", "Ele estará em casa", "He will be at home", "He would be at home", "He is at home", "He was at home"),
        ("Fase 6", "Será divertido", "It will be fun", "It would be fun", "It was fun", "It are fun"),
        ("Fase 7", "Você estará pronto", "You will be ready", "You would be ready", "You are ready", "You was ready"),
        ("Fase 8", "Amanhã eu estarei trabalhando", "Tomorrow I will be working", "Tomorrow I would be working", "Tomorrow I was working", "Tomorrow I am working"),
    ]),
    ("Módulo 5: Dias da Semana", 1, [
        ("Fase 1", "Segunda-feira", "Monday", "Tuesday", "Wednesday", "Sunday"),
        ("Fase 2", "Terça-feira", "Tuesday", "Monday", "Thursday", "Wednesday"),
        ("Fase 3", "Quarta-feira", "Wednesday", "Friday", "Sunday", "Tuesday"),
        ("Fase 4", "Quinta-feira", "Thursday", "Saturday", "Monday", "Friday"),
        ("Fase 5", "Sexta-feira", "Friday", "Wednesday", "Tuesday", "Saturday"),
        ("Fase 6", "Sábado", "Saturday", "Sunday", "Thursday", "Friday"),
        ("Fase 7", "Domingo", "Sunday", "Monday", "Friday", "Saturday"),
        ("Fase 8", "Fim de semana", "Weekend", "Weekday", "Day off", "Weeknight"),
    ]),
    ("Módulo 6: Números 1-20", 1, [
        ("Fase 1", "1", "One", "Two", "Three", "Four"),
        ("Fase 2", "2", "Two", "Twelve", "Twenty", "Ten"),
        ("Fase 3", "3", "Three", "Thirteen", "Thirty", "Third"),
        ("Fase 4", "4", "Four", "Fourteen", "Forty", "Fourth"),
        ("Fase 5", "5", "Five", "Fifteen", "Fifty", "First"),
        ("Fase 6", "6", "Six", "Sixteen", "Sixty", "Seventy"),
        ("Fase 7", "7", "Seven", "Seventeen", "Seventy", "Sixteen"),
        ("Fase 8", "8", "Eight", "Eighteen", "Eighty", "Eleven"),
        ("Fase 9", "9", "Nine", "Nineteen", "Ninety", "Ten"),
        ("Fase 10", "10", "Ten", "Twenty", "Twelve", "Two"),
        ("Fase 11", "11", "Eleven", "Twelve", "One", "Seven"),
        ("Fase 12", "12", "Twelve", "Twenty", "Two", "Twentieth"),
        ("Fase 13", "13", "Thirteen", "Thirty", "Three", "Fourteen"),
        ("Fase 14", "14", "Fourteen", "Forty", "Four", "Fifteen"),
        ("Fase 15", "15", "Fifteen", "Fifty", "Five", "Fourteen"),
        ("Fase 16", "16", "Sixteen", "Sixty", "Six", "Seventeen"),
        ("Fase 17", "17", "Seventeen", "Seventy", "Seven", "Sixteen"),
        ("Fase 18", "18", "Eighteen", "Eighty", "Eight", "Nineteen"),
        ("Fase 19", "19", "Nineteen", "Ninety", "Nine", "Eighteen"),
        ("Fase 20", "20", "Twenty", "Twelve", "Two", "Twenty-two"),
    ]),
    ("Módulo 7: Cores", 1, [
        ("Fase 1", "Vermelho", "Red", "Blue", "Green", "Yellow"),
        ("Fase 2", "Azul", "Blue", "Red", "Yellow", "Black"),
        ("Fase 3", "Amarelo", "Yellow", "Green", "White", "Pink"),
        ("Fase 4", "Verde", "Green", "Black", "Purple", "Blue"),
        ("Fase 5", "Branco", "White", "Orange", "Red", "Grey"),
        ("Fase 6", "Preto", "Black", "Blue", "Yellow", "Brown"),
        ("Fase 7", "Roxo", "Purple", "Green", "White", "Pink"),
        ("Fase 8", "Laranja", "Orange", "Red", "Blue", "Yellow"),
        ("Fase 9", "Cinza", "Grey", "Brown", "Gold", "Silver"),
        ("Fase 10", "Rosa", "Pink", "Silver", "Brown", "Red"),
    ]),
    ("Módulo 8: Termos da Igreja", 1, [
        ("Fase 1", "Deus", "God", "Bible", "Church", "Pastor"),
        ("Fase 2", "Bíblia", "Bible", "God", "Pastor", "Hymn"),
        ("Fase 3", "Espírito Santo", "Holy Spirit", "Faith", "Gospel", "Grace"),
        ("Fase 4", "Igreja", "Church", "Prayer", "Bible", "Chapel"),
        ("Fase 5", "Oração", "Prayer", "Pastor", "God", "Praise"),
        ("Fase 6", "Pastor", "Pastor", "Faith", "Church", "Priest"),
        ("Fase 7", "Fé", "Faith", "Gospel", "Prayer", "Hope"),
        ("Fase 8", "Evangelho", "Gospel", "Holy Spirit", "Bible", "Sermon"),
        ("Fase 9", "Graça", "Grace", "Sin", "Mercy", "Faith"),
        ("Fase 10", "Salvação", "Salvation", "Grace", "Faith", "Glory"),
        ("Fase 11", "Pecado", "Sin", "Mercy", "Grace", "Evil"),
        ("Fase 12", "Misericórdia", "Mercy", "Salvation", "Praise", "Grace"),
        ("Fase 13", "Adoração", "Worship", "Sermon", "Bible", "Praise"),
        ("Fase 14", "Sermão", "Sermon", "Worship", "Prayer", "Speech"),
    ]),
    ("Módulo 9: Saudações e Diálogos", 1, [
        ("Fase 1", "Olá, como vai?", "Hello, how are you?", "Hi, what is up?", "Hey, how is it?", "Hello, how do you?"),
        ("Fase 2", "Qual é o seu nome?", "What is your name?", "What is the name?", "Who is your name?", "How is your name?"),
        ("Fase 3", "Meu nome é...", "My name is...", "I name is...", "The name is...", "Me name is..."),
        ("Fase 4", "Prazer em conhecer você", "Nice to meet you", "Nice to know you", "Good to meet", "Pleasure for meet you"),
        ("Fase 5", "Bom dia", "Good morning", "Good day", "Good night", "Good afternoon"),
        ("Fase 6", "Boa noite (despedida)", "Good night", "Good evening", "Good day", "Good morning"),
        ("Fase 7", "De onde você é?", "Where are you from?", "Where are you?", "From where you?", "Where you from?"),
        ("Fase 8", "Eu sou do Brasil", "I am from Brazil", "I from Brazil", "I am Brazil", "Me from Brazil"),
    ]),
    ("Módulo 10: Pronomes Pessoais", 1, [
        ("Fase 1", "Eu", "I", "Me", "My", "You"),
        ("Fase 2", "Você / Tu", "You", "He", "We", "Your"),
        ("Fase 3", "Ele", "He", "She", "It", "His"),
        ("Fase 4", "Ela", "She", "He", "Her", "Hers"),
        ("Fase 5", "Nós", "We", "They", "Us", "Our"),
        ("Fase 6", "Eles / Elas", "They", "We", "Them", "Those"),
        ("Fase 7", "Isso (objeto/animal)", "It", "He", "This", "That"),
        ("Fase 8", "Me / Mim (objeto)", "Me", "I", "My", "Mine"),
    ]),
    ("Módulo 11: Pronomes Possessivos", 2, [
        ("Fase 1", "Meu / Minha", "My", "Me", "Mine", "I"),
        ("Fase 2", "Seu / Sua", "Your", "Yours", "You", "Yourself"),
        ("Fase 3", "Dele", "His", "Him", "He", "Hers"),
        ("Fase 4", "Dela", "Her", "Hers", "She", "His"),
        ("Fase 5", "Nosso / Nossa", "Our", "Ours", "Us", "We"),
        ("Fase 6", "Deles / Delas", "Their", "Theirs", "Them", "They"),
        ("Fase 7", "Esta é a minha Bíblia", "This is my Bible", "This is mine Bible", "This is me Bible", "This is I Bible"),
        ("Fase 8", "Aquele livro é dele", "That book is his", "That book is him", "That book is he", "That book is hers"),
    ]),
    ("Módulo 12: Família", 1, [
        ("Fase 1", "Mãe", "Mother", "Father", "Sister", "Daughter"),
        ("Fase 2", "Pai", "Father", "Mother", "Brother", "Son"),
        ("Fase 3", "Irmão", "Brother", "Sister", "Cousin", "Father"),
        ("Fase 4", "Irmã", "Sister", "Brother", "Mother", "Daughter"),
        ("Fase 5", "Filho", "Son", "Daughter", "Father", "Brother"),
        ("Fase 6", "Filha", "Daughter", "Son", "Mother", "Sister"),
        ("Fase 7", "Avô", "Grandfather", "Grandmother", "Uncle", "Father"),
        ("Fase 8", "Avó", "Grandmother", "Grandfather", "Aunt", "Mother"),
        ("Fase 9", "Tio", "Uncle", "Aunt", "Cousin", "Nephew"),
        ("Fase 10", "Tia", "Aunt", "Uncle", "Cousin", "Niece"),
        ("Fase 11", "Primo / Prima", "Cousin", "Nephew", "Uncle", "Sister"),
        ("Fase 12", "Marido", "Husband", "Wife", "Boyfriend", "Father"),
        ("Fase 13", "Esposa", "Wife", "Husband", "Girlfriend", "Mother"),
        ("Fase 14", "Filhos (plural)", "Children", "Childs", "Kids only", "Babies"),
    ]),
    ("Módulo 13: Comida e Bebida", 1, [
        ("Fase 1", "Pão", "Bread", "Butter", "Cheese", "Cake"),
        ("Fase 2", "Água", "Water", "Juice", "Milk", "Wine"),
        ("Fase 3", "Leite", "Milk", "Water", "Tea", "Coffee"),
        ("Fase 4", "Café", "Coffee", "Tea", "Cocoa", "Juice"),
        ("Fase 5", "Arroz", "Rice", "Beans", "Pasta", "Bread"),
        ("Fase 6", "Feijão", "Beans", "Rice", "Peas", "Lentils"),
        ("Fase 7", "Carne", "Meat", "Chicken", "Fish", "Vegetable"),
        ("Fase 8", "Frango", "Chicken", "Beef", "Pork", "Turkey"),
        ("Fase 9", "Peixe", "Fish", "Meat", "Shrimp", "Chicken"),
        ("Fase 10", "Fruta", "Fruit", "Vegetable", "Bread", "Salad"),
        ("Fase 11", "Queijo", "Cheese", "Butter", "Milk", "Bread"),
        ("Fase 12", "Ovo", "Egg", "Bread", "Cheese", "Bacon"),
        ("Fase 13", "Suco", "Juice", "Water", "Coffee", "Soda"),
        ("Fase 14", "Açúcar", "Sugar", "Salt", "Honey", "Flour"),
    ]),
    ("Módulo 14: Partes do Corpo", 1, [
        ("Fase 1", "Cabeça", "Head", "Hand", "Hair", "Heart"),
        ("Fase 2", "Olhos", "Eyes", "Ears", "Eyebrows", "Mouth"),
        ("Fase 3", "Boca", "Mouth", "Nose", "Tongue", "Lips"),
        ("Fase 4", "Nariz", "Nose", "Ear", "Mouth", "Neck"),
        ("Fase 5", "Mão", "Hand", "Foot", "Arm", "Finger"),
        ("Fase 6", "Pé", "Foot", "Hand", "Leg", "Toe"),
        ("Fase 7", "Braço", "Arm", "Leg", "Hand", "Elbow"),
        ("Fase 8", "Perna", "Leg", "Arm", "Foot", "Knee"),
        ("Fase 9", "Coração", "Heart", "Lung", "Brain", "Hand"),
        ("Fase 10", "Cabelo", "Hair", "Head", "Ear", "Skin"),
        ("Fase 11", "Orelha", "Ear", "Eye", "Nose", "Hair"),
        ("Fase 12", "Dedo (da mão)", "Finger", "Toe", "Hand", "Nail"),
    ]),
    ("Módulo 15: Meses do Ano", 1, [
        ("Fase 1", "Janeiro", "January", "June", "July", "March"),
        ("Fase 2", "Fevereiro", "February", "January", "December", "April"),
        ("Fase 3", "Março", "March", "May", "August", "April"),
        ("Fase 4", "Abril", "April", "August", "March", "May"),
        ("Fase 5", "Maio", "May", "March", "April", "June"),
        ("Fase 6", "Junho", "June", "July", "January", "May"),
        ("Fase 7", "Julho", "July", "June", "January", "August"),
        ("Fase 8", "Agosto", "August", "April", "October", "March"),
        ("Fase 9", "Setembro", "September", "December", "November", "October"),
        ("Fase 10", "Outubro", "October", "August", "November", "December"),
        ("Fase 11", "Novembro", "November", "December", "September", "October"),
        ("Fase 12", "Dezembro", "December", "November", "September", "February"),
    ]),
    ("Módulo 16: Clima e Tempo", 2, [
        ("Fase 1", "Está sol", "It is sunny", "It is sun", "It is shining only", "It has sun"),
        ("Fase 2", "Está chovendo", "It is raining", "It is rain", "It rains now", "It is wet"),
        ("Fase 3", "Está frio", "It is cold", "It is cool", "It is freeze", "It has cold"),
        ("Fase 4", "Está calor", "It is hot", "It is warm only", "It is heat", "It has hot"),
        ("Fase 5", "Está ventando", "It is windy", "It is wind", "It is blow", "It is air"),
        ("Fase 6", "Está nevando", "It is snowing", "It is snow", "It snows now", "It is white"),
        ("Fase 7", "Está nublado", "It is cloudy", "It is cloud", "It is dark", "It is grey only"),
        ("Fase 8", "Tempestade", "Storm", "Rain only", "Wind", "Thunder only"),
        ("Fase 9", "Arco-íris", "Rainbow", "Rain", "Sun", "Sky"),
        ("Fase 10", "Trovão", "Thunder", "Lightning", "Storm", "Rain"),
    ]),
    ("Módulo 17: Question Words", 2, [
        ("Fase 1", "O quê?", "What?", "Who?", "Where?", "Why?"),
        ("Fase 2", "Onde?", "Where?", "When?", "What?", "Which?"),
        ("Fase 3", "Quando?", "When?", "Where?", "Why?", "What?"),
        ("Fase 4", "Quem?", "Who?", "Whose?", "Whom?", "What?"),
        ("Fase 5", "Por quê?", "Why?", "What?", "Because?", "How?"),
        ("Fase 6", "Como?", "How?", "What?", "Why?", "When?"),
        ("Fase 7", "Qual?", "Which?", "What?", "Who?", "How?"),
        ("Fase 8", "Quanto custa?", "How much?", "How many?", "What price?", "How cost?"),
        ("Fase 9", "Quantos? (contáveis)", "How many?", "How much?", "How long?", "What number?"),
        ("Fase 10", "De quem?", "Whose?", "Who?", "Whom?", "Of who?"),
    ]),
    ("Módulo 18: Verbos Comuns (Infinitivo)", 2, [
        ("Fase 1", "Ter", "To have", "To has", "To had", "To get"),
        ("Fase 2", "Ir", "To go", "To goes", "To went", "To come"),
        ("Fase 3", "Fazer", "To do / To make", "To did", "To done", "To make only"),
        ("Fase 4", "Querer", "To want", "To wish only", "To wanted", "To desire only"),
        ("Fase 5", "Precisar", "To need", "To needs", "To necessity", "To want"),
        ("Fase 6", "Falar", "To speak / To talk", "To say only", "To tell only", "To word"),
        ("Fase 7", "Comer", "To eat", "To eats", "To ate", "To food"),
        ("Fase 8", "Beber", "To drink", "To drinks", "To drank", "To liquid"),
        ("Fase 9", "Dormir", "To sleep", "To sleeps", "To slept", "To dream only"),
        ("Fase 10", "Trabalhar", "To work", "To working", "To worked", "To job"),
        ("Fase 11", "Estudar", "To study", "To studies", "To studied", "To school"),
        ("Fase 12", "Aprender", "To learn", "To teach", "To learned", "To knowledge"),
        ("Fase 13", "Ensinar", "To teach", "To learn", "To taught", "To class"),
        ("Fase 14", "Amar", "To love", "To like only", "To loved", "To heart"),
    ]),
    ("Módulo 19: Frases de Oração", 2, [
        ("Fase 1", "Pai Nosso", "Our Father", "Father Our", "My Father", "Father of all"),
        ("Fase 2", "Em nome de Jesus", "In Jesus' name", "On Jesus name", "By the Jesus", "With Jesus name"),
        ("Fase 3", "Amém", "Amen", "Amem", "Ahmen", "Amin"),
        ("Fase 4", "Senhor, ouve a minha oração", "Lord, hear my prayer", "Lord, listen my pray", "Lord, hears my prayer", "God, hear me prayer"),
        ("Fase 5", "Obrigado, Senhor", "Thank you, Lord", "Thanks you, Lord", "Thank for Lord", "Thanks the Lord"),
        ("Fase 6", "Perdoa-me", "Forgive me", "Forgiveness me", "Pardon to me", "Excuse me only"),
        ("Fase 7", "Tenha misericórdia", "Have mercy", "Has mercy", "Have piety", "Be merciful only"),
        ("Fase 8", "Eu creio em Deus", "I believe in God", "I believe on God", "I belief in God", "I am believe God"),
        ("Fase 9", "Abençoe a minha família", "Bless my family", "Blessing my family", "Bless the family of me", "Bless family"),
        ("Fase 10", "Vamos orar", "Let's pray", "Lets we pray", "We go pray", "Pray we"),
    ]),
    ("Módulo 20: Frases Bíblicas Conhecidas", 2, [
        ("Fase 1", "Deus é amor", "God is love", "God is the love", "God love is", "God has love"),
        ("Fase 2", "O Senhor é meu pastor", "The Lord is my shepherd", "The Lord is the shepherd", "The Lord my pastor", "Lord is my shepherd"),
        ("Fase 3", "No princípio", "In the beginning", "On the begin", "At begin", "In beginning"),
        ("Fase 4", "Eu sou o caminho", "I am the way", "I am the road", "I am way", "I am the path only"),
        ("Fase 5", "A verdade vos libertará", "The truth will set you free", "The truth shall free you", "Truth makes you free", "The truth liberate you"),
        ("Fase 6", "Vinde a mim", "Come to me", "Come at me", "Comes to me", "Coming to me"),
        ("Fase 7", "Crede em Deus", "Believe in God", "Belief in God", "Believe on God", "Believing God"),
        ("Fase 8", "Sede santos", "Be holy", "Are holy", "Being holy", "Be sacred"),
        ("Fase 9", "Não temas", "Do not fear", "No fear", "Don't be fear", "Not be afraid"),
        ("Fase 10", "Tudo posso", "I can do all things", "I can all things", "I make all things", "All things I can"),
    ]),
    ("Módulo 21: Adoração e Louvor", 2, [
        ("Fase 1", "Aleluia", "Hallelujah", "Aleluia", "Hallelluya", "Halleluyah"),
        ("Fase 2", "Glória a Deus", "Glory to God", "Glory of God", "Glory for God", "Glory God"),
        ("Fase 3", "Santo", "Holy", "Saint only", "Sacred only", "Bless"),
        ("Fase 4", "Bendito", "Blessed", "Bless", "Blessing", "Praise"),
        ("Fase 5", "Cantar", "To sing", "To song", "To music", "To choir"),
        ("Fase 6", "Louvar", "To praise", "To worship only", "To pray", "To honor only"),
        ("Fase 7", "Adorar", "To worship", "To adore only", "To praise only", "To love"),
        ("Fase 8", "Coral", "Choir", "Coral", "Singers", "Group"),
        ("Fase 9", "Hino", "Hymn", "Song only", "Music", "Chant"),
        ("Fase 10", "Cântico", "Song", "Hymn only", "Music only", "Chant only"),
    ]),
    ("Módulo 22: Preposições de Lugar", 3, [
        ("Fase 1", "Em (dentro)", "In", "On", "At", "Inside only"),
        ("Fase 2", "Sobre / Em cima", "On", "In", "Over only", "Above only"),
        ("Fase 3", "Em (ponto específico)", "At", "In", "On", "To"),
        ("Fase 4", "Debaixo", "Under", "Below only", "Down", "Bottom"),
        ("Fase 5", "Acima de", "Above / Over", "On only", "Up", "Top"),
        ("Fase 6", "Atrás de", "Behind", "Back of", "After", "Behinds"),
        ("Fase 7", "Na frente de", "In front of", "In front", "Front of", "Before only"),
        ("Fase 8", "Próximo a", "Near / Next to", "Near to", "Close in", "By only"),
        ("Fase 9", "Longe de", "Far from", "Far of", "Long from", "Distant of"),
        ("Fase 10", "Entre (dois)", "Between", "Among only", "Middle", "Inter"),
    ]),
    ("Módulo 23: Present Simple - Afirmativo", 2, [
        ("Fase 1", "Eu trabalho todo dia", "I work every day", "I works every day", "I am work every day", "I working every day"),
        ("Fase 2", "Ela canta no coral", "She sings in the choir", "She sing in the choir", "She singing in the choir", "She is sing in the choir"),
        ("Fase 3", "Ele estuda a Bíblia", "He studies the Bible", "He study the Bible", "He studys the Bible", "He is study the Bible"),
        ("Fase 4", "Nós oramos juntos", "We pray together", "We prays together", "We praying together", "We are pray together"),
        ("Fase 5", "Eles vão à igreja", "They go to church", "They goes to church", "They going to church", "They is go to church"),
        ("Fase 6", "Você fala inglês", "You speak English", "You speaks English", "You speaking English", "You is speak English"),
        ("Fase 7", "Ela ensina crianças", "She teaches children", "She teach children", "She teachs children", "She is teach children"),
        ("Fase 8", "Eu leio todo dia", "I read every day", "I reads every day", "I am read every day", "I reading every day"),
        ("Fase 9", "Ele assiste o sermão", "He watches the sermon", "He watch the sermon", "He watchs the sermon", "He is watch the sermon"),
        ("Fase 10", "Nós cantamos louvores", "We sing praises", "We sings praises", "We are sing praises", "We singing praises"),
    ]),
    ("Módulo 24: Present Simple - Negativo", 2, [
        ("Fase 1", "Eu não trabalho aos domingos", "I do not work on Sundays", "I not work on Sundays", "I don't works on Sundays", "I am not work on Sundays"),
        ("Fase 2", "Ela não come carne", "She does not eat meat", "She do not eat meat", "She not eat meat", "She is not eat meat"),
        ("Fase 3", "Ele não fala espanhol", "He does not speak Spanish", "He do not speak Spanish", "He not speaks Spanish", "He is not speak Spanish"),
        ("Fase 4", "Nós não jogamos futebol", "We do not play soccer", "We does not play soccer", "We not play soccer", "We are not play soccer"),
        ("Fase 5", "Eles não vão à praia", "They do not go to the beach", "They does not go to the beach", "They not go to the beach", "They are not go to the beach"),
        ("Fase 6", "Você não bebe café", "You do not drink coffee", "You does not drink coffee", "You not drink coffee", "You is not drink coffee"),
        ("Fase 7", "Ela não dirige", "She does not drive", "She do not drive", "She not drive", "She is not drive"),
        ("Fase 8", "Eu não esqueço de Deus", "I do not forget God", "I does not forget God", "I not forget God", "I am not forget God"),
    ]),
    ("Módulo 25: Going to - Futuro", 2, [
        ("Fase 1", "Eu vou estudar amanhã", "I am going to study tomorrow", "I going to study tomorrow", "I am go to study tomorrow", "I will going to study tomorrow"),
        ("Fase 2", "Ela vai cantar no culto", "She is going to sing at the service", "She going to sing at the service", "She is go sing at the service", "She will going to sing"),
        ("Fase 3", "Nós vamos viajar", "We are going to travel", "We going to travel", "We are go to travel", "We will going to travel"),
        ("Fase 4", "Eles vão orar pela igreja", "They are going to pray for the church", "They going to pray for the church", "They is going to pray", "They are go pray for the church"),
        ("Fase 5", "Vai chover hoje", "It is going to rain today", "It going to rain today", "It is go to rain today", "It will going to rain today"),
        ("Fase 6", "Você vai trabalhar?", "Are you going to work?", "You going to work?", "Are you go to work?", "You are going work?"),
        ("Fase 7", "Ele vai ler a Bíblia", "He is going to read the Bible", "He going to read the Bible", "He is go to read the Bible", "He will going to read"),
        ("Fase 8", "Eu vou orar agora", "I am going to pray now", "I going to pray now", "I am go pray now", "I will going to pray now"),
    ]),
    ("Módulo 26: Modal Verbs (can, must, should)", 2, [
        ("Fase 1", "Eu posso ajudar", "I can help", "I can to help", "I cans help", "I am can help"),
        ("Fase 2", "Ela pode cantar bem", "She can sing well", "She can sings well", "She can to sing well", "She cans sing well"),
        ("Fase 3", "Você deve estudar", "You must study", "You must to study", "You musts study", "You am must study"),
        ("Fase 4", "Nós devemos amar uns aos outros", "We should love one another", "We should loves one another", "We should to love one another", "We are should love"),
        ("Fase 5", "Ele não pode dirigir", "He cannot drive", "He can't to drive", "He no can drive", "He cans not drive"),
        ("Fase 6", "Eles devem orar", "They must pray", "They must to pray", "They musts pray", "They are must pray"),
        ("Fase 7", "Você deveria descansar", "You should rest", "You should to rest", "You shoulds rest", "You are should rest"),
        ("Fase 8", "Eu não devo mentir", "I must not lie", "I not must lie", "I am not must lie", "I do not must lie"),
    ]),
    ("Módulo 27: Verbos no Passado (Regulares)", 2, [
        ("Fase 1", "Eu trabalhei ontem", "I worked yesterday", "I worky yesterday", "I am work yesterday", "I work yesterday"),
        ("Fase 2", "Ela orou pela família", "She prayed for the family", "She pray for the family", "She prayd for the family", "She is pray for the family"),
        ("Fase 3", "Ele estudou a Palavra", "He studied the Word", "He studyed the Word", "He study the Word", "He is study the Word"),
        ("Fase 4", "Nós cozinhamos juntos (passado)", "We cooked together", "We cookd together", "We cook together", "We are cook together"),
        ("Fase 5", "Eles caminharam ao parque", "They walked to the park", "They walkd to the park", "They walk to the park", "They are walk to the park"),
        ("Fase 6", "Você visitou seu avô", "You visited your grandfather", "You visit your grandfather", "You visitd your grandfather", "You are visit your grandfather"),
        ("Fase 7", "Ela perguntou ao pastor", "She asked the pastor", "She ask the pastor", "She askd the pastor", "She is ask the pastor"),
        ("Fase 8", "Eu joguei bola", "I played soccer", "I plays soccer", "I plaied soccer", "I am play soccer"),
        ("Fase 9", "Ele esperou no carro", "He waited in the car", "He wait in the car", "He waitd in the car", "He is wait in the car"),
        ("Fase 10", "Nós ajudamos os pobres", "We helped the poor", "We help the poor", "We helpd the poor", "We are help the poor"),
    ]),
    ("Módulo 28: Verbos no Passado (Irregulares)", 3, [
        ("Fase 1", "Eu fui à igreja", "I went to church", "I goed to church", "I gone to church", "I was go to church"),
        ("Fase 2", "Ele veio cedo", "He came early", "He comed early", "He coming early", "He was come early"),
        ("Fase 3", "Ela viu o pastor", "She saw the pastor", "She seed the pastor", "She seen the pastor", "She was see the pastor"),
        ("Fase 4", "Nós comemos juntos (passado)", "We ate together", "We eated together", "We eaten together", "We was eat together"),
        ("Fase 5", "Eles falaram sobre Deus", "They spoke about God", "They speaked about God", "They spoken about God", "They was speak about God"),
        ("Fase 6", "Eu fiz minha lição", "I did my homework", "I doed my homework", "I done my homework", "I was do my homework"),
        ("Fase 7", "Ela disse a verdade", "She told the truth", "She sayed the truth", "She say the truth", "She was say the truth"),
        ("Fase 8", "Ele teve fé", "He had faith", "He haved faith", "He has faith", "He was have faith"),
        ("Fase 9", "Eu pensei nele", "I thought of him", "I thinked of him", "I thoughted of him", "I was think of him"),
        ("Fase 10", "Você sabia disso?", "Did you know that?", "Do you knew that?", "You knowed that?", "You did knew that?"),
    ]),
    ("Módulo 29: Animais", 1, [
        ("Fase 1", "Cachorro", "Dog", "Cat", "Bird", "Wolf"),
        ("Fase 2", "Gato", "Cat", "Dog", "Mouse", "Lion"),
        ("Fase 3", "Pássaro", "Bird", "Fish", "Bee", "Bat"),
        ("Fase 4", "Peixe", "Fish", "Snake", "Bird", "Frog"),
        ("Fase 5", "Cavalo", "Horse", "Cow", "Sheep", "Goat"),
        ("Fase 6", "Vaca", "Cow", "Horse", "Pig", "Bull"),
        ("Fase 7", "Ovelha", "Sheep", "Goat", "Lamb", "Cow"),
        ("Fase 8", "Cordeiro", "Lamb", "Sheep", "Goat", "Calf"),
        ("Fase 9", "Leão", "Lion", "Tiger", "Bear", "Wolf"),
        ("Fase 10", "Águia", "Eagle", "Hawk", "Falcon", "Owl"),
        ("Fase 11", "Pomba", "Dove", "Pigeon", "Sparrow", "Hawk"),
        ("Fase 12", "Cobra (serpente)", "Snake", "Serpent only", "Lizard", "Worm"),
    ]),
    ("Módulo 30: Roupas", 1, [
        ("Fase 1", "Camisa", "Shirt", "Pants", "Coat", "Hat"),
        ("Fase 2", "Calça", "Pants", "Shorts", "Skirt", "Belt"),
        ("Fase 3", "Vestido", "Dress", "Skirt", "Robe", "Coat"),
        ("Fase 4", "Sapato", "Shoe", "Sock", "Boot", "Sandal"),
        ("Fase 5", "Chapéu", "Hat", "Cap only", "Helmet", "Scarf"),
        ("Fase 6", "Casaco", "Coat", "Shirt", "Sweater only", "Jacket only"),
        ("Fase 7", "Meia", "Sock", "Shoe", "Stocking only", "Glove"),
        ("Fase 8", "Cinto", "Belt", "Tie", "Strap", "Buckle"),
        ("Fase 9", "Saia", "Skirt", "Dress", "Pants", "Robe"),
        ("Fase 10", "Bolsa", "Bag", "Purse only", "Box", "Case"),
    ]),
    ("Módulo 31: Casa e Móveis", 1, [
        ("Fase 1", "Casa", "House", "Home only", "Building", "Cabin"),
        ("Fase 2", "Sala", "Living room", "Kitchen", "Bedroom", "Hall"),
        ("Fase 3", "Cozinha", "Kitchen", "Bathroom", "Pantry", "Diner"),
        ("Fase 4", "Quarto", "Bedroom", "Living room", "Bath", "Closet"),
        ("Fase 5", "Banheiro", "Bathroom", "Kitchen", "Closet", "Sink"),
        ("Fase 6", "Mesa", "Table", "Chair", "Desk only", "Shelf"),
        ("Fase 7", "Cadeira", "Chair", "Sofa", "Stool only", "Bench"),
        ("Fase 8", "Cama", "Bed", "Sofa", "Bench", "Couch"),
        ("Fase 9", "Sofá", "Sofa", "Chair", "Bed", "Recliner only"),
        ("Fase 10", "Porta", "Door", "Window", "Gate only", "Entrance"),
        ("Fase 11", "Janela", "Window", "Door", "Mirror", "Shutter"),
        ("Fase 12", "Espelho", "Mirror", "Window", "Glass", "Picture"),
    ]),
    ("Módulo 32: Profissões", 2, [
        ("Fase 1", "Professor", "Teacher", "Student", "Doctor", "Tutor"),
        ("Fase 2", "Médico", "Doctor", "Teacher", "Nurse", "Surgeon only"),
        ("Fase 3", "Engenheiro", "Engineer", "Architect", "Builder", "Mechanic"),
        ("Fase 4", "Missionário", "Missionary", "Pastor", "Priest", "Volunteer"),
        ("Fase 5", "Padeiro", "Baker", "Cook", "Chef", "Farmer"),
        ("Fase 6", "Cozinheiro", "Cook", "Baker", "Waiter", "Butler"),
        ("Fase 7", "Motorista", "Driver", "Mechanic", "Pilot", "Passenger"),
        ("Fase 8", "Estudante", "Student", "Teacher", "Pupil only", "Reader"),
        ("Fase 9", "Carpinteiro", "Carpenter", "Mason", "Painter", "Plumber"),
        ("Fase 10", "Pescador", "Fisherman", "Sailor", "Hunter", "Farmer"),
        ("Fase 11", "Agricultor", "Farmer", "Fisherman", "Gardener", "Worker"),
        ("Fase 12", "Enfermeiro", "Nurse", "Doctor", "Helper", "Carer"),
    ]),
    ("Módulo 33: Lugares da Cidade", 1, [
        ("Fase 1", "Escola", "School", "Church", "Hospital", "Office"),
        ("Fase 2", "Hospital", "Hospital", "Clinic", "School", "Pharmacy"),
        ("Fase 3", "Mercado", "Supermarket", "Store only", "Mall", "Shop only"),
        ("Fase 4", "Restaurante", "Restaurant", "Café", "Diner only", "Bar"),
        ("Fase 5", "Banco", "Bank", "ATM only", "Office", "Building"),
        ("Fase 6", "Parque", "Park", "Garden", "Field", "Plaza"),
        ("Fase 7", "Praia", "Beach", "Coast only", "Sea", "Shore only"),
        ("Fase 8", "Padaria", "Bakery", "Market", "Café", "Shop"),
        ("Fase 9", "Farmácia", "Pharmacy", "Hospital", "Clinic", "Store"),
        ("Fase 10", "Posto de gasolina", "Gas station", "Parking lot", "Garage", "Stop"),
        ("Fase 11", "Aeroporto", "Airport", "Station", "Port", "Terminal only"),
        ("Fase 12", "Biblioteca", "Library", "Bookstore", "School", "Office"),
    ]),
    ("Módulo 34: Sentimentos e Emoções", 2, [
        ("Fase 1", "Feliz", "Happy", "Sad", "Tired", "Angry"),
        ("Fase 2", "Triste", "Sad", "Happy", "Bored", "Tired"),
        ("Fase 3", "Alegre", "Joyful", "Sad", "Angry", "Calm"),
        ("Fase 4", "Bravo", "Angry", "Happy", "Tired", "Glad"),
        ("Fase 5", "Cansado", "Tired", "Energetic", "Happy", "Awake"),
        ("Fase 6", "Animado", "Excited", "Bored", "Tired", "Sad"),
        ("Fase 7", "Calmo", "Calm", "Nervous", "Excited", "Loud"),
        ("Fase 8", "Nervoso", "Nervous", "Calm", "Sleepy", "Bored"),
        ("Fase 9", "Amor", "Love", "Hate", "Liking only", "Friendship"),
        ("Fase 10", "Paz", "Peace", "War", "Fight", "Trouble"),
        ("Fase 11", "Esperança", "Hope", "Faith", "Despair", "Doubt"),
        ("Fase 12", "Gratidão", "Gratitude", "Anger", "Hope", "Faith"),
    ]),
    ("Módulo 35: Personagens Bíblicos", 1, [
        ("Fase 1", "Jesus", "Jesus", "Joshua", "Joseph", "Judah"),
        ("Fase 2", "Maria", "Mary", "Martha", "Magdalene", "Mara"),
        ("Fase 3", "José", "Joseph", "Jonah", "Josiah", "Joshua"),
        ("Fase 4", "Davi", "David", "Daniel", "Dan", "Eli"),
        ("Fase 5", "Moisés", "Moses", "Joshua", "Aaron", "Noah"),
        ("Fase 6", "Abraão", "Abraham", "Isaac", "Adam", "Aaron"),
        ("Fase 7", "Noé", "Noah", "Job", "Jonah", "Eli"),
        ("Fase 8", "Adão", "Adam", "Abraham", "Noah", "Aaron"),
        ("Fase 9", "Eva", "Eve", "Esther", "Ruth", "Sarah"),
        ("Fase 10", "Paulo", "Paul", "Peter", "Saul only", "Philip"),
        ("Fase 11", "Pedro", "Peter", "Paul", "Philip", "John"),
        ("Fase 12", "João (apóstolo)", "John", "Joshua", "Jonah", "James"),
        ("Fase 13", "Sara", "Sarah", "Ruth", "Esther", "Mary"),
        ("Fase 14", "Rute", "Ruth", "Sarah", "Naomi", "Esther"),
        ("Fase 15", "Daniel", "Daniel", "David", "Dan only", "Joshua"),
    ]),
    ("Módulo 36: Livros da Bíblia", 2, [
        ("Fase 1", "Gênesis", "Genesis", "Exodus", "Joshua", "Judges"),
        ("Fase 2", "Êxodo", "Exodus", "Genesis", "Leviticus", "Deuteronomy"),
        ("Fase 3", "Levítico", "Leviticus", "Numbers", "Exodus", "Deuteronomy"),
        ("Fase 4", "Salmos", "Psalms", "Proverbs", "Job", "Songs"),
        ("Fase 5", "Provérbios", "Proverbs", "Psalms", "Ecclesiastes", "Songs"),
        ("Fase 6", "Eclesiastes", "Ecclesiastes", "Proverbs", "Psalms", "Ezekiel"),
        ("Fase 7", "Isaías", "Isaiah", "Jeremiah", "Ezekiel", "Daniel"),
        ("Fase 8", "Mateus", "Matthew", "Mark", "Luke", "John"),
        ("Fase 9", "Marcos", "Mark", "Matthew", "Luke", "John"),
        ("Fase 10", "Lucas", "Luke", "Matthew", "Mark", "John"),
        ("Fase 11", "João (evangelho)", "John", "Luke", "Mark", "Matthew"),
        ("Fase 12", "Atos dos Apóstolos", "Acts", "Romans", "Hebrews", "James"),
        ("Fase 13", "Romanos", "Romans", "Hebrews", "Galatians", "Ephesians"),
        ("Fase 14", "Apocalipse", "Revelation", "Revelations", "Apocalypse", "Acts"),
    ]),
    ("Módulo 37: 🔊 Listening - Palavras do Dia a Dia", 2, [
        ("Fase 1", "Ouça e escolha", "Welcome", "Goodbye", "Hello", "Sorry"),
        ("Fase 2", "Ouça e escolha", "Thank you", "Please", "Excuse me", "Sorry"),
        ("Fase 3", "Ouça e escolha", "Sorry", "Please", "Excuse", "Pardon"),
        ("Fase 4", "Ouça e escolha", "Yes", "No", "Maybe", "Sure"),
        ("Fase 5", "Ouça e escolha", "Today", "Tomorrow", "Yesterday", "Tonight"),
        ("Fase 6", "Ouça e escolha", "Morning", "Evening", "Night", "Afternoon"),
        ("Fase 7", "Ouça e escolha", "Right", "Left", "Center", "Wrong"),
        ("Fase 8", "Ouça e escolha", "Open", "Close", "Lock", "Knock"),
        ("Fase 9", "Ouça e escolha", "Now", "Then", "Soon", "Never"),
        ("Fase 10", "Ouça e escolha", "Always", "Never", "Sometimes", "Often"),
        ("Fase 11", "Ouça e escolha", "Help", "Hold", "Hope", "Hide"),
        ("Fase 12", "Ouça e escolha", "Bread", "Bread bag", "Brand", "Breed"),
    ]),
    ("Módulo 38: 🔊 Listening - Frases Bíblicas", 2, [
        ("Fase 1", "Ouça e escolha", "God is love", "God is good", "God is great", "God is light"),
        ("Fase 2", "Ouça e escolha", "Praise the Lord", "Praise to Lord", "Praise our Lord", "Praise the King"),
        ("Fase 3", "Ouça e escolha", "Jesus loves you", "Jesus saves you", "Jesus calls you", "Jesus knows you"),
        ("Fase 4", "Ouça e escolha", "Glory to God", "Glory for God", "Glory of God", "Glory and God"),
        ("Fase 5", "Ouça e escolha", "Holy Spirit", "Holy Father", "Holy God", "Holy One"),
        ("Fase 6", "Ouça e escolha", "Amen", "Awoman", "Yeman", "Aimin"),
        ("Fase 7", "Ouça e escolha", "Hallelujah", "Hello there", "Holiday", "Hollywood"),
        ("Fase 8", "Ouça e escolha", "Have faith", "Have fate", "Have it", "Have feet"),
        ("Fase 9", "Ouça e escolha", "Be blessed", "Be best", "Be brave", "Be back"),
        ("Fase 10", "Ouça e escolha", "Pray with me", "Pay with me", "Play with me", "Stay with me"),
    ]),
]

# Explicações pedagógicas - só onde realmente ajuda (gramática)
# =========================================================
# MÓDULO DE CONVERSAÇÃO (temas com trilha de perguntas)
# =========================================================
# Cada tema tem várias perguntas que fluem em sequência, como a trilha de aulas.
# O conversa_id usado pra armazenar é "{tema_id}_q{indice}".
CONVERSAS_TEMAS = [
    {
        "id": "apresentacao",
        "icone": "👋",
        "tema": "Apresentação",
        "descricao": "Conheça-se em inglês — o básico de uma primeira conversa.",
        "perguntas": [
            {"pergunta_pt": "Como você se chama?",
             "pergunta_en": "What is your name?",
             "dica": "Comece com 'My name is...' ou 'I am...'"},
            {"pergunta_pt": "Quantos anos você tem?",
             "pergunta_en": "How old are you?",
             "dica": "'I am X years old' — use TO BE, não HAVE."},
            {"pergunta_pt": "De onde você é?",
             "pergunta_en": "Where are you from?",
             "dica": "'I am from Brazil' ou 'I am from Marília.'"},
            {"pergunta_pt": "Onde você mora?",
             "pergunta_en": "Where do you live?",
             "dica": "'I live in...' + cidade ou bairro."},
            {"pergunta_pt": "O que você faz da vida?",
             "pergunta_en": "What do you do?",
             "dica": "'I am a student/teacher/...' ou 'I work as a...'"},
            {"pergunta_pt": "Conte uma coisa interessante sobre você.",
             "pergunta_en": "Tell me one interesting thing about yourself.",
             "dica": "Hobby, talento, algo único: 'I can play guitar', 'I love cooking'..."},
        ]
    },
    {
        "id": "familia",
        "icone": "👨‍👩‍👧",
        "tema": "Família",
        "descricao": "Fale sobre seus pais, irmãos, e momentos em família.",
        "perguntas": [
            {"pergunta_pt": "Você tem irmãos? Quantos?",
             "pergunta_en": "Do you have brothers or sisters? How many?",
             "dica": "'I have two brothers and one sister' — use HAVE pra contar."},
            {"pergunta_pt": "Qual o nome deles?",
             "pergunta_en": "What are their names?",
             "dica": "'Their names are...' ou 'My brother's name is...'"},
            {"pergunta_pt": "Você é o mais velho, mais novo ou do meio?",
             "pergunta_en": "Are you the oldest, the youngest, or the middle child?",
             "dica": "'I am the oldest/youngest/middle child.'"},
            {"pergunta_pt": "Você mora com sua família?",
             "pergunta_en": "Do you live with your family?",
             "dica": "'Yes, I live with...' ou 'No, I live alone/with friends/...'"},
            {"pergunta_pt": "Quem é a pessoa mais próxima de você na sua família?",
             "pergunta_en": "Who is the closest person to you in your family?",
             "dica": "'My closest person is my mom/dad/sister...' + 'because...'"},
            {"pergunta_pt": "Conte uma memória feliz em família.",
             "pergunta_en": "Tell me about a happy memory with your family.",
             "dica": "Use passado: 'I remember when we...', 'We traveled to...', 'We celebrated...'"},
        ]
    },
    {
        "id": "rotina",
        "icone": "⏰",
        "tema": "Rotina",
        "descricao": "Descreva como é um dia comum na sua vida.",
        "perguntas": [
            {"pergunta_pt": "Que horas você costuma acordar?",
             "pergunta_en": "What time do you usually wake up?",
             "dica": "'I usually wake up at 7 a.m.' Use presente simples + 'at + hora'."},
            {"pergunta_pt": "Qual é a primeira coisa que você faz de manhã?",
             "pergunta_en": "What is the first thing you do in the morning?",
             "dica": "'The first thing I do is...' ou 'I pray', 'I drink coffee', 'I take a shower'..."},
            {"pergunta_pt": "Você toma café da manhã? O que come?",
             "pergunta_en": "Do you eat breakfast? What do you eat?",
             "dica": "'Yes, I eat...' / 'No, I usually skip breakfast.'"},
            {"pergunta_pt": "Como você vai pro trabalho/escola?",
             "pergunta_en": "How do you go to work or school?",
             "dica": "'I go by car/bus/bike/foot.' Use 'by' + transporte."},
            {"pergunta_pt": "O que você faz à noite?",
             "pergunta_en": "What do you do in the evening?",
             "dica": "'In the evening I...' + verbos: read, watch TV, pray, study..."},
            {"pergunta_pt": "Que horas você costuma dormir?",
             "pergunta_en": "What time do you usually go to bed?",
             "dica": "'I usually go to bed at 10 p.m.'"},
        ]
    },
    {
        "id": "igreja_fe",
        "icone": "⛪",
        "tema": "Igreja e Fé",
        "descricao": "Compartilhe sobre sua fé, igreja e relacionamento com Deus.",
        "perguntas": [
            {"pergunta_pt": "Qual igreja você frequenta?",
             "pergunta_en": "Which church do you attend?",
             "dica": "'I attend Bethany Church' ou 'My church is...'"},
            {"pergunta_pt": "Há quanto tempo você é cristão?",
             "pergunta_en": "How long have you been a Christian?",
             "dica": "'I have been a Christian for X years.' (Present Perfect Continuous)"},
            {"pergunta_pt": "O que você faz na igreja no domingo?",
             "pergunta_en": "What do you do at church on Sunday?",
             "dica": "'I sing in the choir', 'I help with kids', 'I listen to the sermon'..."},
            {"pergunta_pt": "Tem uma música de adoração favorita?",
             "pergunta_en": "Do you have a favorite worship song?",
             "dica": "'My favorite worship song is...' + 'because...'"},
            {"pergunta_pt": "Qual seu versículo bíblico favorito? Por quê?",
             "pergunta_en": "What is your favorite Bible verse and why?",
             "dica": "'My favorite verse is...' + 'It is from John/Psalms/...' + 'because...'"},
            {"pergunta_pt": "Como você costuma orar?",
             "pergunta_en": "How do you usually pray?",
             "dica": "'I pray every morning', 'I thank God for...', 'I ask God for...'"},
            {"pergunta_pt": "Conte sobre quando sentiu Deus pela primeira vez.",
             "pergunta_en": "Tell me about when you first felt God in your life.",
             "dica": "Use passado: 'I felt God when...', 'It was during...', 'I remember...'"},
        ]
    },
    {
        "id": "comida",
        "icone": "🍽️",
        "tema": "Comida",
        "descricao": "Comida favorita, cozinha brasileira, e experiências culinárias.",
        "perguntas": [
            {"pergunta_pt": "Qual é sua comida favorita?",
             "pergunta_en": "What is your favorite food?",
             "dica": "'My favorite food is...' + 'because I love...'"},
            {"pergunta_pt": "Você sabe cozinhar? O que sabe fazer?",
             "pergunta_en": "Do you know how to cook? What can you cook?",
             "dica": "'Yes, I can cook...' / 'No, I do not know how to cook.'"},
            {"pergunta_pt": "Descreva um café da manhã típico no Brasil.",
             "pergunta_en": "Describe a typical breakfast in Brazil.",
             "dica": "'A typical Brazilian breakfast has...' + bread, coffee, fruits, cheese..."},
            {"pergunta_pt": "Qual comida você não gosta?",
             "pergunta_en": "What food do you not like?",
             "dica": "'I do not like...' + 'because it is too...' (salty, spicy, sweet)"},
            {"pergunta_pt": "Você já provou comida americana? O quê?",
             "pergunta_en": "Have you ever tried American food? What did you try?",
             "dica": "'Yes, I have tried...' / 'No, I have never tried...' (Present Perfect)"},
        ]
    },
    {
        "id": "sonhos_futuro",
        "icone": "⭐",
        "tema": "Sonhos e Futuro",
        "descricao": "Seus planos, sonhos, e o futuro que você espera.",
        "perguntas": [
            {"pergunta_pt": "Qual é seu maior sonho na vida?",
             "pergunta_en": "What is your biggest dream in life?",
             "dica": "'My biggest dream is to...' + verbo no infinitivo."},
            {"pergunta_pt": "O que você quer fazer nos próximos 5 anos?",
             "pergunta_en": "What do you want to do in the next 5 years?",
             "dica": "'I want to...' + verbo. Pode listar várias coisas."},
            {"pergunta_pt": "Você quer viajar? Pra onde?",
             "pergunta_en": "Do you want to travel? Where to?",
             "dica": "'Yes, I want to travel to...' / 'My dream destination is...'"},
            {"pergunta_pt": "Que tipo de trabalho você sonha fazer?",
             "pergunta_en": "What kind of work do you dream of doing?",
             "dica": "'I want to be a...' + profissão, ou 'I want to work with...'"},
            {"pergunta_pt": "Como sua fé pode ajudar você a alcançar seus sonhos?",
             "pergunta_en": "How can your faith help you reach your dreams?",
             "dica": "'My faith helps me to...' / 'God gives me...'"},
        ]
    },
    {
        "id": "sentimentos",
        "icone": "💗",
        "tema": "Sentimentos",
        "descricao": "Como você se sente, o que te alegra e o que te abala.",
        "perguntas": [
            {"pergunta_pt": "Como você está se sentindo hoje?",
             "pergunta_en": "How are you feeling today?",
             "dica": "'I am feeling happy/sad/tired/...' Use TO BE, não HAVE."},
            {"pergunta_pt": "O que te deixa feliz?",
             "pergunta_en": "What makes you happy?",
             "dica": "'X makes me happy' — sujeito + makes me + adjetivo."},
            {"pergunta_pt": "O que te deixa triste?",
             "pergunta_en": "What makes you sad?",
             "dica": "'It makes me sad when...' ou 'I feel sad when...'"},
            {"pergunta_pt": "O que você faz quando está nervoso?",
             "pergunta_en": "What do you do when you are nervous?",
             "dica": "'When I am nervous, I...' + pray, breathe, walk, etc."},
            {"pergunta_pt": "Conte um momento em que sentiu muita gratidão.",
             "pergunta_en": "Tell me about a moment when you felt very grateful.",
             "dica": "Use passado: 'I felt grateful when...', 'I will never forget when...'"},
        ]
    },
    {
        "id": "testemunho",
        "icone": "✨",
        "tema": "Testemunho",
        "descricao": "Pratique compartilhar sua história com Deus em inglês.",
        "perguntas": [
            {"pergunta_pt": "Quando você se tornou cristão?",
             "pergunta_en": "When did you become a Christian?",
             "dica": "'I became a Christian when I was X years old' ou 'in [ano]'."},
            {"pergunta_pt": "Conte um momento em que Deus respondeu sua oração.",
             "pergunta_en": "Tell me about a time when God answered your prayer.",
             "dica": "Use passado: 'I prayed for...', 'God answered when...', 'It was a miracle'."},
            {"pergunta_pt": "Quem te apresentou a Jesus?",
             "pergunta_en": "Who introduced you to Jesus?",
             "dica": "'My mother/father/friend/pastor introduced me to Jesus.'"},
            {"pergunta_pt": "Como sua vida mudou depois que conheceu Deus?",
             "pergunta_en": "How has your life changed since you met God?",
             "dica": "Present Perfect: 'My life has changed...' + 'I have more peace/joy/...'"},
            {"pergunta_pt": "O que você diria pra alguém que não conhece Jesus?",
             "pergunta_en": "What would you say to someone who does not know Jesus?",
             "dica": "'I would tell them that...' ou 'Jesus loves you', 'He can change your life'."},
        ]
    },
    {
        "id": "aconselhamento",
        "icone": "🫂",
        "tema": "Aconselhamento",
        "descricao": "Pratique consolar, encorajar e dar conselhos em inglês.",
        "perguntas": [
            {"pergunta_pt": "Um amigo está triste. O que você diz?",
             "pergunta_en": "A friend is feeling sad. What do you say?",
             "dica": "'I am here for you', 'Do not worry', 'God loves you'."},
            {"pergunta_pt": "Alguém está doente. O que você diz?",
             "pergunta_en": "Someone is sick. What do you say?",
             "dica": "'I hope you get better soon', 'I will pray for you'."},
            {"pergunta_pt": "Um amigo conseguiu um novo emprego. Como você o parabeniza?",
             "pergunta_en": "A friend got a new job. How do you congratulate them?",
             "dica": "'Congratulations!', 'I am so happy for you!', 'You deserve it!'"},
            {"pergunta_pt": "Alguém está com dúvidas sobre Deus. Como você encoraja?",
             "pergunta_en": "Someone is doubting God. How do you encourage them?",
             "dica": "'God is real', 'I had doubts too, but...', 'Read the Bible and pray'."},
            {"pergunta_pt": "Um amigo perdeu alguém querido. O que você diz?",
             "pergunta_en": "A friend lost someone they love. What do you say?",
             "dica": "'I am so sorry for your loss', 'I will pray for you', 'God is with you'."},
        ]
    },
    {
        "id": "conversa_casual",
        "icone": "💬",
        "tema": "Conversa Casual",
        "descricao": "Small talk: assuntos leves do dia a dia em inglês.",
        "perguntas": [
            {"pergunta_pt": "Como está o tempo hoje?",
             "pergunta_en": "How is the weather today?",
             "dica": "'It is sunny/rainy/hot/cold today.' Use 'it is' pra clima."},
            {"pergunta_pt": "O que você fez no fim de semana passado?",
             "pergunta_en": "What did you do last weekend?",
             "dica": "Passado: 'I went to...', 'I visited...', 'I stayed home and...'"},
            {"pergunta_pt": "O que está planejando pra amanhã?",
             "pergunta_en": "What are you planning for tomorrow?",
             "dica": "'I am going to...' / 'Tomorrow I will...'"},
            {"pergunta_pt": "Viu algum filme bom recentemente?",
             "pergunta_en": "Have you seen any good movies lately?",
             "dica": "'Yes, I watched...' / 'No, I have not watched any movies lately.'"},
            {"pergunta_pt": "Qual a melhor parte da sua semana?",
             "pergunta_en": "What is the best part of your week?",
             "dica": "'The best part of my week is/was...' + por quê."},
        ]
    },
]

# Termos da igreja/bíblicos que o spellchecker pode marcar erradamente
WHITELIST_SPELL = {
    "hallelujah", "amen", "pastor", "messiah", "savior", "gospel",
    "psalms", "proverbs", "deuteronomy", "leviticus", "ecclesiastes",
    "exodus", "isaiah", "jeremiah", "ezekiel", "philippians", "ephesians",
    "galatians", "thessalonians", "philemon", "hebrews", "revelation",
    "jesus", "christ", "moses", "noah", "abraham", "isaac", "jacob",
    "joseph", "mary", "magdalene", "nazareth", "bethlehem", "calvary",
}

def corrigir_ingles(texto):
    """Analisa texto em inglês escrito por brasileiro. Retorna lista de problemas + sugestões."""
    problemas = []
    if not texto or not texto.strip():
        return problemas
    t = texto.strip()

    # 1. Capitalização inicial
    if t[0].islower():
        problemas.append({
            "tipo": "Capitalização",
            "msg": "Frases em inglês começam com letra maiúscula.",
            "exemplo": f"'{t[0]}...' → '{t[0].upper()}...'"
        })

    # 2. "i" sozinho deve ser "I" (pronome eu)
    matches_i = re.findall(r'\bi\b', t)
    if matches_i:
        problemas.append({
            "tipo": "Pronome I",
            "msg": "O pronome 'I' (eu) é SEMPRE maiúsculo em inglês.",
            "exemplo": "'i am happy' → 'I am happy'"
        })

    # 3. Verbo TO BE incorreto
    if re.search(r'\bI\s+(are|is|be|were)\b', t, re.IGNORECASE):
        problemas.append({
            "tipo": "Verbo TO BE",
            "msg": "Com 'I' use AM (presente) ou WAS (passado). Nunca is/are/be/were.",
            "exemplo": "'I are happy' → 'I AM happy'"
        })
    if re.search(r'\b(he|she|it)\s+(are|am|were)\b', t, re.IGNORECASE):
        problemas.append({
            "tipo": "Verbo TO BE",
            "msg": "Com he/she/it use IS (presente) ou WAS (passado).",
            "exemplo": "'She are nice' → 'She IS nice'"
        })
    if re.search(r'\b(we|they|you)\s+(is|am|was)\b', t, re.IGNORECASE):
        problemas.append({
            "tipo": "Verbo TO BE",
            "msg": "Com we/they/you use ARE (presente) ou WERE (passado).",
            "exemplo": "'They is here' → 'They ARE here'"
        })

    # 4. Brasileirismo: "I have X years"
    m = re.search(r'\b(I|he|she|you|we|they)\s+(have|has|had)\s+(\d+)\s+years?\b', t, re.IGNORECASE)
    if m:
        problemas.append({
            "tipo": "Idade",
            "msg": "Em inglês, idade usa TO BE: '___ AM/IS X years old' (não HAVE).",
            "exemplo": f"'I have {m.group(3)} years' → 'I am {m.group(3)} years old'"
        })

    # 5. Brasileirismo: "I have hungry / cold / etc"
    estados = ["hungry", "thirsty", "cold", "hot", "tired", "sleepy",
               "scared", "afraid", "happy", "sad", "angry", "nervous"]
    pat = r'\b(I|you|he|she|we|they)\s+(have|has|had)\s+(' + '|'.join(estados) + r')\b'
    m = re.search(pat, t, re.IGNORECASE)
    if m:
        problemas.append({
            "tipo": "Estado/Sentimento",
            "msg": "Estados e sentimentos usam TO BE em inglês, não HAVE.",
            "exemplo": f"'I have {m.group(3)}' → 'I AM {m.group(3)}'"
        })

    # 6. Concordância 3ª pessoa singular (he/she/it precisa de S no verbo)
    verbos_terceira = ["work", "live", "love", "like", "play", "study", "read", "write",
                       "eat", "drink", "go", "come", "do", "want", "need", "speak",
                       "talk", "see", "watch", "sleep", "wake", "pray", "sing", "help",
                       "ask", "tell", "give", "take", "make", "feel", "know", "think"]
    pat3 = r'\b(he|she|it)\s+(' + '|'.join(verbos_terceira) + r')\b(?!s)'
    if re.search(pat3, t, re.IGNORECASE):
        problemas.append({
            "tipo": "Concordância (he/she/it)",
            "msg": "Com he/she/it, adicione S no fim do verbo: he WORKS, she PLAYS, it GOES.",
            "exemplo": "'He work' → 'He works'"
        })

    # 7. Negação errada: "I no like"
    if re.search(r'\b(I|you|we|they)\s+no\s+\w+', t, re.IGNORECASE):
        problemas.append({
            "tipo": "Negação",
            "msg": "Pra negar verbos comuns com I/you/we/they: use DO NOT (don't) + verbo.",
            "exemplo": "'I no like' → 'I do not like' (ou 'I don't like')"
        })
    if re.search(r'\b(he|she|it)\s+no\s+\w+', t, re.IGNORECASE):
        problemas.append({
            "tipo": "Negação",
            "msg": "Pra negar com he/she/it: use DOES NOT (doesn't) + verbo (sem S).",
            "exemplo": "'She no eat' → 'She does not eat'"
        })

    # 8. "Don't" com he/she/it (deveria ser "doesn't")
    if re.search(r"\b(he|she|it)\s+(don't|do\s+not)\b", t, re.IGNORECASE):
        problemas.append({
            "tipo": "Negação 3ª pessoa",
            "msg": "Com he/she/it use DOESN'T (não DON'T).",
            "exemplo": "'She don't know' → 'She doesn't know'"
        })

    # 9. Ortografia (se spellchecker disponível)
    if SPELL_OK:
        try:
            spell = get_spell()
            palavras = re.findall(r"\b[a-zA-Z']+\b", t)
            # Só verifica palavras minúsculas (evita nomes próprios)
            candidatas = [w for w in palavras if len(w) > 2 and w.islower()
                          and w not in WHITELIST_SPELL]
            misspelled = spell.unknown(candidatas)
            if misspelled:
                sugestoes = []
                for w in list(misspelled)[:5]:
                    cor = spell.correction(w)
                    if cor and cor != w:
                        sugestoes.append(f"'{w}' → '{cor}'")
                if sugestoes:
                    problemas.append({
                        "tipo": "Ortografia",
                        "msg": "Possíveis erros de ortografia detectados:",
                        "exemplo": ", ".join(sugestoes)
                    })
        except Exception:
            pass  # silencia erros do spellchecker

    return problemas

# =========================================================
# EXPLICAÇÕES PEDAGÓGICAS (lições gramaticais)
# =========================================================
EXPLICACOES = {
    ("Módulo 1: To Be - Presente", "Fase 1"): "Com 'I' usamos sempre 'am'. Nunca 'is' nem 'are'.",
    ("Módulo 1: To Be - Presente", "Fase 2"): "Com he, she, it usamos 'is'. (She IS, He IS, It IS).",
    ("Módulo 1: To Be - Presente", "Fase 3"): "Com we, you, they usamos 'are'.",
    ("Módulo 1: To Be - Presente", "Fase 4"): "They + are = correto. They + was/be são erros comuns.",
    ("Módulo 1: To Be - Presente", "Fase 5"): "He + is. Decore essa cola: I am / He-She-It is / We-You-They are.",
    ("Módulo 1: To Be - Presente", "Fase 8"): "I am hungry = 'estou COM fome'. Em inglês, fome é uma característica (be), não algo que se 'tem'.",
    ("Módulo 2: To Be - Negativo", "Fase 1"): "Para negar com 'to be', basta adicionar 'not' depois do verbo: am not / is not / are not.",
    ("Módulo 2: To Be - Negativo", "Fase 3"): "He IS not (não 'He not is'). A ordem é sempre: sujeito + verbo + not.",
    ("Módulo 3: To Be - Passado", "Fase 1"): "No passado: I/He/She/It = was. You/We/They = were.",
    ("Módulo 3: To Be - Passado", "Fase 2"): "They WERE (não 'was'). Plural sempre usa 'were'.",
    ("Módulo 4: To Be - Futuro", "Fase 1"): "Futuro: will + be (para todos os sujeitos). 'Would' significa 'estaria', é condicional.",
    ("Módulo 11: Pronomes Possessivos", "Fase 1"): "'My' vem antes do substantivo (My Bible). 'Mine' vem sozinho (It is mine).",
    ("Módulo 17: Question Words", "Fase 8"): "'How much' = quanto (incontáveis ou preço). 'How many' = quantos (contáveis).",
    ("Módulo 22: Preposições de Lugar", "Fase 1"): "IN = dentro de algo grande (in the church). ON = em cima (on the table). AT = ponto específico (at the door).",
    ("Módulo 23: Present Simple - Afirmativo", "Fase 1"): "No presente simples, I/You/We/They usam o verbo no infinitivo. He/She/It adicionam 's' no final.",
    ("Módulo 23: Present Simple - Afirmativo", "Fase 2"): "She/He/It + verbo + S. Ex: She SINGS, He WORKS, It RAINS.",
    ("Módulo 23: Present Simple - Afirmativo", "Fase 3"): "Verbos terminados em consoante+Y viram IES com he/she/it: study → studies.",
    ("Módulo 24: Present Simple - Negativo", "Fase 1"): "Para negar verbos comuns: I/You/We/They + DO NOT + verbo. He/She/It + DOES NOT + verbo (sem o S no verbo).",
    ("Módulo 24: Present Simple - Negativo", "Fase 2"): "DOES NOT come com he/she/it. Atenção: o verbo perde o S quando tem 'does not'. SHE DOES NOT EAT (não 'eats').",
    ("Módulo 25: Going to - Futuro", "Fase 1"): "Going to expressa planos/intenções. Estrutura: SUJEITO + AM/IS/ARE + GOING TO + verbo no infinitivo.",
    ("Módulo 26: Modal Verbs (can, must, should)", "Fase 1"): "CAN = poder (capacidade). MUST = dever (obrigação forte). SHOULD = deveria (sugestão). Verbos modais NUNCA vêm com 'to': 'I can help' (não 'I can to help').",
    ("Módulo 26: Modal Verbs (can, must, should)", "Fase 5"): "Negativo: CANNOT (uma palavra só) ou CAN'T. MUST NOT ou MUSTN'T. SHOULD NOT ou SHOULDN'T.",
    ("Módulo 27: Verbos no Passado (Regulares)", "Fase 1"): "Verbos regulares no passado: adicione -ED. Work → Worked. Play → Played. Verbos terminados em E só adicionam D: live → lived.",
    ("Módulo 28: Verbos no Passado (Irregulares)", "Fase 1"): "Verbos irregulares não seguem regra: GO → WENT, COME → CAME, SEE → SAW. Precisa decorar.",
}

# --- INICIALIZAÇÃO DO BANCO ---
def iniciar_banco():
    con = conectar(); cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS alunos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        pin_hash TEXT,
        xp_total INTEGER DEFAULT 0,
        ultimo_acesso TEXT,
        streak INTEGER DEFAULT 0,
        melhor_streak INTEGER DEFAULT 0,
        criado_em TEXT
    )''')
    cur.execute('CREATE TABLE IF NOT EXISTS modulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL UNIQUE, nivel INTEGER DEFAULT 1, audio_puro INTEGER DEFAULT 0)')
    cur.execute('''CREATE TABLE IF NOT EXISTS licoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        modulo_id INTEGER,
        titulo_botao TEXT, pergunta TEXT,
        opcao_1 TEXT, opcao_2 TEXT, opcao_3 TEXT, opcao_4 TEXT,
        resposta_correta TEXT,
        explicacao TEXT
    )''')
    cur.execute('CREATE TABLE IF NOT EXISTS progresso (aluno_id INTEGER, licao_id INTEGER, PRIMARY KEY (aluno_id, licao_id))')
    cur.execute('CREATE TABLE IF NOT EXISTS erros (aluno_id INTEGER, licao_id INTEGER, count INTEGER DEFAULT 1, ultimo_erro TEXT, PRIMARY KEY (aluno_id, licao_id))')
    cur.execute('CREATE TABLE IF NOT EXISTS conquistas (aluno_id INTEGER, badge_id TEXT, obtida_em TEXT, PRIMARY KEY (aluno_id, badge_id))')
    cur.execute('''CREATE TABLE IF NOT EXISTS duelos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        desafiante_id INTEGER NOT NULL,
        desafiado_id INTEGER NOT NULL,
        questoes_ids TEXT NOT NULL,
        score_desafiante INTEGER,
        score_desafiado INTEGER,
        vencedor_id INTEGER,
        status TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS torneios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        nivel INTEGER NOT NULL,
        tamanho INTEGER NOT NULL,
        status TEXT NOT NULL,
        campeao_id INTEGER,
        criado_em TEXT NOT NULL,
        finalizado_em TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS torneio_partidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        torneio_id INTEGER NOT NULL,
        rodada INTEGER NOT NULL,
        posicao INTEGER NOT NULL,
        jogador1_id INTEGER,
        jogador2_id INTEGER,
        duelo_id INTEGER,
        vencedor_id INTEGER,
        proxima_partida_id INTEGER
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS desafios_diarios (
        aluno_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        licao_id INTEGER,
        completado INTEGER DEFAULT 0,
        PRIMARY KEY (aluno_id, data)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS conversas_respondidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id INTEGER NOT NULL,
        conversa_id TEXT NOT NULL,
        resposta TEXT NOT NULL,
        erros_qtd INTEGER DEFAULT 0,
        respondido_em TEXT NOT NULL
    )''')

    # MIGRAÇÕES: tenta adicionar colunas novas se o banco for antigo
    for tabela, coluna, tipo, default in [
        ("alunos", "pin_hash", "TEXT", None),
        ("alunos", "ultimo_acesso", "TEXT", None),
        ("alunos", "streak", "INTEGER", 0),
        ("alunos", "melhor_streak", "INTEGER", 0),
        ("alunos", "criado_em", "TEXT", None),
        ("alunos", "vitorias_duelo", "INTEGER", 0),
        ("alunos", "derrotas_duelo", "INTEGER", 0),
        ("alunos", "empates_duelo", "INTEGER", 0),
        ("alunos", "streak_vitorias_duelo", "INTEGER", 0),
        ("alunos", "melhor_streak_vitorias_duelo", "INTEGER", 0),
        ("modulos", "nivel", "INTEGER", 1),
        ("modulos", "audio_puro", "INTEGER", 0),
        ("licoes", "opcao_4", "TEXT", None),
        ("licoes", "explicacao", "TEXT", None),
        ("duelos", "xp_apostado", "INTEGER", None),
        ("duelos", "tempo_desafiante", "REAL", None),
        ("duelos", "tempo_desafiado", "REAL", None),
        ("duelos", "torneio_partida_id", "INTEGER", None),
    ]:
        try:
            if default is not None:
                cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo} DEFAULT {default}")
            else:
                cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        except sqlite3.OperationalError:
            pass

    # Preenche opcao_4 nulas da versão antiga
    cur.execute("UPDATE licoes SET opcao_4 = 'None of the above' WHERE opcao_4 IS NULL")

    # Inserir só módulos que ainda não existem (por título)
    for titulo, nivel, licoes in TRILHA:
        eh_audio_puro = 1 if titulo in MODULOS_AUDIO_PURO else 0
        cur.execute("SELECT id FROM modulos WHERE titulo = ?", (titulo,))
        if cur.fetchone():
            # módulo já existe - atualizar nível e audio_puro caso tenha mudado
            cur.execute("UPDATE modulos SET nivel = ?, audio_puro = ? WHERE titulo = ?",
                        (nivel, eh_audio_puro, titulo))
            continue
        cur.execute("INSERT INTO modulos (titulo, nivel, audio_puro) VALUES (?, ?, ?)",
                    (titulo, nivel, eh_audio_puro))
        mid = cur.lastrowid
        for l in licoes:
            explicacao = EXPLICACOES.get((titulo, l[0]), "")
            cur.execute(
                "INSERT INTO licoes (modulo_id, titulo_botao, pergunta, opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta, explicacao) VALUES (?,?,?,?,?,?,?,?,?)",
                (mid, l[0], l[1], l[2], l[3], l[4], l[5], l[2], explicacao)
            )
    con.commit(); con.close()

iniciar_banco()

# --- ESTADOS DA SESSÃO ---
for k, v in [("tela", "login"), ("vidas", 3), ("respondido", False),
             ("opcoes_atuais", []), ("erros_na_licao", 0),
             ("modo_revisao", False), ("login_etapa", "nome"),
             ("duelo_id", None), ("duelo_modo", None), ("duelo_score", 0),
             ("duelo_questoes", []), ("duelo_idx", 0),
             ("duelo_iniciado_em", None), ("duelo_aposta", None),
             ("duelo_torneio_partida_id", None),
             ("modo_desafio_diario", False), ("onboarding_slide", 0),
             ("modo_cronometro", False), ("questao_iniciada_em", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

def reset_para_inicio():
    """Volta para a tela principal limpando estado de lição."""
    st.session_state.tela = "inicio"
    st.session_state.respondido = False
    st.session_state.opcoes_atuais = []
    st.session_state.erros_na_licao = 0
    st.session_state.modo_revisao = False
    st.session_state.modo_desafio_diario = False
    st.session_state.duelo_id = None
    st.session_state.duelo_modo = None
    st.session_state.duelo_score = 0
    st.session_state.duelo_questoes = []
    st.session_state.duelo_idx = 0
    st.session_state.duelo_iniciado_em = None
    st.session_state.duelo_aposta = None
    st.session_state.duelo_torneio_partida_id = None

# --- Funções auxiliares da tela de lição ---
def processar_resposta(resp, correta, lic_id, explicacao, forcar=None):
    """Trata acerto/erro. Se forcar=True/False, ignora comparação direta (caso typing)."""
    uid = st.session_state.uid
    if forcar is None:
        acertou = (resp == correta)
    else:
        acertou = forcar
    if acertou:
        if st.session_state.get("modo_desafio_diario"):
            xp_ganho = DESAFIO_XP_BONUS
        else:
            xp_ganho = XP_REVISAO if st.session_state.modo_revisao else XP_POR_ACERTO

        # Bônus de velocidade se cronômetro estiver ativo
        bonus = 0
        if st.session_state.get("modo_cronometro") and st.session_state.get("questao_iniciada_em"):
            tempo_resposta = time.time() - st.session_state.questao_iniciada_em
            bonus = calcular_bonus_velocidade(tempo_resposta)
            st.session_state.ultimo_tempo_resposta = tempo_resposta
            st.session_state.ultimo_bonus = bonus

        st.session_state.feedback_acerto = True
        st.session_state.feedback_xp = xp_ganho + bonus
        st.session_state.feedback_bonus = bonus
        st.session_state.feedback = "✅ Correto!"
        executar("UPDATE alunos SET xp_total = xp_total + ? WHERE id = ?", (xp_ganho + bonus, uid))
        if not st.session_state.modo_revisao and not st.session_state.get("modo_desafio_diario"):
            executar("INSERT OR IGNORE INTO progresso VALUES (?,?)", (uid, lic_id))
        if st.session_state.modo_revisao:
            executar("UPDATE erros SET count = MAX(count - 1, 0) WHERE aluno_id = ? AND licao_id = ?", (uid, lic_id))
        if st.session_state.get("modo_desafio_diario"):
            marcar_desafio_completado(uid)
    else:
        st.session_state.vidas -= 1
        st.session_state.erros_na_licao += 1
        st.session_state.feedback_acerto = False
        st.session_state.feedback = f"❌ Não foi dessa vez. Resposta correta: **{correta}**"
        registrar_erro(uid, lic_id)
    st.session_state.respondido = True

def mostrar_feedback(correta, explicacao):
    if st.session_state.get("feedback_acerto"):
        xp_ganho = st.session_state.get("feedback_xp", 10)
        bonus = st.session_state.get("feedback_bonus", 0)
        tempo = st.session_state.get("ultimo_tempo_resposta")
        bonus_html = ""
        if bonus > 0:
            bonus_html = f" <span style='color:var(--accent);font-size:0.95rem;'>🚀 +{bonus} bônus ({tempo:.1f}s)</span>"
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:14px;'>"
            f"<span style='font-size:1.6rem;'>✅</span>"
            f"<span style='font-size:1.2rem;font-weight:600;color:var(--primary-light);'>Correto!</span>"
            f"<span class='xp-floating'>+{xp_ganho} XP</span>"
            f"{bonus_html}"
            f"</div>", unsafe_allow_html=True)
    else:
        st.markdown(st.session_state.feedback)
    botao_audio(correta, "🔊 Ouvir a resposta correta")
    if explicacao:
        st.markdown(f"<div class='explicacao'>💡 <b>Dica:</b> {explicacao}</div>", unsafe_allow_html=True)

def botao_proxima(trilha, idx):
    if st.button("Avançar ➡️"):
        if idx + 1 < len(trilha):
            st.session_state.idx += 1
            st.session_state.respondido = False
            st.session_state.opcoes_atuais = []
            st.session_state.questao_iniciada_em = None  # reseta cronômetro
            st.rerun()
        else:
            uid = st.session_state.uid
            novas = verificar_conquistas(uid)
            if not st.session_state.modo_revisao and trilha:
                lic_id_final = trilha[idx][0]
                modulo = consultar_um("""SELECT m.titulo FROM modulos m
                                         JOIN licoes l ON l.modulo_id = m.id
                                         WHERE l.id = ?""", (lic_id_final,))
                if modulo:
                    pendentes = consultar_um("""SELECT COUNT(*) FROM licoes l
                                                WHERE l.modulo_id = (SELECT modulo_id FROM licoes WHERE id = ?)
                                                AND l.id NOT IN (SELECT licao_id FROM progresso WHERE aluno_id = ?)""",
                                             (lic_id_final, uid))[0]
                    if pendentes == 0:
                        b = conceder_badge_modulo(uid, modulo[0])
                        if b: novas.append(b)
            if st.session_state.erros_na_licao == 0 and not st.session_state.modo_revisao:
                if conceder_conquista(uid, "perfeccionista"):
                    novas.append("perfeccionista")
            st.session_state.conquistas_novas = novas
            st.session_state.tela = "conclusao_trilha"
            st.rerun()

# =========================================================
# SIDEBAR DE NAVEGAÇÃO (renderiza em todas as telas exceto login/onboarding)
# =========================================================
# =========================================================
# CERTIFICADOS EM PDF
# =========================================================
def gerar_certificado_pdf(nome_aluno, titulo_modulo, data_conclusao, xp_modulo):
    """Gera certificado PDF em memória, retorna bytes (ou None se reportlab não estiver instalado)."""
    if not REPORTLAB_OK:
        return None
    from io import BytesIO

    buf = BytesIO()
    largura, altura = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    # Cores da identidade visual
    cor_primary = HexColor("#10B981")
    cor_gold = HexColor("#F59E0B")
    cor_dark = HexColor("#0B1014")
    cor_text = HexColor("#1F2937")
    cor_dim = HexColor("#6B7280")

    # Borda decorativa (frame duplo)
    c.setStrokeColor(cor_primary)
    c.setLineWidth(3)
    c.rect(0.8*cm, 0.8*cm, largura - 1.6*cm, altura - 1.6*cm)
    c.setStrokeColor(cor_gold)
    c.setLineWidth(1)
    c.rect(1.2*cm, 1.2*cm, largura - 2.4*cm, altura - 2.4*cm)

    # Cabeçalho - nome da escola
    c.setFillColor(cor_dim)
    c.setFont("Helvetica", 12)
    c.drawCentredString(largura/2, altura - 2.2*cm, "BETHANY CHURCH ENGLISH SCHOOL")

    c.setFillColor(cor_primary)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(largura/2, altura - 2.8*cm, "Sheep Teacher")

    # Título do certificado
    c.setFillColor(cor_dark)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(largura/2, altura - 5.2*cm, "Certificado de Conclusão")

    # Linha decorativa
    c.setStrokeColor(cor_gold)
    c.setLineWidth(2)
    c.line(largura/2 - 3*cm, altura - 5.8*cm, largura/2 + 3*cm, altura - 5.8*cm)

    # Texto introdutório
    c.setFillColor(cor_text)
    c.setFont("Helvetica", 14)
    c.drawCentredString(largura/2, altura - 7.5*cm, "Certificamos que")

    # Nome do aluno em destaque
    c.setFillColor(cor_primary)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(largura/2, altura - 9.2*cm, nome_aluno)

    # Texto de conclusão
    c.setFillColor(cor_text)
    c.setFont("Helvetica", 13)
    c.drawCentredString(largura/2, altura - 10.5*cm, "concluiu com êxito o módulo")

    # Nome do módulo
    c.setFillColor(cor_dark)
    c.setFont("Helvetica-Bold", 20)
    # Remove emoji do título se houver (pra evitar quadradinhos em fontes sem suporte)
    titulo_limpo = "".join(ch for ch in titulo_modulo if ord(ch) < 0x1F000).strip()
    c.drawCentredString(largura/2, altura - 12*cm, titulo_limpo)

    # XP conquistado
    c.setFillColor(cor_gold)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(largura/2, altura - 13.5*cm, f"★  {xp_modulo} XP conquistados  ★")

    # Data + assinaturas
    c.setFillColor(cor_dim)
    c.setFont("Helvetica", 11)
    c.drawCentredString(largura/2, altura - 16*cm, f"Marília, {data_conclusao}")

    # Linha de assinatura
    c.setStrokeColor(cor_dark)
    c.setLineWidth(0.5)
    c.line(largura/2 - 4*cm, 2.8*cm, largura/2 + 4*cm, 2.8*cm)
    c.setFont("Helvetica", 10)
    c.setFillColor(cor_text)
    c.drawCentredString(largura/2, 2.3*cm, "Coordenação - Bethany Church English School")

    c.save()
    buf.seek(0)
    return buf.getvalue()

def modulos_completos_do_aluno(uid):
    """Retorna lista de módulos que o aluno completou (todas as lições)."""
    return consultar("""
        SELECT m.id, m.titulo
        FROM modulos m
        WHERE NOT EXISTS (
            SELECT 1 FROM licoes l
            WHERE l.modulo_id = m.id
            AND l.id NOT IN (SELECT licao_id FROM progresso WHERE aluno_id = ?)
        )
        ORDER BY m.id
    """, (uid,))

def xp_do_modulo(modulo_id):
    """Estima o XP conquistado num módulo (10 XP por lição)."""
    qtd = consultar_um("SELECT COUNT(*) FROM licoes WHERE modulo_id = ?", (modulo_id,))[0]
    return qtd * XP_POR_ACERTO

def render_sidebar():
    """Renderiza menu lateral de navegação. Só pra alunos logados."""
    if st.session_state.tela in ("login", "onboarding") or "uid" not in st.session_state:
        return
    uid = st.session_state.uid
    eh_professor = st.session_state.get("aluno") == "Professor"

    with st.sidebar:
        if eh_professor:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px;padding:8px 0 16px;'>"
                f"<div style='font-size:2.4rem;'>👨‍🏫</div>"
                f"<div><b style='color:var(--text);'>Professor</b><br>"
                f"<small style='color:var(--text-dim);'>Painel admin</small></div></div>",
                unsafe_allow_html=True
            )
            st.markdown("<hr style='border-color:var(--border);margin:4px 0 12px;'>", unsafe_allow_html=True)
            if st.button("🚪 Sair do painel", use_container_width=True, key="sb_sair_admin"):
                for k in ["tela", "aluno", "uid"]:
                    if k in st.session_state: del st.session_state[k]
                st.session_state.tela = "login"; st.rerun()
            return

        # Info do aluno
        aluno_data = consultar_um("SELECT xp_total, streak FROM alunos WHERE id = ?", (uid,))
        xp_a, streak_a = aluno_data if aluno_data else (0, 0)
        nome_aluno = st.session_state.get("aluno", "?")
        _, nivel_nome, xp_no_nivel, xp_pro_proximo = info_nivel(xp_a)
        pct_nivel = int(100 * xp_no_nivel / xp_pro_proximo) if xp_pro_proximo else 100
        fire = f" 🔥{streak_a}" if streak_a and streak_a > 0 else ""

        st.markdown(
            f"<div style='display:flex;align-items:center;gap:12px;padding:8px 0 12px;'>"
            f"{render_avatar(nome_aluno, 44)}"
            f"<div style='flex:1;min-width:0;'>"
            f"<b style='color:var(--text);'>{nome_aluno}</b>{fire}<br>"
            f"<small style='color:var(--text-dim);'>{nivel_nome}</small>"
            f"</div></div>"
            f"<div style='background:var(--border);height:6px;border-radius:3px;overflow:hidden;margin-bottom:4px;'>"
            f"<div style='background:var(--primary);height:100%;width:{pct_nivel}%;transition:width 0.5s;'></div></div>"
            f"<div style='font-size:0.75rem;color:var(--text-muted);margin-bottom:14px;'>"
            f"{xp_no_nivel}/{xp_pro_proximo} XP pro próximo nível</div>",
            unsafe_allow_html=True
        )

        # Notificações
        n_duelos = len(duelos_pendentes_para_responder(uid))
        n_torneios = len(partidas_pendentes_do_aluno(uid))

        # Navegação
        if st.button("🏠 Trilha", use_container_width=True, key="sb_tri"):
            reset_para_inicio(); st.rerun()
        if st.button("🧠 Revisão", use_container_width=True, key="sb_rev"):
            revisao = obter_revisao_inteligente(uid, n=10)
            if not revisao:
                st.toast("Faça uma lição primeiro pra liberar a revisão.")
            else:
                st.session_state.trilha = revisao
                st.session_state.idx = 0
                st.session_state.vidas = 3
                st.session_state.respondido = False
                st.session_state.opcoes_atuais = []
                st.session_state.modo_revisao = True
                st.session_state.tela = "licao"
                st.rerun()
        dlabel = f"🥊 Duelos ({n_duelos})" if n_duelos else "🥊 Duelos"
        if st.button(dlabel, use_container_width=True, key="sb_due"):
            st.session_state.tela = "duelo_lobby"; st.rerun()
        tlabel = f"🏆 Torneios ({n_torneios})" if n_torneios else "🏆 Torneios"
        if st.button(tlabel, use_container_width=True, key="sb_tor"):
            st.session_state.tela = "torneio_lista"; st.rerun()
        if st.button("🏅 Conquistas", use_container_width=True, key="sb_con"):
            st.session_state.tela = "conquistas"; st.rerun()
        if st.button("💬 Conversação", use_container_width=True, key="sb_conv"):
            st.session_state.tela = "conversacao_lista"; st.rerun()
        if st.button("🐑 Falar com Sheep", use_container_width=True, key="sb_chat"):
            st.session_state.tela = "chat_sheep"; st.rerun()
        if st.button("👤 Meu Perfil", use_container_width=True, key="sb_per"):
            st.session_state.perfil_id = uid
            st.session_state.tela = "perfil"; st.rerun()

        st.markdown("<hr style='border-color:var(--border);margin:14px 0 8px;'>", unsafe_allow_html=True)
        if st.button("🚪 Sair", use_container_width=True, key="sb_sair"):
            for k in ["tela", "aluno", "uid"]:
                if k in st.session_state: del st.session_state[k]
            st.session_state.tela = "login"; st.rerun()

render_sidebar()

# =========================================================
# TELA: LOGIN (redesenhada)
# =========================================================
if st.session_state.tela == "login":
    # Hero
    st.markdown("<br>", unsafe_allow_html=True)
    h1, h2, h3 = st.columns([1, 2, 1])
    with h2:
        st.markdown(f"""
        <div class='premium-card' style='text-align:center;'>
            <div class='logo-wrap'>{LOGO_SVG}</div>
            <h1 class='titulo-principal'>Sheep Teacher</h1>
            <p class='subtitulo'>Bethany Church English School<br>
            <span class='destaque-lime'>Learn English. Grow in Faith.</span></p>
        </div>
        """, unsafe_allow_html=True)

    # Stats da escola
    total_alunos = consultar_um("SELECT COUNT(*) FROM alunos WHERE nome != ?", (PROFESSOR_NOME,))[0]
    total_licoes = consultar_um("SELECT COUNT(*) FROM licoes")[0]
    total_xp = consultar_um("SELECT COALESCE(SUM(xp_total),0) FROM alunos WHERE nome != ?", (PROFESSOR_NOME,))[0]
    s1, s2, s3 = st.columns(3)
    with s1: st.markdown(f"<div class='stat-box'><div class='stat-num'>{total_alunos}</div><div class='stat-label'>Alunos</div></div>", unsafe_allow_html=True)
    with s2: st.markdown(f"<div class='stat-box'><div class='stat-num'>{total_licoes}</div><div class='stat-label'>Lições</div></div>", unsafe_allow_html=True)
    with s3: st.markdown(f"<div class='stat-box'><div class='stat-num'>{total_xp}</div><div class='stat-label'>XP Total</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    l1, l2 = st.columns([2, 1])
    with l1:
        tab_login, tab_novo = st.tabs(["🚪 Já tenho conta", "✨ Sou novo aqui"])

        with tab_login:
            with st.form("login_existente"):
                nome_l = st.text_input("Seu nome", placeholder="Como você se cadastrou", key="l_nome").strip()
                pin_l = st.text_input("Seu PIN", type="password", max_chars=8, placeholder="Sua senha de 4+ dígitos", key="l_pin")
                entrar = st.form_submit_button("Entrar 🚀", use_container_width=True)
                if entrar:
                    if not nome_l or not pin_l:
                        st.warning("Preencha nome e PIN.")
                    elif nome_l.lower() == PROFESSOR_NOME:
                        if pin_l == PROFESSOR_PIN:
                            st.session_state.tela = "admin"
                            st.session_state.aluno = "Professor"
                            st.rerun()
                        else:
                            st.error("PIN do professor incorreto.")
                    else:
                        existente = consultar_um("SELECT id, pin_hash FROM alunos WHERE nome = ?", (nome_l,))
                        if not existente:
                            st.error("Conta não encontrada. Vá em 'Sou novo aqui' pra criar uma.")
                        else:
                            uid, pin_h = existente
                            if not pin_h:
                                # Aluno migrado do banco antigo (sem PIN): cadastra agora
                                executar("UPDATE alunos SET pin_hash = ? WHERE id = ?", (hash_pin(pin_l), uid))
                                st.session_state.uid = uid
                                st.session_state.aluno = nome_l
                                atualizar_streak_no_login(uid)
                                verificar_conquistas(uid)
                                reset_para_inicio()
                                st.rerun()
                            elif pin_h == hash_pin(pin_l):
                                st.session_state.uid = uid
                                st.session_state.aluno = nome_l
                                atualizar_streak_no_login(uid)
                                verificar_conquistas(uid)
                                reset_para_inicio()
                                st.rerun()
                            else:
                                st.error("PIN incorreto. Tente de novo.")

        with tab_novo:
            with st.form("cadastro_novo"):
                nome_n = st.text_input("Escolha seu nome", placeholder="Como você vai aparecer no ranking", key="n_nome").strip()
                pin_n = st.text_input("Crie um PIN", type="password", max_chars=8, placeholder="4 ou mais dígitos", key="n_pin")
                pin_n2 = st.text_input("Confirme o PIN", type="password", max_chars=8, placeholder="Digite o PIN de novo", key="n_pin2")
                st.caption("⚠️ Guarde bem seu PIN — é com ele que você volta a entrar.")
                criar = st.form_submit_button("✨ Criar conta", use_container_width=True)
                if criar:
                    if not nome_n or not pin_n:
                        st.warning("Preencha nome e PIN.")
                    elif len(pin_n) < 4:
                        st.warning("O PIN precisa ter pelo menos 4 caracteres.")
                    elif pin_n != pin_n2:
                        st.error("Os PINs não coincidem.")
                    elif nome_n.lower() == PROFESSOR_NOME:
                        st.error("Esse nome é reservado. Escolha outro.")
                    else:
                        ja_existe = consultar_um("SELECT 1 FROM alunos WHERE LOWER(nome) = LOWER(?)", (nome_n,))
                        if ja_existe:
                            st.error(f"❌ O nome **{nome_n}** já está em uso. Escolha outro nome ou, se for você, use a aba 'Já tenho conta'.")
                        else:
                            uid = executar("INSERT INTO alunos (nome, pin_hash, criado_em) VALUES (?, ?, ?)",
                                           (nome_n, hash_pin(pin_n), date.today().isoformat()))
                            st.session_state.uid = uid
                            st.session_state.aluno = nome_n
                            atualizar_streak_no_login(uid)
                            verificar_conquistas(uid)
                            st.session_state.onboarding_slide = 0
                            st.session_state.tela = "onboarding"
                            st.rerun()

    with l2:
        exibir_ranking()
        st.markdown("---")
        st.caption("👨‍🏫 Professores: faça login com o nome 'professor' e o PIN definido no código.")

# =========================================================
# TELA: ADMIN / PAINEL DO PROFESSOR
# =========================================================
elif st.session_state.tela == "admin":
    st.markdown("## 👨‍🏫 Painel do Professor")
    if st.button("⬅️ Sair do painel"):
        for k in ["tela", "aluno", "uid"]:
            if k in st.session_state: del st.session_state[k]
        st.session_state.tela = "login"; st.rerun()

    aba1, aba2, aba3, aba4, aba5 = st.tabs(["📊 Alunos", "❌ Questões mais erradas", "🥊 Duelos", "📦 Conteúdo", "➕ Nova Lição"])

    with aba1:
        st.markdown("### Todos os alunos")
        alunos = consultar("""
            SELECT id, nome, xp_total, streak, melhor_streak, ultimo_acesso, criado_em
            FROM alunos WHERE nome != ? ORDER BY xp_total DESC
        """, (PROFESSOR_NOME,))
        if not alunos:
            st.info("Ainda não há alunos cadastrados.")
        else:
            for a in alunos:
                uid_a, nome_a, xp_a, streak_a, melhor_a, ult_a, crio_a = a
                licoes_a = consultar_um("SELECT COUNT(*) FROM progresso WHERE aluno_id = ?", (uid_a,))[0]
                badges_a = consultar_um("SELECT COUNT(*) FROM conquistas WHERE aluno_id = ?", (uid_a,))[0]
                st.markdown(f"""
                <div class='ranking-box' style='display:flex;align-items:center;gap:12px;'>
                {render_avatar(nome_a, 42)}
                <div style='flex:1;'>
                <b>{nome_a}</b> &nbsp;|&nbsp; <span style='color:var(--primary);font-weight:600;'>{xp_a} XP</span> &nbsp;|&nbsp;
                🔥 {streak_a or 0} (melhor: {melhor_a or 0}) &nbsp;|&nbsp;
                ✅ {licoes_a} lições &nbsp;|&nbsp; 🏅 {badges_a} conquistas<br>
                <small style='color:var(--text-muted);'>Último acesso: {ult_a or '—'} &nbsp;|&nbsp; Cadastrado: {crio_a or '—'}</small>
                </div></div>
                """, unsafe_allow_html=True)

    with aba2:
        st.markdown("### Questões com mais erros (use isso para revisar em aula)")
        problemas = consultar("""
            SELECT l.pergunta, l.resposta_correta, SUM(e.count) as total_erros, COUNT(DISTINCT e.aluno_id) as alunos_que_erraram
            FROM erros e
            JOIN licoes l ON l.id = e.licao_id
            GROUP BY e.licao_id
            ORDER BY total_erros DESC
            LIMIT 15
        """)
        if not problemas:
            st.info("Ainda não há erros registrados.")
        for p in problemas:
            pergunta, correta, total, qtd = p
            st.markdown(f"""
            <div class='ranking-box' style='border-left-color:#ff5252;'>
            <b>{pergunta}</b> → <span style='color:var(--primary);'>{correta}</span><br>
            <small>{total} erros totais, {qtd} aluno(s) erraram</small>
            </div>
            """, unsafe_allow_html=True)

    with aba3:
        st.markdown("### Duelos em andamento e finalizados")
        total_duelos = consultar_um("SELECT COUNT(*) FROM duelos")[0]
        em_andamento = consultar_um("SELECT COUNT(*) FROM duelos WHERE status = 'aguardando_desafiado'")[0]
        finalizados_qtd = consultar_um("SELECT COUNT(*) FROM duelos WHERE status = 'finalizado'")[0]
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='stat-box'><div class='stat-num'>{total_duelos}</div><div class='stat-label'>Total</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='stat-box'><div class='stat-num'>{em_andamento}</div><div class='stat-label'>Em andamento</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='stat-box'><div class='stat-num'>{finalizados_qtd}</div><div class='stat-label'>Finalizados</div></div>", unsafe_allow_html=True)

        st.markdown("#### Últimos 20 duelos")
        ultimos = consultar("""
            SELECT a1.nome, a2.nome, d.score_desafiante, d.score_desafiado, d.status, d.criado_em, d.vencedor_id, d.desafiante_id, d.desafiado_id
            FROM duelos d
            JOIN alunos a1 ON a1.id = d.desafiante_id
            JOIN alunos a2 ON a2.id = d.desafiado_id
            ORDER BY d.criado_em DESC
            LIMIT 20
        """)
        if not ultimos:
            st.caption("Nenhum duelo criado ainda.")
        for n1, n2, s1_, s2_, st_, criado, venc, did, ddoid in ultimos:
            if st_ == "finalizado":
                if venc is None:
                    res = f"🤝 EMPATE {s1_} x {s2_}"
                elif venc == did:
                    res = f"🏆 <b>{n1}</b> venceu ({s1_} x {s2_})"
                else:
                    res = f"🏆 <b>{n2}</b> venceu ({s1_} x {s2_})"
            else:
                res = f"⏳ Aguardando <b>{n2}</b> (placar parcial: {s1_} x —)"
            st.markdown(f"<div class='ranking-box'>{n1} vs {n2}<br>{res}<br><small style='color:var(--text-muted);'>{criado}</small></div>", unsafe_allow_html=True)

    with aba4:
        st.markdown("### Conteúdo atual")
        for mod in consultar("SELECT id, titulo, nivel FROM modulos ORDER BY id"):
            mid, tit, niv = mod
            niv_label = {1: "Básico", 2: "Intermediário", 3: "Avançado"}.get(niv, "—")
            with st.expander(f"{icone_modulo(tit)} {tit} — Nível: {niv_label}"):
                for lic in consultar("SELECT titulo_botao, pergunta, resposta_correta FROM licoes WHERE modulo_id = ?", (mid,)):
                    st.markdown(f"- **{lic[0]}**: _{lic[1]}_ → `{lic[2]}`")

    with aba5:
        modulos_lista = consultar("SELECT id, titulo FROM modulos ORDER BY id")
        if not modulos_lista:
            st.info("Cadastre módulos primeiro.")
        else:
            with st.form("nova_licao"):
                mod_id = st.selectbox("Módulo", options=[m[0] for m in modulos_lista],
                                       format_func=lambda i: dict(modulos_lista)[i])
                titulo_botao = st.text_input("Título da fase (ex: Fase 9)")
                pergunta = st.text_input("Pergunta em português")
                correta = st.text_input("Resposta correta em inglês")
                e1 = st.text_input("Alternativa errada 1")
                e2 = st.text_input("Alternativa errada 2")
                e3 = st.text_input("Alternativa errada 3")
                explicacao = st.text_area("Explicação (opcional)", height=80)
                if st.form_submit_button("Adicionar lição"):
                    if all([titulo_botao, pergunta, correta, e1, e2, e3]):
                        executar("""INSERT INTO licoes (modulo_id, titulo_botao, pergunta,
                                    opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta, explicacao)
                                    VALUES (?,?,?,?,?,?,?,?,?)""",
                                 (mod_id, titulo_botao, pergunta, correta, e1, e2, e3, correta, explicacao))
                        st.success("Lição adicionada!")
                    else:
                        st.warning("Preencha todos os campos obrigatórios.")

        st.markdown("---")
        st.markdown("### Criar novo módulo")
        with st.form("novo_modulo"):
            novo_tit = st.text_input("Título do módulo (ex: Módulo 23: Verbos no Passado)")
            novo_niv = st.selectbox("Nível", [1, 2, 3], format_func=lambda x: {1:"Básico", 2:"Intermediário", 3:"Avançado"}[x])
            if st.form_submit_button("Criar módulo"):
                if novo_tit:
                    existe = consultar_um("SELECT 1 FROM modulos WHERE titulo = ?", (novo_tit,))
                    if existe:
                        st.error("Já existe módulo com esse título.")
                    else:
                        executar("INSERT INTO modulos (titulo, nivel) VALUES (?, ?)", (novo_tit, novo_niv))
                        st.success("Módulo criado! Adicione lições na aba acima.")

# =========================================================
# TELA: INÍCIO / MAPA DE MÓDULOS
# =========================================================
elif st.session_state.tela == "inicio":
    uid = st.session_state.uid
    aluno_info = consultar_um("SELECT xp_total, streak, melhor_streak FROM alunos WHERE id = ?", (uid,))
    xp_a, streak_a, melhor_a = aluno_info if aluno_info else (0, 0, 0)
    licoes_done = consultar_um("SELECT COUNT(*) FROM progresso WHERE aluno_id = ?", (uid,))[0]
    badges_qtd = consultar_um("SELECT COUNT(*) FROM conquistas WHERE aluno_id = ?", (uid,))[0]

    # Header com stats
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:14px;margin-bottom:18px;'>"
        f"{render_avatar(st.session_state.aluno, 52)}"
        f"<div><h3 style='margin:0;'>Bem-vindo, {st.session_state.aluno}</h3>"
        f"<span class='subtitulo'>Pronto pra mais uma lição?</span></div></div>",
        unsafe_allow_html=True
    )
    sa, sb, sc, sd = st.columns(4)
    with sa: st.markdown(f"<div class='stat-box'><div class='stat-num'>{xp_a}</div><div class='stat-label'>XP</div></div>", unsafe_allow_html=True)
    with sb: st.markdown(f"<div class='stat-box'><div class='stat-num'>🔥 {streak_a or 0}</div><div class='stat-label'>Streak (dias)</div></div>", unsafe_allow_html=True)
    with sc: st.markdown(f"<div class='stat-box'><div class='stat-num'>{licoes_done}</div><div class='stat-label'>Lições</div></div>", unsafe_allow_html=True)
    with sd: st.markdown(f"<div class='stat-box'><div class='stat-num'>🏅 {badges_qtd}</div><div class='stat-label'>Conquistas</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Notificação de desafios pendentes
    pendentes_qtd = len(duelos_pendentes_para_responder(uid))
    if pendentes_qtd > 0:
        st.markdown(f"<div style='background:#3A1B1B;border-left:4px solid #F87171;padding:14px;border-radius:8px;margin-bottom:14px;'><b>🥊 Você foi desafiado!</b> Você tem <b>{pendentes_qtd}</b> duelo(s) esperando sua resposta.</div>", unsafe_allow_html=True)

    # Notificação de partidas de torneio
    partidas_torneio = partidas_pendentes_do_aluno(uid)
    if partidas_torneio:
        for pt in partidas_torneio:
            partida_id, t_nome, t_id, rodada, j1, j2, j1_n, j2_n = pt
            oponente = j2_n if j1 == uid else j1_n
            st.markdown(f"<div style='background:#3A2D1B;border-left:4px solid #FFC97C;padding:14px;border-radius:8px;margin-bottom:14px;'><b>🏆 Torneio \"{t_nome}\" — Rodada {rodada}</b><br>Sua próxima partida é contra <b>{oponente}</b>. Vá no menu de Torneios para jogar.</div>", unsafe_allow_html=True)

    # Desafio Diário - destaque do dia
    desafio_lic_id, desafio_feito = obter_ou_gerar_desafio_diario(uid)
    if desafio_lic_id:
        if desafio_feito:
            st.markdown(
                f"<div style='background:linear-gradient(135deg, rgba(16,185,129,0.12), rgba(252,211,77,0.06));"
                f"border:1px solid var(--primary);border-radius:14px;padding:16px 20px;margin-bottom:16px;"
                f"display:flex;align-items:center;gap:14px;'>"
                f"<div style='font-size:1.8rem;'>✅</div>"
                f"<div style='flex:1;'>"
                f"<b style='color:var(--primary-light);'>Desafio diário completo!</b><br>"
                f"<small style='color:var(--text-dim);'>Volte amanhã pra um novo desafio.</small>"
                f"</div></div>",
                unsafe_allow_html=True
            )
        else:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(
                    f"<div style='background:linear-gradient(135deg, rgba(245,158,11,0.15), rgba(252,211,77,0.05));"
                    f"border:1px solid rgba(245,158,11,0.4);border-radius:14px;padding:16px 20px;"
                    f"display:flex;align-items:center;gap:14px;'>"
                    f"<div style='font-size:1.8rem;'>🎁</div>"
                    f"<div style='flex:1;'>"
                    f"<b style='color:var(--gold);'>Desafio Diário</b> · <span style='color:var(--text-dim);font-size:0.9rem;'>+{DESAFIO_XP_BONUS} XP bônus</span><br>"
                    f"<small style='color:var(--text-dim);'>Uma pergunta especial hoje. Aceita?</small>"
                    f"</div></div>",
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("🎯 Fazer", key="btn_desafio_diario", use_container_width=True):
                    q = consultar_um(
                        "SELECT id, pergunta, opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta, explicacao FROM licoes WHERE id = ?",
                        (desafio_lic_id,)
                    )
                    if q:
                        st.session_state.trilha = [q]
                        st.session_state.idx = 0
                        st.session_state.vidas = 3
                        st.session_state.respondido = False
                        st.session_state.opcoes_atuais = []
                        st.session_state.modo_revisao = False
                        st.session_state.modo_desafio_diario = True
                        st.session_state.tela = "licao"
                        st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("---")

    c_main, c_rank = st.columns([3, 1])
    with c_main:
        modulos = consultar("SELECT id, titulo, nivel FROM modulos ORDER BY id")
        for mid, mod_tit, nivel in modulos:
            niv_label = {1: ("Básico", "nivel-1"), 2: ("Intermediário", "nivel-2"), 3: ("Avançado", "nivel-3")}.get(nivel, ("—", "nivel-1"))
            licoes_mod = consultar("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ? ORDER BY id", (mid,))
            total = len(licoes_mod)
            feitas = consultar_um("""SELECT COUNT(*) FROM progresso p
                                     JOIN licoes l ON l.id = p.licao_id
                                     WHERE l.modulo_id = ? AND p.aluno_id = ?""", (mid, uid))[0]
            pct = int(100 * feitas / total) if total else 0
            label_expander = f"{icone_modulo(mod_tit)}  {mod_tit}  —  {feitas}/{total} ({pct}%)"

            with st.expander(label_expander):
                st.markdown(f"<span class='tag-nivel {niv_label[1]}'>{niv_label[0]}</span>", unsafe_allow_html=True)
                if not licoes_mod:
                    st.caption("Sem lições neste módulo ainda.")
                    continue
                num_cols = min(len(licoes_mod), 5)
                cols = st.columns(num_cols)
                for i, lic in enumerate(licoes_mod):
                    if i > 0:
                        passou_ant = consultar_um("SELECT 1 FROM progresso WHERE aluno_id = ? AND licao_id = ?",
                                                  (uid, licoes_mod[i-1][0]))
                    else:
                        passou_ant = True
                    ja_fez = consultar_um("SELECT 1 FROM progresso WHERE aluno_id = ? AND licao_id = ?",
                                          (uid, lic[0]))
                    with cols[i % num_cols]:
                        if ja_fez:
                            # botão de refazer ao lado do check
                            if st.button(f"✅ {lic[1]} 🔄", key=f"redo_{lic[0]}", help="Refazer esta lição"):
                                st.session_state.trilha = consultar(
                                    "SELECT id, pergunta, opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta, explicacao FROM licoes WHERE modulo_id = ? ORDER BY id", (mid,))
                                st.session_state.idx = i
                                st.session_state.vidas = 3
                                st.session_state.respondido = False
                                st.session_state.opcoes_atuais = []
                                st.session_state.erros_na_licao = 0
                                st.session_state.modo_revisao = False
                                st.session_state.tela = "licao"; st.rerun()
                        elif i > 0 and not passou_ant:
                            st.button(f"🔒 {lic[1]}", key=f"lock_{lic[0]}", disabled=True)
                        else:
                            if st.button(f"🎯 {lic[1]}", key=f"go_{lic[0]}"):
                                st.session_state.trilha = consultar(
                                    "SELECT id, pergunta, opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta, explicacao FROM licoes WHERE modulo_id = ? ORDER BY id", (mid,))
                                st.session_state.idx = i
                                st.session_state.vidas = 3
                                st.session_state.respondido = False
                                st.session_state.opcoes_atuais = []
                                st.session_state.erros_na_licao = 0
                                st.session_state.modo_revisao = False
                                st.session_state.tela = "licao"; st.rerun()
    with c_rank:
        exibir_ranking()

# =========================================================
# TELA: CONQUISTAS
# =========================================================
elif st.session_state.tela == "conquistas":
    uid = st.session_state.uid
    if st.button("⬅️ Voltar"):
        reset_para_inicio(); st.rerun()
    st.markdown("## 🏅 Minhas Conquistas")
    obtidas = {r[0] for r in consultar("SELECT badge_id FROM conquistas WHERE aluno_id = ?", (uid,))}
    cols = st.columns(3)
    for i, (bid, (icone, nome, desc)) in enumerate(BADGES.items()):
        with cols[i % 3]:
            cls = "badge-card" if bid in obtidas else "badge-card badge-locked"
            status = "✅ Conquistada" if bid in obtidas else "🔒 Bloqueada"
            st.markdown(f"<div class='{cls}'><div style='font-size:2rem'>{icone}</div><b>{nome}</b><br><small style='color:var(--text-muted);'>{desc}</small><br><small>{status}</small></div>", unsafe_allow_html=True)

# =========================================================
# TELA: LIÇÃO
# =========================================================
elif st.session_state.tela == "licao":
    trilha = st.session_state.trilha
    idx = st.session_state.idx
    # Cada item: id, pergunta, o1, o2, o3, o4, correta, explicacao
    lic_id, pergunta, o1, o2, o3, o4, correta, explicacao = trilha[idx]

    # Tipo de exercício
    # Aulas normais e revisão: rotaciona MC, LISTEN, TYPE para variedade (audio e escrita).
    # Desafio diário: só MC pra ser rápido (1 pergunta só).
    # Módulos audio_puro: TODAS as questões em modo Listen
    eh_audio_puro = False
    if not st.session_state.modo_revisao and not st.session_state.get("modo_desafio_diario"):
        # Detecta se a lição atual pertence a um módulo audio_puro
        mod_info = consultar_um(
            "SELECT m.audio_puro FROM licoes l JOIN modulos m ON m.id = l.modulo_id WHERE l.id = ?",
            (lic_id,)
        )
        if mod_info and mod_info[0]:
            eh_audio_puro = True

    if eh_audio_puro:
        tipo = "listen"
    elif st.session_state.get("modo_desafio_diario"):
        tipo = "mc"
    elif st.session_state.modo_revisao:
        tipo = ["mc", "listen", "type"][idx % 3]
    else:
        # Padrão: 2 MC, 1 Listen, 1 MC, 1 Type ... pra dosar variedade
        tipo = ["mc", "listen", "mc", "type"][idx % 4]

    # Header
    c_sair, c_prog, c_crono = st.columns([1, 3, 1])
    with c_sair:
        if st.button("⬅️ Menu"):
            reset_para_inicio(); st.rerun()
    with c_prog:
        st.progress((idx + 1) / len(trilha))
        if st.session_state.get("modo_desafio_diario"):
            modo_label = "🎁 Desafio Diário"
        elif st.session_state.modo_revisao:
            modo_label = "🧠 Revisão"
        else:
            modo_label = "📘 Aprendizado"
        st.write(f"{modo_label} — Fase {idx + 1} de {len(trilha)}")
    with c_crono:
        # Toggle do cronômetro (só fora de desafio diário/revisão)
        if not st.session_state.get("modo_desafio_diario"):
            crono_label = "⏱️ Cronômetro ON" if st.session_state.modo_cronometro else "⏱️ Cronômetro OFF"
            if st.button(crono_label, key=f"toggle_crono_{idx}", help="Bônus de XP por velocidade: <3s=+5, <6s=+3, <10s=+1"):
                st.session_state.modo_cronometro = not st.session_state.modo_cronometro
                st.rerun()

    # Inicia o cronômetro da questão atual (se ainda não foi iniciado)
    if not st.session_state.respondido and st.session_state.questao_iniciada_em is None:
        st.session_state.questao_iniciada_em = time.time()

    st.markdown(f"### Vidas: {'❤️' * st.session_state.vidas}")

    # Cronômetro visual (se ativo)
    if st.session_state.modo_cronometro and not st.session_state.respondido:
        st.components.v1.html(f"""
        <div id='crono' style='color:var(--primary);font-weight:700;font-size:1.4rem;
             font-family:Sora,sans-serif;text-align:center;
             background:rgba(16,185,129,0.08);padding:8px;border-radius:10px;
             border:1px solid rgba(16,185,129,0.3);margin-bottom:10px;'>⏱️ 0.0s</div>
        <script>
            (function(){{
                var t0 = Date.now();
                var el = document.getElementById('crono');
                var iv = setInterval(function(){{
                    var s = ((Date.now()-t0)/1000).toFixed(1);
                    el.textContent = '⏱️ ' + s + 's';
                    var sNum = parseFloat(s);
                    if (sNum < 3) el.style.color = '#FCD34D';
                    else if (sNum < 6) el.style.color = '#34D399';
                    else if (sNum < 10) el.style.color = '#94A3B8';
                    else el.style.color = '#94A3B8';
                }}, 100);
            }})();
        </script>
        """, height=60)

    if not st.session_state.opcoes_atuais:
        ops = [o1, o2, o3, o4]
        random.shuffle(ops)
        st.session_state.opcoes_atuais = ops

    if st.session_state.vidas <= 0:
        st.error("💔 Game Over! Você esgotou suas vidas.")
        if st.button("Voltar ao Menu"):
            reset_para_inicio(); st.rerun()
    else:
        # --- MC: múltipla escolha (PT → EN) ---
        if tipo == "mc":
            st.markdown(f"<div class='premium-card'><h3>Traduza:</h3><h2 style='color:var(--primary);'>{pergunta}</h2></div>", unsafe_allow_html=True)
            if not st.session_state.respondido:
                with st.form("form_mc"):
                    resp = st.radio("Escolha a opção em inglês:", st.session_state.opcoes_atuais, index=None)
                    enviou = st.form_submit_button("Validar")
                    if enviou:
                        if not resp:
                            st.warning("Selecione uma opção.")
                        else:
                            processar_resposta(resp, correta, lic_id, explicacao)
                            st.rerun()
            else:
                mostrar_feedback(correta, explicacao)
                botao_proxima(trilha, idx)

        # --- LISTEN: ouvir e escolher (audio EN → pick EN) ---
        elif tipo == "listen":
            st.markdown(f"<div class='premium-card'><h3>Ouça e escolha a opção correta:</h3></div>", unsafe_allow_html=True)
            botao_audio(correta, "🔊 Tocar áudio novamente")
            if not st.session_state.respondido:
                with st.form("form_listen"):
                    resp = st.radio("O que você ouviu?", st.session_state.opcoes_atuais, index=None)
                    enviou = st.form_submit_button("Validar")
                    if enviou:
                        if not resp:
                            st.warning("Selecione uma opção.")
                        else:
                            processar_resposta(resp, correta, lic_id, explicacao)
                            st.rerun()
            else:
                st.caption(f"Tradução: _{pergunta}_")
                mostrar_feedback(correta, explicacao)
                botao_proxima(trilha, idx)

        # --- TYPE: digite a tradução ---
        elif tipo == "type":
            st.markdown(f"<div class='premium-card'><h3>Digite em inglês:</h3><h2 style='color:var(--primary);'>{pergunta}</h2></div>", unsafe_allow_html=True)
            if not st.session_state.respondido:
                with st.form("form_type"):
                    resp = st.text_input("Sua resposta:", placeholder="Digite aqui...")
                    enviou = st.form_submit_button("Validar")
                    if enviou:
                        if not resp.strip():
                            st.warning("Digite uma resposta.")
                        else:
                            # Comparação tolerante: minúsculas, contrações expandidas, alternativas X / Y
                            acertou = acerto_typing(resp, correta)
                            processar_resposta(resp, correta, lic_id, explicacao, forcar=acertou)
                            st.rerun()
            else:
                mostrar_feedback(correta, explicacao)
                botao_proxima(trilha, idx)

# =========================================================
# TELA: DUELO - LOBBY
# =========================================================
elif st.session_state.tela == "duelo_lobby":
    uid = st.session_state.uid
    if st.button("⬅️ Voltar ao menu"):
        reset_para_inicio(); st.rerun()

    st.markdown("## 🥊 Arena de Duelos")
    stats = consultar_um("SELECT vitorias_duelo, derrotas_duelo, empates_duelo FROM alunos WHERE id = ?", (uid,))
    v, d, e = (stats[0] or 0, stats[1] or 0, stats[2] or 0) if stats else (0,0,0)
    total = v + d + e
    aproveit = f"{int(100*v/total)}%" if total else "—"
    s1, s2, s3, s4 = st.columns(4)
    with s1: st.markdown(f"<div class='stat-box'><div class='stat-num'>🏆 {v}</div><div class='stat-label'>Vitórias</div></div>", unsafe_allow_html=True)
    with s2: st.markdown(f"<div class='stat-box'><div class='stat-num'>💀 {d}</div><div class='stat-label'>Derrotas</div></div>", unsafe_allow_html=True)
    with s3: st.markdown(f"<div class='stat-box'><div class='stat-num'>🤝 {e}</div><div class='stat-label'>Empates</div></div>", unsafe_allow_html=True)
    with s4: st.markdown(f"<div class='stat-box'><div class='stat-num'>{aproveit}</div><div class='stat-label'>Aproveitamento</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("⚔️ Criar Novo Duelo", use_container_width=True):
        st.session_state.tela = "duelo_criar"; st.rerun()

    st.markdown("---")

    # Desafios pendentes (para responder)
    st.markdown("### 🔴 Desafios para você responder")
    pendentes = duelos_pendentes_para_responder(uid)
    if not pendentes:
        st.caption("Ninguém te desafiou ainda. Calmaria antes da tempestade.")
    meu_xp = consultar_um("SELECT xp_total FROM alunos WHERE id = ?", (uid,))[0]
    for d_id, oponente, score_op, criado in pendentes:
        duelo_info = carregar_duelo(d_id)
        aposta = duelo_info[10] if duelo_info else None
        c1, c2 = st.columns([4, 1])
        with c1:
            aposta_txt = f" — 💰 Aposta: <b>{aposta} XP</b>" if aposta else ""
            st.markdown(f"<div class='ranking-box' style='border-left-color:var(--danger);display:flex;align-items:center;gap:12px;'>{render_avatar(oponente, 40)}<div style='flex:1;'><b>{oponente}</b> te desafiou! Acertou <b>{score_op}/{DUELO_QUESTOES}</b>.{aposta_txt}<br><small style='color:var(--text-muted);'>{criado}</small></div></div>", unsafe_allow_html=True)
        with c2:
            pode_aceitar = (not aposta) or (meu_xp >= aposta)
            if not pode_aceitar:
                st.button(f"❌ Sem XP", key=f"semxp_{d_id}", use_container_width=True, disabled=True,
                          help=f"Você precisa de {aposta} XP para aceitar essa aposta.")
            else:
                if st.button("Aceitar ⚔️", key=f"aceitar_{d_id}", use_container_width=True):
                    duelo = carregar_duelo(d_id)
                    ids = json.loads(duelo[3])
                    # Se tem aposta, debita XP do desafiado agora
                    if aposta:
                        executar("UPDATE alunos SET xp_total = xp_total - ? WHERE id = ?", (aposta, uid))
                    st.session_state.duelo_id = d_id
                    st.session_state.duelo_modo = "desafiado"
                    st.session_state.duelo_questoes = carregar_questoes(ids)
                    st.session_state.duelo_idx = 0
                    st.session_state.duelo_score = 0
                    st.session_state.respondido = False
                    st.session_state.opcoes_atuais = []
                    st.session_state.duelo_iniciado_em = time.time()
                    st.session_state.duelo_aposta = aposta
                    st.session_state.duelo_torneio_partida_id = duelo[13]  # se for partida de torneio
                    st.session_state.tela = "duelo_jogando"
                    st.rerun()

    # Enviados aguardando
    st.markdown("### 🟡 Aguardando resposta")
    enviados = duelos_enviados_aguardando(uid)
    if not enviados:
        st.caption("Nenhum duelo seu está esperando resposta.")
    for d_id, oponente, meu_score, criado in enviados:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"<div class='ranking-box' style='border-left-color:var(--accent);display:flex;align-items:center;gap:12px;'>{render_avatar(oponente, 40)}<div style='flex:1;'>Aguardando <b>{oponente}</b>... Você acertou <b>{meu_score}/{DUELO_QUESTOES}</b>.<br><small style='color:var(--text-muted);'>{criado}</small></div></div>", unsafe_allow_html=True)
        with c2:
            if st.button("Cancelar", key=f"cancelar_{d_id}", use_container_width=True):
                if cancelar_duelo(d_id, uid):
                    st.success("Duelo cancelado.")
                    st.rerun()

    # Histórico
    st.markdown("### 📜 Últimos duelos finalizados")
    hist = duelos_finalizados(uid, limite=10)
    if not hist:
        st.caption("Nenhum duelo finalizado ainda.")
    for d_id, oponente, meu_score, score_op, vencedor_id, quando in hist:
        if vencedor_id is None:
            emoji, cor, status = "🤝", "#FFC97C", "Empate"
        elif vencedor_id == uid:
            emoji, cor, status = "🏆", "#10B981", "Vitória"
        else:
            emoji, cor, status = "💀", "#F87171", "Derrota"
        st.markdown(f"<div class='ranking-box' style='border-left-color:{cor};'>{emoji} <b>{status}</b> contra <b>{oponente}</b> — {meu_score} x {score_op}<br><small style='color:var(--text-muted);'>{quando}</small></div>", unsafe_allow_html=True)

    # Ranking de duelistas
    st.markdown("---")
    st.markdown("### 🏆 Ranking de Duelistas")
    duelistas = consultar("""
        SELECT nome, vitorias_duelo, derrotas_duelo, empates_duelo
        FROM alunos WHERE nome != ? AND (vitorias_duelo > 0 OR derrotas_duelo > 0 OR empates_duelo > 0)
        ORDER BY vitorias_duelo DESC, derrotas_duelo ASC
        LIMIT 10
    """, (PROFESSOR_NOME,))
    if not duelistas:
        st.caption("Ninguém duelou ainda. Seja o primeiro!")
    for nome_d, v_d, d_d, e_d in duelistas:
        st.markdown(f"<div class='ranking-box' style='display:flex;align-items:center;gap:12px;'>{render_avatar(nome_d, 36)}<div style='flex:1;'><b>{nome_d}</b> &nbsp;|&nbsp; 🏆 {v_d} &nbsp;|&nbsp; 💀 {d_d} &nbsp;|&nbsp; 🤝 {e_d}</div></div>", unsafe_allow_html=True)

# =========================================================
# TELA: DUELO - CRIAR
# =========================================================
elif st.session_state.tela == "duelo_criar":
    uid = st.session_state.uid
    if st.button("⬅️ Voltar"):
        st.session_state.tela = "duelo_lobby"; st.rerun()

    st.markdown("## ⚔️ Criar Novo Duelo")

    # Verifica limite de duelos pendentes
    qtd_pendentes_enviados = len(duelos_enviados_aguardando(uid))
    if qtd_pendentes_enviados >= DUELO_MAX_PENDENTES:
        st.error(f"Você já tem {DUELO_MAX_PENDENTES} duelos esperando resposta. Espere algum terminar ou cancele um antes de criar novo.")
    else:
        oponentes = consultar(
            "SELECT id, nome FROM alunos WHERE id != ? AND nome != ? ORDER BY nome",
            (uid, PROFESSOR_NOME)
        )
        if not oponentes:
            st.warning("Ainda não há outros alunos cadastrados pra desafiar. Chame um amigo!")
        else:
            with st.form("form_duelo"):
                oponente_id = st.selectbox(
                    "Escolha seu oponente:",
                    options=[o[0] for o in oponentes],
                    format_func=lambda i: dict(oponentes)[i]
                )
                nivel = st.select_slider(
                    "Dificuldade:",
                    options=[1, 2, 3],
                    value=2,
                    format_func=lambda x: {1: "🟢 Fácil (básico)", 2: "🟡 Médio (básico + intermediário)", 3: "🔴 Difícil (tudo)"}[x]
                )

                # Aposta de XP
                meu_xp = consultar_um("SELECT xp_total FROM alunos WHERE id = ?", (uid,))[0]
                max_aposta_aluno = min(DUELO_APOSTA_MAX, meu_xp)
                if max_aposta_aluno >= DUELO_APOSTA_MIN:
                    quer_apostar = st.checkbox("💰 Apostar XP neste duelo")
                    if quer_apostar:
                        aposta = st.slider(
                            f"Quanto apostar? (você tem {meu_xp} XP)",
                            min_value=DUELO_APOSTA_MIN,
                            max_value=max_aposta_aluno,
                            value=DUELO_APOSTA_MIN, step=10
                        )
                        st.caption(f"⚠️ Os {aposta} XP serão descontados de você agora. Se vencer, leva o dobro ({2*aposta}). Se perder, perdeu tudo. Empate: cada um recebe o seu de volta.")
                    else:
                        aposta = None
                else:
                    st.caption(f"💡 Você precisa de pelo menos {DUELO_APOSTA_MIN} XP pra apostar.")
                    aposta = None

                st.caption(f"⚔️ Serão {DUELO_QUESTOES} questões aleatórias. Você joga primeiro, depois o oponente. Vencedor leva {DUELO_XP_VITORIA} XP, perdedor {DUELO_XP_DERROTA}, empate {DUELO_XP_EMPATE} cada (sem aposta).")
                iniciar = st.form_submit_button("⚔️ INICIAR DUELO", use_container_width=True)
                if iniciar:
                    ids = gerar_questoes_duelo(nivel_max=nivel, n=DUELO_QUESTOES)
                    if len(ids) < DUELO_QUESTOES:
                        st.error(f"Não há questões suficientes nesse nível. Tente nível maior.")
                    else:
                        st.session_state.duelo_id = None  # ainda não criado no DB
                        st.session_state.duelo_modo = "desafiante"
                        st.session_state.duelo_questoes = carregar_questoes(ids)
                        st.session_state.duelo_oponente_id = oponente_id
                        st.session_state.duelo_idx = 0
                        st.session_state.duelo_score = 0
                        st.session_state.respondido = False
                        st.session_state.opcoes_atuais = []
                        st.session_state.duelo_iniciado_em = time.time()
                        st.session_state.duelo_aposta = aposta
                        st.session_state.duelo_torneio_partida_id = None
                        st.session_state.tela = "duelo_jogando"
                        st.rerun()

# =========================================================
# TELA: DUELO - JOGANDO
# =========================================================
elif st.session_state.tela == "duelo_jogando":
    uid = st.session_state.uid
    questoes = st.session_state.duelo_questoes
    idx = st.session_state.duelo_idx
    if idx >= len(questoes):
        # Acabou o duelo. Calcular tempo total.
        tempo_total = time.time() - st.session_state.duelo_iniciado_em if st.session_state.duelo_iniciado_em else None
        if st.session_state.duelo_modo == "desafiante":
            duelo_id = criar_duelo(
                uid,
                st.session_state.duelo_oponente_id,
                [q[0] for q in questoes],
                st.session_state.duelo_score,
                xp_apostado=st.session_state.duelo_aposta,
                tempo_desafiante=tempo_total,
                torneio_partida_id=st.session_state.duelo_torneio_partida_id
            )
            st.session_state.duelo_id = duelo_id
            # Se for partida de torneio, registra o duelo na partida
            if st.session_state.duelo_torneio_partida_id:
                executar("UPDATE torneio_partidas SET duelo_id = ? WHERE id = ?",
                         (duelo_id, st.session_state.duelo_torneio_partida_id))
        else:
            finalizar_duelo(st.session_state.duelo_id, st.session_state.duelo_score,
                            tempo_desafiado=tempo_total)
            verificar_conquistas(uid)
        st.session_state.tela = "duelo_resultado"
        st.rerun()
    else:
        q = questoes[idx]
        lic_id, pergunta, o1, o2, o3, o4, correta, explicacao = q

        c_sair, c_prog, c_timer = st.columns([1, 3, 1])
        with c_sair:
            modo_emoji = "⚔️" if st.session_state.duelo_modo == "desafiante" else "🛡️"
            torneio_tag = " 🏆" if st.session_state.duelo_torneio_partida_id else ""
            st.markdown(f"### {modo_emoji}{torneio_tag} Duelo")
        with c_prog:
            st.progress((idx + 1) / len(questoes))
            placar_extra = ""
            if st.session_state.duelo_aposta:
                placar_extra = f" — 💰 {st.session_state.duelo_aposta} XP em jogo"
            st.write(f"Questão {idx + 1} de {len(questoes)} — Acertos: {st.session_state.duelo_score}{placar_extra}")
        with c_timer:
            # Cronômetro JS decorativo (zera a cada questão visualmente)
            st.components.v1.html(f"""
            <div id='timer' style='color:var(--primary);font-weight:bold;font-size:1.3rem;text-align:right;'>⏱️ 0s</div>
            <script>
                (function(){{
                    var t0 = Date.now();
                    var el = document.getElementById('timer');
                    var ref = {DUELO_TEMPO_REFERENCIA_SEG};
                    var iv = setInterval(function(){{
                        var s = Math.floor((Date.now()-t0)/1000);
                        el.textContent = '⏱️ ' + s + 's';
                        el.style.color = s > ref ? '#F87171' : (s > ref*0.7 ? '#FFC97C' : '#10B981');
                    }}, 250);
                }})();
            </script>
            """, height=40)

        # Se for desafiado, mostra score a bater
        if st.session_state.duelo_modo == "desafiado":
            duelo = carregar_duelo(st.session_state.duelo_id)
            if duelo:
                score_oponente = duelo[4]
                falta = max(0, score_oponente - st.session_state.duelo_score + 1)
                if falta > 0:
                    rest = len(questoes) - idx
                    st.markdown(f"<div style='background:#1B2A3A;border-left:4px solid #4FC3F7;padding:10px;border-radius:6px;margin-bottom:10px;'>🎯 Oponente fez <b>{score_oponente}</b>. Você precisa de mais <b>{falta}</b> acerto(s) em <b>{rest}</b> questão(ões) restantes.</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='background:#1B3A1B;border-left:3px solid var(--primary);padding:10px;border-radius:6px;margin-bottom:10px;'>🔥 Você já garantiu pelo menos o empate!</div>", unsafe_allow_html=True)

        if not st.session_state.opcoes_atuais:
            ops = [o1, o2, o3, o4]
            random.shuffle(ops)
            st.session_state.opcoes_atuais = ops

        st.markdown(f"<div class='premium-card'><h3>Traduza:</h3><h2 style='color:var(--primary);'>{pergunta}</h2></div>", unsafe_allow_html=True)

        if not st.session_state.respondido:
            with st.form(f"form_duelo_q{idx}"):
                resp = st.radio("Escolha:", st.session_state.opcoes_atuais, index=None)
                enviou = st.form_submit_button("Validar")
                if enviou:
                    if not resp:
                        st.warning("Selecione uma opção.")
                    else:
                        if resp == correta:
                            st.session_state.duelo_score += 1
                            st.session_state.feedback = "✅ Correto!"
                        else:
                            st.session_state.feedback = f"❌ Errado. Correta: **{correta}**"
                        st.session_state.respondido = True
                        st.rerun()
        else:
            st.markdown(st.session_state.feedback)
            botao_audio(correta, "🔊 Ouvir")
            if st.button("Próxima ➡️"):
                st.session_state.duelo_idx += 1
                st.session_state.respondido = False
                st.session_state.opcoes_atuais = []
                st.rerun()

# =========================================================
# TELA: DUELO - RESULTADO
# =========================================================
elif st.session_state.tela == "duelo_resultado":
    uid = st.session_state.uid
    duelo = carregar_duelo(st.session_state.duelo_id)
    if not duelo:
        st.error("Duelo não encontrado.")
        if st.button("Voltar"):
            reset_para_inicio(); st.rerun()
    else:
        (d_id, des_id, dou_id, q_ids, sc_des, sc_dou, vencedor, status, criado, atualizado,
         xp_apostado, tempo_des, tempo_dou, torneio_partida_id) = duelo
        nome_des = consultar_um("SELECT nome FROM alunos WHERE id = ?", (des_id,))[0]
        nome_dou = consultar_um("SELECT nome FROM alunos WHERE id = ?", (dou_id,))[0]

        if status == "aguardando_desafiado":
            # Desafiante acabou de jogar, mas o outro ainda não respondeu
            tempo_txt = f"<p>⏱️ Seu tempo: <b>{tempo_des:.0f}s</b></p>" if tempo_des else ""
            aposta_txt = f"<p>💰 Aposta: <b>{xp_apostado} XP</b> (já descontados de você)</p>" if xp_apostado else ""
            st.markdown(f"""
            <div class='premium-card' style='text-align:center;'>
                <h1>⚔️ Desafio enviado!</h1>
                <h2 style='color:var(--primary);'>{sc_des}/{len(json.loads(q_ids))}</h2>
                {tempo_txt}
                {aposta_txt}
                <p>Agora é só esperar <b>{nome_dou}</b> aceitar e responder.</p>
                <p>Você ganha XP só depois que ele jogar.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Finalizado
            if vencedor is None:
                emoji, titulo, cor = "🤝", "EMPATE!", "#FFC97C"
                if xp_apostado:
                    msg = f"Empate com <b>{sc_des}</b> acertos cada. Cada um recebeu seus {xp_apostado} XP de volta."
                else:
                    msg = f"Vocês empataram com <b>{sc_des}</b> acertos cada. +{DUELO_XP_EMPATE} XP."
            elif vencedor == uid:
                emoji, titulo, cor = "🏆", "VITÓRIA!", "#10B981"
                meu = sc_des if uid == des_id else sc_dou
                op = sc_dou if uid == des_id else sc_des
                op_nome = nome_dou if uid == des_id else nome_des
                if xp_apostado:
                    msg = f"Você venceu <b>{op_nome}</b> por <b>{meu} a {op}</b>! 💰 Você leva {2*xp_apostado} XP da aposta."
                else:
                    msg = f"Você venceu <b>{op_nome}</b> por <b>{meu} a {op}</b>! +{DUELO_XP_VITORIA} XP"
            else:
                emoji, titulo, cor = "💀", "DERROTA", "#F87171"
                meu = sc_des if uid == des_id else sc_dou
                op = sc_dou if uid == des_id else sc_des
                op_nome = nome_dou if uid == des_id else nome_des
                if xp_apostado:
                    msg = f"<b>{op_nome}</b> venceu por <b>{op} a {meu}</b>. 💸 Você perdeu os {xp_apostado} XP apostados."
                else:
                    msg = f"<b>{op_nome}</b> venceu por <b>{op} a {meu}</b>. +{DUELO_XP_DERROTA} XP de consolação."

            tempo_extra = ""
            if tempo_des and tempo_dou:
                tempo_extra = f"<p style='color:var(--text-dim);'>⏱️ Tempo: <b>{nome_des}</b> {tempo_des:.0f}s &nbsp;×&nbsp; {tempo_dou:.0f}s <b>{nome_dou}</b></p>"
                if sc_des == sc_dou and vencedor:  # houve desempate por tempo
                    tempo_extra += "<p style='color:#FFC97C;'>⚡ Desempate por tempo!</p>"

            st.markdown(f"""
            <div class='premium-card' style='text-align:center;border-color:{cor};'>
                <div style='font-size:4rem'>{emoji}</div>
                <h1 style='color:{cor};'>{titulo}</h1>
                <p style='font-size:1.1rem;'>{msg}</p>
                <p style='color:var(--text-dim);'><b>{nome_des}</b> {sc_des} &nbsp;×&nbsp; {sc_dou} <b>{nome_dou}</b></p>
                {tempo_extra}
            </div>
            """, unsafe_allow_html=True)

            verificar_conquistas(uid)

        # Botões de ação
        if status == "finalizado" and not torneio_partida_id:
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🔄 Revanche!", use_container_width=True):
                    # Cria um novo duelo contra o mesmo oponente, mesmo nível, sem aposta
                    oponente_id = dou_id if uid == des_id else des_id
                    qtd_pend = len(duelos_enviados_aguardando(uid))
                    if qtd_pend >= DUELO_MAX_PENDENTES:
                        st.warning(f"Você já tem {DUELO_MAX_PENDENTES} duelos pendentes. Espere algum terminar.")
                    else:
                        # Detectar nível pelos questões originais
                        ids_originais = json.loads(q_ids)
                        nivel_max = consultar_um("""
                            SELECT MAX(m.nivel) FROM modulos m
                            JOIN licoes l ON l.modulo_id = m.id
                            WHERE l.id IN ({})
                        """.format(",".join("?" * len(ids_originais))), ids_originais)[0] or 2
                        novos_ids = gerar_questoes_duelo(nivel_max=nivel_max, n=DUELO_QUESTOES)
                        st.session_state.duelo_id = None
                        st.session_state.duelo_modo = "desafiante"
                        st.session_state.duelo_questoes = carregar_questoes(novos_ids)
                        st.session_state.duelo_oponente_id = oponente_id
                        st.session_state.duelo_idx = 0
                        st.session_state.duelo_score = 0
                        st.session_state.respondido = False
                        st.session_state.opcoes_atuais = []
                        st.session_state.duelo_iniciado_em = time.time()
                        st.session_state.duelo_aposta = None
                        st.session_state.duelo_torneio_partida_id = None
                        st.session_state.tela = "duelo_jogando"
                        st.rerun()
            with c2:
                if st.button("🥊 Voltar ao Lobby", use_container_width=True):
                    st.session_state.tela = "duelo_lobby"
                    st.session_state.duelo_id = None
                    st.rerun()
            with c3:
                if st.button("🏠 Menu Principal", use_container_width=True):
                    reset_para_inicio(); st.rerun()
        else:
            c1, c2 = st.columns(2)
            with c1:
                if torneio_partida_id:
                    if st.button("🏆 Voltar ao torneio", use_container_width=True):
                        # Encontra o torneio dessa partida
                        tp = consultar_um("SELECT torneio_id FROM torneio_partidas WHERE id = ?", (torneio_partida_id,))
                        if tp:
                            st.session_state.torneio_atual = tp[0]
                            st.session_state.tela = "torneio_detalhe"
                        else:
                            st.session_state.tela = "torneio_lista"
                        st.rerun()
                else:
                    if st.button("🥊 Voltar ao Lobby", use_container_width=True):
                        st.session_state.tela = "duelo_lobby"
                        st.session_state.duelo_id = None
                        st.rerun()
            with c2:
                if st.button("🏠 Menu Principal", use_container_width=True):
                    reset_para_inicio(); st.rerun()

# =========================================================
# TELA: TORNEIO - LISTA
# =========================================================
elif st.session_state.tela == "torneio_lista":
    uid = st.session_state.uid
    if st.button("⬅️ Voltar ao menu"):
        reset_para_inicio(); st.rerun()

    st.markdown("## 🏆 Torneios")

    # Partidas pendentes
    pendentes = partidas_pendentes_do_aluno(uid)
    if pendentes:
        st.markdown("### ⚔️ Suas partidas pendentes")
        for partida_id, t_nome, t_id, rodada, j1, j2, j1_n, j2_n in pendentes:
            oponente_id = j2 if j1 == uid else j1
            oponente = j2_n if j1 == uid else j1_n
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"<div class='ranking-box' style='border-left-color:#FFC97C;'><b>{t_nome}</b> — Rodada {rodada}<br>Sua próxima partida: contra <b>{oponente}</b></div>", unsafe_allow_html=True)
            with c2:
                if st.button("Jogar ⚔️", key=f"jog_t_{partida_id}", use_container_width=True):
                    t_info = consultar_um("SELECT nivel FROM torneios WHERE id = ?", (t_id,))
                    nivel = t_info[0] if t_info else 2
                    ids = gerar_questoes_duelo(nivel_max=nivel, n=DUELO_QUESTOES)
                    st.session_state.duelo_id = None
                    st.session_state.duelo_modo = "desafiante"
                    st.session_state.duelo_questoes = carregar_questoes(ids)
                    st.session_state.duelo_oponente_id = oponente_id
                    st.session_state.duelo_idx = 0
                    st.session_state.duelo_score = 0
                    st.session_state.respondido = False
                    st.session_state.opcoes_atuais = []
                    st.session_state.duelo_iniciado_em = time.time()
                    st.session_state.duelo_aposta = None
                    st.session_state.duelo_torneio_partida_id = partida_id
                    st.session_state.tela = "duelo_jogando"
                    st.rerun()
        st.markdown("---")

    if st.button("➕ Criar Novo Torneio", use_container_width=True):
        st.session_state.tela = "torneio_criar"; st.rerun()

    st.markdown("### 📋 Torneios")
    em_andamento = listar_torneios("em_andamento")
    finalizados = listar_torneios("finalizado")

    if em_andamento:
        st.markdown("#### Em andamento")
        for t in em_andamento:
            t_id, nome, nivel, tamanho, status, campeao_id, criado = t
            if st.button(f"📂 {nome} ({tamanho} jogadores, nível {nivel})", key=f"abrir_t_{t_id}", use_container_width=True):
                st.session_state.torneio_atual = t_id
                st.session_state.tela = "torneio_detalhe"
                st.rerun()
    if finalizados:
        st.markdown("#### Finalizados")
        for t in finalizados[:5]:
            t_id, nome, nivel, tamanho, status, campeao_id, criado = t
            campeao_nome = consultar_um("SELECT nome FROM alunos WHERE id = ?", (campeao_id,))
            cn = campeao_nome[0] if campeao_nome else "—"
            if st.button(f"🏆 {nome} — Campeão: {cn}", key=f"abrir_t_fin_{t_id}", use_container_width=True):
                st.session_state.torneio_atual = t_id
                st.session_state.tela = "torneio_detalhe"
                st.rerun()
    if not em_andamento and not finalizados:
        st.caption("Nenhum torneio ainda. Crie o primeiro!")

# =========================================================
# TELA: TORNEIO - CRIAR
# =========================================================
elif st.session_state.tela == "torneio_criar":
    uid = st.session_state.uid
    if st.button("⬅️ Voltar"):
        st.session_state.tela = "torneio_lista"; st.rerun()

    st.markdown("## ➕ Criar Novo Torneio")
    alunos_disp = consultar("SELECT id, nome FROM alunos WHERE nome != ? ORDER BY nome", (PROFESSOR_NOME,))
    if len(alunos_disp) < 4:
        st.warning("São necessários no mínimo 4 alunos cadastrados pra criar um torneio.")
    else:
        with st.form("form_torneio"):
            nome_t = st.text_input("Nome do torneio:", placeholder="Ex: Copa Bethany 2026")
            tamanho = st.radio("Tamanho:", [4, 8], horizontal=True,
                                format_func=lambda x: f"{x} jogadores ({'semifinal + final' if x==4 else 'quartas + semi + final'})")
            nivel = st.select_slider("Dificuldade:", options=[1, 2, 3], value=2,
                                      format_func=lambda x: {1:"🟢 Fácil",2:"🟡 Médio",3:"🔴 Difícil"}[x])
            participantes_ids = st.multiselect(
                f"Selecione exatamente {tamanho} participantes:",
                options=[a[0] for a in alunos_disp],
                format_func=lambda i: dict(alunos_disp)[i]
            )
            st.caption(f"🏆 Campeão: +{TORNEIO_XP_CAMPEAO} XP &nbsp;|&nbsp; Vice: +{TORNEIO_XP_FINALISTA} XP &nbsp;|&nbsp; Semifinalistas: +{TORNEIO_XP_SEMIFINALISTA} XP")
            criar = st.form_submit_button("🏆 Criar Torneio", use_container_width=True)
            if criar:
                if not nome_t.strip():
                    st.warning("Dê um nome ao torneio.")
                elif len(participantes_ids) != tamanho:
                    st.error(f"Selecione exatamente {tamanho} participantes (você selecionou {len(participantes_ids)}).")
                else:
                    t_id = criar_torneio(nome_t.strip(), nivel, participantes_ids)
                    if t_id:
                        st.success(f"Torneio criado! Bracket gerado.")
                        st.session_state.torneio_atual = t_id
                        st.session_state.tela = "torneio_detalhe"
                        st.rerun()
                    else:
                        st.error("Erro ao criar o torneio.")

# =========================================================
# TELA: TORNEIO - DETALHE (BRACKET)
# =========================================================
elif st.session_state.tela == "torneio_detalhe":
    uid = st.session_state.uid
    t_id = st.session_state.get("torneio_atual")
    if st.button("⬅️ Voltar aos torneios"):
        st.session_state.tela = "torneio_lista"; st.rerun()

    if not t_id:
        st.error("Torneio não selecionado.")
    else:
        t, partidas = estado_torneio(t_id)
        if not t:
            st.error("Torneio não encontrado.")
        else:
            tid, nome, nivel, tamanho, status, campeao_id, criado, finalizado = t
            niv_lbl = {1:"🟢 Fácil",2:"🟡 Médio",3:"🔴 Difícil"}[nivel]
            st.markdown(f"## 🏆 {nome}")
            st.caption(f"{tamanho} jogadores &nbsp;|&nbsp; {niv_lbl} &nbsp;|&nbsp; Status: {status}")

            if campeao_id:
                campeao_nome = consultar_um("SELECT nome FROM alunos WHERE id = ?", (campeao_id,))[0]
                st.markdown(f"<div class='premium-card' style='text-align:center;border-color:gold;'><div style='font-size:3rem;'>🏆</div><h2 style='color:gold;'>CAMPEÃO: {campeao_nome}</h2></div>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

            # Organiza partidas por rodada
            total_rodadas = 2 if tamanho == 4 else 3
            nomes_rodadas = {1: "1ª Rodada", 2: "Semifinal" if tamanho == 8 else "Final"}
            if tamanho == 8:
                nomes_rodadas = {1: "Quartas de final", 2: "Semifinal", 3: "Final"}
            else:
                nomes_rodadas = {1: "Semifinal", 2: "Final"}

            for r in range(1, total_rodadas + 1):
                st.markdown(f"### {nomes_rodadas[r]}")
                partidas_r = [p for p in partidas if p[1] == r]
                for p in partidas_r:
                    pid, rod, pos, j1, j2, venc, duelo_id, j1n, j2n, vn = p
                    j1n_disp = j1n or "TBD"
                    j2n_disp = j2n or "TBD"
                    if venc:
                        # Já terminou
                        st.markdown(f"<div class='ranking-box' style='border-left-color:var(--primary);'>"
                                    f"<b style='color:{'#10B981' if j1 == venc else '#888'};'>{j1n_disp}</b> vs "
                                    f"<b style='color:{'#10B981' if j2 == venc else '#888'};'>{j2n_disp}</b><br>"
                                    f"<small>Vencedor: <b style='color:var(--primary);'>{vn}</b></small>"
                                    f"</div>", unsafe_allow_html=True)
                    elif j1 and j2:
                        # Pronta pra jogar
                        if uid in (j1, j2):
                            c1, c2 = st.columns([4, 1])
                            with c1:
                                st.markdown(f"<div class='ranking-box' style='border-left-color:#FFC97C;'><b>{j1n_disp}</b> vs <b>{j2n_disp}</b> ⏳</div>", unsafe_allow_html=True)
                            with c2:
                                if st.button("Jogar ⚔️", key=f"play_t_{pid}", use_container_width=True):
                                    oponente_id = j2 if j1 == uid else j1
                                    if duelo_id:
                                        # Já existe duelo (o outro jogou primeiro): aceitar como desafiado
                                        dl = carregar_duelo(duelo_id)
                                        if dl:
                                            ids = json.loads(dl[3])
                                            st.session_state.duelo_id = duelo_id
                                            st.session_state.duelo_modo = "desafiado"
                                            st.session_state.duelo_questoes = carregar_questoes(ids)
                                            st.session_state.duelo_idx = 0
                                            st.session_state.duelo_score = 0
                                            st.session_state.respondido = False
                                            st.session_state.opcoes_atuais = []
                                            st.session_state.duelo_iniciado_em = time.time()
                                            st.session_state.duelo_aposta = None
                                            st.session_state.duelo_torneio_partida_id = pid
                                            st.session_state.tela = "duelo_jogando"
                                            st.rerun()
                                    else:
                                        # É o primeiro a jogar: cria duelo como desafiante
                                        ids = gerar_questoes_duelo(nivel_max=nivel, n=DUELO_QUESTOES)
                                        st.session_state.duelo_id = None
                                        st.session_state.duelo_modo = "desafiante"
                                        st.session_state.duelo_questoes = carregar_questoes(ids)
                                        st.session_state.duelo_oponente_id = oponente_id
                                        st.session_state.duelo_idx = 0
                                        st.session_state.duelo_score = 0
                                        st.session_state.respondido = False
                                        st.session_state.opcoes_atuais = []
                                        st.session_state.duelo_iniciado_em = time.time()
                                        st.session_state.duelo_aposta = None
                                        st.session_state.duelo_torneio_partida_id = pid
                                        st.session_state.tela = "duelo_jogando"
                                        st.rerun()
                        else:
                            # Alguma das duas partes pode ser o desafiado de um duelo já criado
                            if duelo_id:
                                dl = carregar_duelo(duelo_id)
                                if dl and dl[7] == 'aguardando_desafiado':
                                    st.markdown(f"<div class='ranking-box' style='border-left-color:#888;'><b>{j1n_disp}</b> vs <b>{j2n_disp}</b><br><small>Desafiante já jogou. Aguardando oponente.</small></div>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<div class='ranking-box' style='border-left-color:#888;'><b>{j1n_disp}</b> vs <b>{j2n_disp}</b> ⏳</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='ranking-box' style='border-left-color:#888;'><b>{j1n_disp}</b> vs <b>{j2n_disp}</b> ⏳</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='ranking-box' style='border-left-color:#444;'><i>Aguardando vencedores das partidas anteriores</i></div>", unsafe_allow_html=True)

# =========================================================
# TELA: PERFIL DO ALUNO
# =========================================================
elif st.session_state.tela == "perfil":
    perfil_id = st.session_state.get("perfil_id", st.session_state.uid)
    aluno = consultar_um("""
        SELECT id, nome, xp_total, streak, melhor_streak, ultimo_acesso, criado_em,
               vitorias_duelo, derrotas_duelo, empates_duelo,
               streak_vitorias_duelo, melhor_streak_vitorias_duelo
        FROM alunos WHERE id = ?
    """, (perfil_id,))
    if not aluno:
        st.error("Aluno não encontrado.")
        if st.button("⬅️ Voltar"):
            reset_para_inicio(); st.rerun()
    else:
        (pid, nome, xp, streak, melhor_streak, ult_acesso, criado,
         vit_d, der_d, emp_d, streak_v, melhor_streak_v) = aluno
        is_self = (pid == st.session_state.uid)

        # Header com avatar grande + nível
        nivel_idx, nivel_nome, xp_no_nivel, xp_proximo = info_nivel(xp)
        pct_nivel = int(100 * xp_no_nivel / xp_proximo) if xp_proximo else 100
        avatar_grande = render_avatar(nome, 88)

        st.markdown(
            f"<div class='premium-card' style='display:flex;align-items:center;gap:20px;'>"
            f"{avatar_grande}"
            f"<div style='flex:1;'>"
            f"<h1 style='margin:0 0 4px;font-family:Sora,sans-serif;'>{nome}</h1>"
            f"<div style='color:var(--text-dim);font-size:1.05rem;margin-bottom:10px;'>{nivel_nome}"
            + (f" &nbsp;·&nbsp; <span style='color:var(--accent);'>🔥 streak {streak or 0}</span>" if streak and streak > 0 else "")
            + f"</div>"
            f"<div style='background:var(--border);height:8px;border-radius:4px;overflow:hidden;'>"
            f"<div style='background:linear-gradient(90deg, var(--primary), var(--primary-light));height:100%;width:{pct_nivel}%;transition:width 0.6s;'></div></div>"
            f"<div style='font-size:0.8rem;color:var(--text-muted);margin-top:4px;'>{xp_no_nivel} / {xp_proximo} XP pro próximo nível</div>"
            f"</div></div>",
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Stats principais
        licoes_done = consultar_um("SELECT COUNT(*) FROM progresso WHERE aluno_id = ?", (pid,))[0]
        badges_qtd = consultar_um("SELECT COUNT(*) FROM conquistas WHERE aluno_id = ?", (pid,))[0]

        sa, sb, sc, sd = st.columns(4)
        with sa: st.markdown(f"<div class='stat-box'><div class='stat-num'>{xp}</div><div class='stat-label'>XP Total</div></div>", unsafe_allow_html=True)
        with sb: st.markdown(f"<div class='stat-box'><div class='stat-num'>🔥 {melhor_streak or 0}</div><div class='stat-label'>Melhor Streak</div></div>", unsafe_allow_html=True)
        with sc: st.markdown(f"<div class='stat-box'><div class='stat-num'>{licoes_done}</div><div class='stat-label'>Lições</div></div>", unsafe_allow_html=True)
        with sd: st.markdown(f"<div class='stat-box'><div class='stat-num'>🏅 {badges_qtd}</div><div class='stat-label'>Conquistas</div></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Stats de duelo
        st.markdown("### 🥊 Duelos")
        v_d, d_d, e_d = vit_d or 0, der_d or 0, emp_d or 0
        total_duelos = v_d + d_d + e_d
        aprov = f"{int(100*v_d/total_duelos)}%" if total_duelos else "—"
        d1, d2, d3, d4, d5 = st.columns(5)
        with d1: st.markdown(f"<div class='stat-box'><div class='stat-num'>🏆 {v_d}</div><div class='stat-label'>Vitórias</div></div>", unsafe_allow_html=True)
        with d2: st.markdown(f"<div class='stat-box'><div class='stat-num'>💀 {d_d}</div><div class='stat-label'>Derrotas</div></div>", unsafe_allow_html=True)
        with d3: st.markdown(f"<div class='stat-box'><div class='stat-num'>🤝 {e_d}</div><div class='stat-label'>Empates</div></div>", unsafe_allow_html=True)
        with d4: st.markdown(f"<div class='stat-box'><div class='stat-num'>{aprov}</div><div class='stat-label'>Aproveitamento</div></div>", unsafe_allow_html=True)
        with d5: st.markdown(f"<div class='stat-box'><div class='stat-num'>⚡ {melhor_streak_v or 0}</div><div class='stat-label'>Melhor Sequência</div></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Conquistas
        st.markdown("### 🏅 Conquistas")
        obtidas = {r[0] for r in consultar("SELECT badge_id FROM conquistas WHERE aluno_id = ?", (pid,))}
        cols = st.columns(4)
        for i, (bid, (icone, nm_b, desc)) in enumerate(BADGES.items()):
            with cols[i % 4]:
                cls = "badge-card" if bid in obtidas else "badge-card badge-locked"
                st.markdown(
                    f"<div class='{cls}'><div style='font-size:1.8rem'>{icone}</div>"
                    f"<b style='font-size:0.85rem;'>{nm_b}</b><br>"
                    f"<small style='color:var(--text-muted);font-size:0.7rem;'>{desc}</small></div>",
                    unsafe_allow_html=True
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Certificados de módulos completos
        st.markdown("### 📜 Meus Certificados")
        modulos_completos = modulos_completos_do_aluno(pid)
        if not modulos_completos:
            st.caption("Complete um módulo inteiro pra desbloquear seu primeiro certificado!")
        else:
            if not REPORTLAB_OK and is_self:
                st.warning("⚠️ Geração de PDF indisponível. Peça pro admin instalar `reportlab` (adicione ao `requirements.txt` se estiver no Streamlit Cloud).")
            for mod_id, mod_titulo in modulos_completos:
                xp_mod = xp_do_modulo(mod_id)
                icone = icone_modulo(mod_titulo)
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(
                        f"<div class='ranking-box' style='border-left-color:var(--gold);display:flex;align-items:center;gap:12px;'>"
                        f"<div style='font-size:1.8rem;'>{icone}</div>"
                        f"<div style='flex:1;'><b>{mod_titulo}</b><br>"
                        f"<small style='color:var(--text-muted);'>{xp_mod} XP · Módulo completo</small></div></div>",
                        unsafe_allow_html=True
                    )
                with c2:
                    # Só permite baixar se for o próprio aluno olhando o próprio perfil E reportlab disponível
                    if is_self and REPORTLAB_OK:
                        try:
                            pdf_bytes = gerar_certificado_pdf(
                                nome,
                                mod_titulo,
                                date.today().strftime("%d/%m/%Y"),
                                xp_mod
                            )
                            if pdf_bytes:
                                nome_arquivo = f"certificado_{nome.replace(' ', '_')}_{mod_id}.pdf"
                                st.download_button(
                                    "📥 Baixar",
                                    data=pdf_bytes,
                                    file_name=nome_arquivo,
                                    mime="application/pdf",
                                    key=f"cert_dl_{mod_id}",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.caption(f"Erro: {e}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Últimos duelos
        st.markdown("### ⚔️ Últimos duelos")
        hist = duelos_finalizados(pid, limite=5)
        if not hist:
            st.caption("Nenhum duelo finalizado ainda.")
        for d_id, oponente, meu_score, score_op, vencedor_id, quando in hist:
            if vencedor_id is None:
                emoji, cor, status = "🤝", "var(--accent)", "Empate"
            elif vencedor_id == pid:
                emoji, cor, status = "🏆", "var(--primary)", "Vitória"
            else:
                emoji, cor, status = "💀", "var(--danger)", "Derrota"
            st.markdown(
                f"<div class='ranking-box' style='border-left-color:{cor};display:flex;align-items:center;gap:12px;'>"
                f"{render_avatar(oponente, 36)}"
                f"<div style='flex:1;'>{emoji} <b>{status}</b> contra <b>{oponente}</b> — {meu_score} x {score_op}<br>"
                f"<small style='color:var(--text-muted);'>{quando}</small></div></div>",
                unsafe_allow_html=True
            )

        # Meta
        st.markdown(
            f"<div style='margin-top:18px;padding:12px;background:var(--surface);border-radius:10px;"
            f"border:1px solid var(--border);font-size:0.85rem;color:var(--text-muted);'>"
            f"<b style='color:var(--text-dim);'>Membro desde:</b> {criado or '—'} · "
            f"<b style='color:var(--text-dim);'>Último acesso:</b> {ult_acesso or '—'}"
            f"</div>",
            unsafe_allow_html=True
        )

# =========================================================
# TELA: ONBOARDING (novo aluno)
# =========================================================
elif st.session_state.tela == "onboarding":
    slide = st.session_state.get("onboarding_slide", 0)
    slides = [
        {
            "icone": LOGO_SVG,
            "titulo": f"Bem-vindo, {st.session_state.get('aluno', '')}!",
            "texto": "Aqui no <b>Sheep Teacher</b> você aprende inglês completando lições temáticas — gramática, vocabulário, frases bíblicas e muito mais.",
            "extra": "Cada módulo tem várias fases. Comece pelos básicos e desbloqueie os avançados."
        },
        {
            "icone": "<div style='font-size:5rem;text-align:center;'>🏆</div>",
            "titulo": "Ganhe XP, suba de nível",
            "texto": "Cada acerto vale <b>XP</b>. Acumule XP pra subir de nível: 🌱 Iniciante → 📚 Aprendiz → ✍️ Estudante → 🎓 Avançado → 🏆 Mestre → 👑 Sábio → ⭐ Lenda.",
            "extra": "Desbloqueie conquistas, apareça no ranking e mostre que está evoluindo!"
        },
        {
            "icone": "<div style='font-size:5rem;text-align:center;'>🔥</div>",
            "titulo": "Estude todo dia",
            "texto": "Entre <b>todo dia</b> pra manter seu streak 🔥. Quanto mais dias seguidos, mais conquistas desbloqueia.",
            "extra": "Tem também duelos contra amigos 🥊, torneios eliminatórios 🏆 e o desafio diário 🎁 — vale +25 XP bônus por dia!"
        },
    ]

    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        s = slides[slide]
        st.markdown(
            f"<div class='premium-card' style='text-align:center;'>"
            f"<div class='logo-wrap' style='margin:8px 0 20px;'>{s['icone']}</div>"
            f"<h1 style='font-family:Sora;'>{s['titulo']}</h1>"
            f"<p style='font-size:1.1rem;color:var(--text-dim);line-height:1.6;max-width:480px;margin:14px auto;'>{s['texto']}</p>"
            f"<p style='font-size:0.95rem;color:var(--text-muted);max-width:480px;margin:0 auto;'>{s['extra']}</p>"
            f"</div>",
            unsafe_allow_html=True
        )

        # Dots de progresso
        dots = "".join([
            f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px;"
            f"background:{'var(--primary)' if i == slide else 'var(--border-light)'};'></span>"
            for i in range(len(slides))
        ])
        st.markdown(f"<div style='text-align:center;margin:20px 0;'>{dots}</div>", unsafe_allow_html=True)

        bc1, bc2 = st.columns(2)
        with bc1:
            if slide > 0:
                if st.button("⬅️ Voltar", use_container_width=True, key="ob_back"):
                    st.session_state.onboarding_slide = slide - 1
                    st.rerun()
            else:
                if st.button("Pular →", use_container_width=True, key="ob_skip"):
                    st.session_state.onboarding_slide = 0
                    reset_para_inicio(); st.rerun()
        with bc2:
            if slide < len(slides) - 1:
                if st.button("Próximo ➡️", use_container_width=True, key="ob_next"):
                    st.session_state.onboarding_slide = slide + 1
                    st.rerun()
            else:
                if st.button("🚀 Começar a aprender", use_container_width=True, key="ob_done"):
                    st.session_state.onboarding_slide = 0
                    reset_para_inicio(); st.rerun()

# =========================================================
# TELA: CONVERSAÇÃO - LISTA DE TEMAS
# =========================================================
elif st.session_state.tela == "conversacao_lista":
    uid = st.session_state.uid

    st.markdown(
        "<div class='premium-card' style='display:flex;align-items:center;gap:18px;'>"
        "<div style='font-size:3rem;'>💬</div>"
        "<div><h1 style='margin:0;font-family:Sora,sans-serif;'>Conversação</h1>"
        "<p class='subtitulo' style='margin:4px 0 0;'>Cada tema é uma trilha de perguntas em sequência. "
        "Responda no seu ritmo — o app te ajuda corrigindo erros comuns.</p>"
        "</div></div>",
        unsafe_allow_html=True
    )

    # Estatísticas globais
    total_perguntas = sum(len(t["perguntas"]) for t in CONVERSAS_TEMAS)
    hist = historico_conversas(uid)
    total_respondidas = sum(1 for h in hist if any(
        h.startswith(t["id"] + "_q") for t in CONVERSAS_TEMAS
    ))
    temas_completos = sum(1 for t in CONVERSAS_TEMAS if tema_completo(uid, t))

    sa, sb, sc = st.columns(3)
    with sa: st.markdown(f"<div class='stat-box'><div class='stat-num'>{total_respondidas}</div><div class='stat-label'>Perguntas Respondidas</div></div>", unsafe_allow_html=True)
    with sb: st.markdown(f"<div class='stat-box'><div class='stat-num'>{total_perguntas}</div><div class='stat-label'>Total de Perguntas</div></div>", unsafe_allow_html=True)
    with sc: st.markdown(f"<div class='stat-box'><div class='stat-num'>{temas_completos}/{len(CONVERSAS_TEMAS)}</div><div class='stat-label'>Temas Completos</div></div>", unsafe_allow_html=True)

    if not SPELL_OK:
        st.info("ℹ️ Corretor de ortografia indisponível. O corretor de gramática continua funcionando.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📚 Escolha um tema")

    # Grid de temas
    cols = st.columns(2)
    for i, tema in enumerate(CONVERSAS_TEMAS):
        respondidas, total = progresso_tema(uid, tema)
        pct = int(100 * respondidas / total) if total else 0
        completo = (respondidas == total)
        cor_borda = "var(--primary)" if completo else ("var(--accent)" if respondidas > 0 else "var(--border-light)")
        badge = ("<span style='color:var(--primary);font-weight:600;'>✅ COMPLETO</span>"
                 if completo else
                 f"<span style='color:var(--accent);font-weight:600;'>{respondidas}/{total} respondidas</span>"
                 if respondidas > 0 else
                 f"<span style='color:var(--text-dim);font-weight:600;'>{total} perguntas</span>")

        with cols[i % 2]:
            st.markdown(
                f"<div class='premium-card' style='padding:18px;margin-bottom:14px;"
                f"border-left:3px solid {cor_borda};'>"
                f"<div style='display:flex;align-items:start;gap:14px;'>"
                f"<div style='font-size:2.4rem;'>{tema['icone']}</div>"
                f"<div style='flex:1;min-width:0;'>"
                f"<b style='font-size:1.1rem;'>{tema['tema']}</b><br>"
                f"{badge}"
                f"<p style='color:var(--text-dim);margin:8px 0 10px;font-size:0.9rem;line-height:1.45;'>{tema['descricao']}</p>"
                # Barra de progresso
                f"<div style='background:var(--border);height:6px;border-radius:3px;overflow:hidden;'>"
                f"<div style='background:{cor_borda};height:100%;width:{pct}%;transition:width 0.5s;'></div></div>"
                f"</div></div></div>",
                unsafe_allow_html=True
            )
            if completo:
                btn_label = "🔁 Refazer tema"
            elif respondidas > 0:
                btn_label = "➡️ Continuar tema"
            else:
                btn_label = "🎯 Começar tema"
            if st.button(btn_label, key=f"tema_btn_{tema['id']}", use_container_width=True):
                st.session_state.tema_atual = tema["id"]
                # Se completo, começa do início; senão, na próxima não respondida
                if completo:
                    st.session_state.tema_pergunta_idx = 0
                else:
                    st.session_state.tema_pergunta_idx = proxima_pergunta_tema(uid, tema)
                for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho"]:
                    st.session_state.pop(k, None)
                st.session_state.tela = "conversacao_tema"
                st.rerun()

# =========================================================
# TELA: CONVERSAÇÃO - TRILHA DE PERGUNTAS DENTRO DE UM TEMA
# =========================================================
elif st.session_state.tela == "conversacao_tema":
    uid = st.session_state.uid
    tema_id = st.session_state.get("tema_atual")
    tema = next((t for t in CONVERSAS_TEMAS if t["id"] == tema_id), None)

    if not tema:
        st.error("Tema não encontrado.")
        if st.button("⬅️ Voltar"):
            st.session_state.tela = "conversacao_lista"; st.rerun()
    else:
        idx = st.session_state.get("tema_pergunta_idx", 0)
        idx = max(0, min(idx, len(tema["perguntas"]) - 1))
        pergunta = tema["perguntas"][idx]
        conv_id = _conversa_id(tema["id"], idx)
        total = len(tema["perguntas"])
        respondidas, _ = progresso_tema(uid, tema)
        pct = int(100 * (idx + 1) / total)

        # Top: voltar pra lista
        c_back, c_prog = st.columns([1, 4])
        with c_back:
            if st.button("⬅️ Temas"):
                st.session_state.tela = "conversacao_lista"
                for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with c_prog:
            st.progress((idx + 1) / total)
            st.caption(f"{tema['icone']} {tema['tema']} — Pergunta {idx + 1} de {total} · {respondidas} respondida(s)")

        # Cabeçalho da pergunta
        st.markdown(
            f"<div class='premium-card' style='display:flex;align-items:center;gap:18px;margin-top:8px;'>"
            f"<div style='font-size:2.8rem;'>{tema['icone']}</div>"
            f"<div style='flex:1;'>"
            f"<div style='color:var(--text-dim);font-size:0.8rem;text-transform:uppercase;"
            f"letter-spacing:1.4px;font-weight:600;'>{tema['tema']}</div>"
            f"<h2 style='margin:4px 0;font-family:Sora,sans-serif;font-size:1.6rem;'>{pergunta['pergunta_pt']}</h2>"
            f"<div style='color:var(--primary-light);font-size:1.05rem;font-style:italic;margin-top:6px;'>"
            f"{pergunta['pergunta_en']}</div></div></div>",
            unsafe_allow_html=True
        )

        # Áudio + dica
        col_a, col_b = st.columns([1, 6])
        with col_a:
            botao_audio(pergunta["pergunta_en"], "🔊 Ouvir")
        if pergunta.get("dica"):
            st.markdown(f"<div class='explicacao'>💡 <b>Dica:</b> {pergunta['dica']}</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        ja_respondeu_antes = ultima_resposta_conversa(uid, conv_id)
        respondida_agora = bool(st.session_state.get("conv_resposta_enviada"))

        if not respondida_agora:
            # Mostra textarea pra responder
            if ja_respondeu_antes:
                st.caption(f"📌 Sua resposta anterior ({ja_respondeu_antes[2]}): _{ja_respondeu_antes[0]}_")
            resposta = st.text_area(
                "✏️ Sua resposta em inglês:",
                height=130,
                placeholder="Escreva sua resposta. Não precisa ser perfeita — o importante é praticar.",
                key=f"conv_ta_{tema['id']}_{idx}"
            )
            c_send, c_skip = st.columns([2, 1])
            with c_send:
                if st.button("📤 Enviar resposta", use_container_width=True, type="primary",
                             key=f"send_{tema['id']}_{idx}"):
                    if not resposta or not resposta.strip():
                        st.warning("Escreva alguma coisa antes de enviar 😊")
                    elif len(resposta.strip()) < 3:
                        st.warning("Tente escrever uma frase mais completa.")
                    else:
                        problemas = corrigir_ingles(resposta)
                        erros_qtd = len(problemas)
                        xp_ganho = XP_CONVERSA_BASE + (XP_CONVERSA_BONUS_SEM_ERROS if erros_qtd == 0 else 0)

                        # Verifica se essa resposta completa o tema (bônus extra na primeira vez)
                        tema_estava_completo = tema_completo(uid, tema)
                        salvar_resposta_conversa(uid, conv_id, resposta.strip(), erros_qtd)
                        tema_agora_completo = tema_completo(uid, tema)
                        bonus_tema = 0
                        if not tema_estava_completo and tema_agora_completo:
                            bonus_tema = XP_TEMA_COMPLETO_BONUS
                            xp_ganho += bonus_tema
                            st.session_state.tema_recem_completado = True

                        executar("UPDATE alunos SET xp_total = xp_total + ? WHERE id = ?", (xp_ganho, uid))
                        verificar_conquistas(uid)
                        st.session_state.conv_resposta_enviada = resposta.strip()
                        st.session_state.conv_problemas = problemas
                        st.session_state.conv_xp_ganho = xp_ganho
                        st.session_state.conv_bonus_tema = bonus_tema
                        st.rerun()
            with c_skip:
                if idx + 1 < total:
                    if st.button("⏭️ Pular", use_container_width=True, key=f"skip_{tema['id']}_{idx}",
                                 help="Pular esta pergunta sem responder"):
                        st.session_state.tema_pergunta_idx = idx + 1
                        for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho"]:
                            st.session_state.pop(k, None)
                        st.rerun()

        else:
            # Mostra feedback da resposta
            resposta = st.session_state.conv_resposta_enviada
            problemas = st.session_state.get("conv_problemas", [])
            xp_ganho = st.session_state.get("conv_xp_ganho", XP_CONVERSA_BASE)
            bonus_tema = st.session_state.get("conv_bonus_tema", 0)

            # Banner principal
            sem_erros = (len(problemas) == 0)
            st.markdown(
                f"<div style='background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(252,211,77,0.08));"
                f"border:1px solid var(--primary);border-radius:14px;padding:18px 22px;margin-bottom:18px;"
                f"display:flex;align-items:center;gap:16px;'>"
                f"<div style='font-size:2.2rem;'>{'🌟' if sem_erros else '✅'}</div>"
                f"<div style='flex:1;'>"
                f"<b style='color:var(--primary-light);font-size:1.15rem;'>"
                f"{'Resposta perfeita!' if sem_erros else 'Resposta enviada!'}</b><br>"
                f"<span class='xp-floating'>+{xp_ganho} XP</span>"
                + (f" <span style='color:var(--gold);font-weight:600;'>(+{XP_CONVERSA_BONUS_SEM_ERROS} bônus sem erros)</span>" if sem_erros and bonus_tema == 0 else "")
                + (f"<br><span style='color:var(--gold);font-weight:700;font-size:1.05rem;'>🏆 TEMA COMPLETO! +{XP_TEMA_COMPLETO_BONUS} XP de bônus</span>" if bonus_tema > 0 else "")
                + f"</div></div>",
                unsafe_allow_html=True
            )

            # Resposta dele
            st.markdown(
                f"<div style='background:var(--surface);border:1px solid var(--border);"
                f"border-radius:12px;padding:16px;margin-bottom:18px;'>"
                f"<div style='color:var(--text-dim);font-size:0.78rem;text-transform:uppercase;"
                f"letter-spacing:1.2px;font-weight:600;margin-bottom:6px;'>📝 Sua resposta:</div>"
                f"<div style='font-size:1.05rem;color:var(--text);line-height:1.55;'>{resposta}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

            # Problemas
            if problemas:
                st.markdown(f"### 💡 {len(problemas)} dica(s) pra melhorar:")
                for i, p in enumerate(problemas, 1):
                    st.markdown(
                        f"<div class='ranking-box' style='border-left-color:var(--accent);'>"
                        f"<div style='display:flex;align-items:start;gap:12px;'>"
                        f"<div style='background:var(--accent);color:white;border-radius:50%;"
                        f"width:24px;height:24px;display:flex;align-items:center;justify-content:center;"
                        f"font-weight:700;font-size:0.85rem;flex-shrink:0;'>{i}</div>"
                        f"<div style='flex:1;'>"
                        f"<b style='color:var(--gold);font-size:0.85rem;text-transform:uppercase;"
                        f"letter-spacing:0.5px;'>{p['tipo']}</b><br>"
                        f"<span style='color:var(--text);'>{p['msg']}</span><br>"
                        f"<span style='color:var(--text-dim);font-size:0.9rem;font-style:italic;'>"
                        f"📌 {p['exemplo']}</span>"
                        f"</div></div></div>",
                        unsafe_allow_html=True
                    )
                st.markdown("<br>", unsafe_allow_html=True)
            else:
                st.success("🎯 Texto bem escrito! Não detectei erros gramaticais comuns.")

            botao_audio(resposta, "🔊 Ouvir sua resposta")

            st.markdown("<br>", unsafe_allow_html=True)

            # Navegação: próxima pergunta ou voltar
            if idx + 1 < total:
                cb1, cb2, cb3 = st.columns([1, 2, 1])
                with cb1:
                    if st.button("🔁 Refazer", use_container_width=True, key=f"redo_{tema['id']}_{idx}"):
                        for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho", "conv_bonus_tema"]:
                            st.session_state.pop(k, None)
                        st.rerun()
                with cb2:
                    if st.button("Próxima pergunta ➡️", use_container_width=True, type="primary",
                                 key=f"next_{tema['id']}_{idx}"):
                        st.session_state.tema_pergunta_idx = idx + 1
                        for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho", "conv_bonus_tema"]:
                            st.session_state.pop(k, None)
                        st.rerun()
                with cb3:
                    if st.button("📋 Temas", use_container_width=True, key=f"back_{tema['id']}_{idx}"):
                        st.session_state.tela = "conversacao_lista"
                        for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho", "conv_bonus_tema"]:
                            st.session_state.pop(k, None)
                        st.rerun()
            else:
                # Última pergunta — tema concluído
                st.markdown(
                    f"<div style='background:linear-gradient(135deg, rgba(252,211,77,0.18), rgba(16,185,129,0.1));"
                    f"border:2px solid var(--gold);border-radius:14px;padding:24px;margin:18px 0;text-align:center;'>"
                    f"<div style='font-size:3rem;'>🎉</div>"
                    f"<h2 style='margin:8px 0;font-family:Sora,sans-serif;color:var(--gold);'>Tema concluído!</h2>"
                    f"<p style='color:var(--text-dim);'>Você respondeu todas as perguntas de <b>{tema['tema']}</b>. "
                    f"Parabéns pela prática!</p></div>",
                    unsafe_allow_html=True
                )
                cb1, cb2 = st.columns(2)
                with cb1:
                    if st.button("📋 Outros temas", use_container_width=True, type="primary",
                                 key=f"others_{tema['id']}"):
                        st.session_state.tela = "conversacao_lista"
                        for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho", "conv_bonus_tema"]:
                            st.session_state.pop(k, None)
                        st.rerun()
                with cb2:
                    if st.button("🔁 Refazer este tema", use_container_width=True, key=f"redo_tema_{tema['id']}"):
                        st.session_state.tema_pergunta_idx = 0
                        for k in ["conv_resposta_enviada", "conv_problemas", "conv_xp_ganho", "conv_bonus_tema"]:
                            st.session_state.pop(k, None)
                        st.rerun()

# =========================================================
# TELA: CHAT COM SHEEP (IA conversa livre)
# =========================================================
elif st.session_state.tela == "chat_sheep":
    uid = st.session_state.uid
    nome_aluno = st.session_state.get("aluno", "friend")

    # Header
    st.markdown(
        f"<div class='premium-card' style='display:flex;align-items:center;gap:18px;'>"
        f"<div class='logo-wrap' style='margin:0;'>{LOGO_SVG}</div>"
        f"<div style='flex:1;'>"
        f"<h1 style='margin:0;font-family:Sora,sans-serif;'>Conversar com Sheep</h1>"
        f"<p class='subtitulo' style='margin:4px 0 0;'>Bate-papo livre em inglês com a Sheep 🐑. "
        f"Ela responde, faz perguntas e adapta a conversa ao seu nível. +5 XP por mensagem enviada.</p>"
        f"</div></div>",
        unsafe_allow_html=True
    )

    # Detecta provedor disponível
    gem_disp = get_gemini_model(SHEEP_SYSTEM_PROMPT) is not None
    ant_disp = get_anthropic_client() is not None
    nenhum = not (gem_disp or ant_disp)

    if nenhum:
        if not (GEMINI_LIB_OK or ANTHROPIC_LIB_OK):
            st.warning("⚠️ Bibliotecas de IA não instaladas. Adicione ao `requirements.txt`: `google-generativeai>=0.8` (grátis) ou `anthropic>=0.40` (pago).")
        else:
            st.warning("⚠️ Nenhuma chave de API configurada. Veja abaixo como ativar (uma vez só).")

        with st.expander("🎁 Opção 1 — Google Gemini (RECOMENDADO, GRÁTIS)", expanded=True):
            st.markdown("""
**Google dá 1 milhão de tokens por dia, grátis.** Pra uma escola com 30-50 alunos, é mais que suficiente — você nunca vai bater o limite.

1. Vá em **https://aistudio.google.com/apikey** (entre com sua conta Google)
2. Clique em **"Create API key"**
3. Copie a chave (começa com `AIzaSy...`)
4. No painel do **Streamlit Cloud**, abra seu app → **⚙️ Settings → Secrets**
5. Adicione esta linha:
   ```
   GEMINI_API_KEY = "AIzaSy-sua-chave-aqui"
   ```
6. Salve. O app reinicia e o chat passa a funcionar.

**Custo:** 0,00 USD. Não pede cartão de crédito.
""")

        with st.expander("💼 Opção 2 — Anthropic Claude (pago, mais inteligente)"):
            st.markdown("""
Se quiser mais qualidade nas respostas (Claude é mais sofisticado), use a Anthropic.

1. Crie conta em **https://console.anthropic.com/**
2. Vá em **API Keys → Create Key**, copie (começa com `sk-ant-...`)
3. No Streamlit Cloud, adicione nos Secrets:
   ```
   ANTHROPIC_API_KEY = "sk-ant-sua-chave-aqui"
   ```

**Custo:** ~$0,01 USD por conversa de 10 mensagens (Claude Haiku). Anthropic dá US$5 de crédito inicial.
""")
        st.caption("💡 **Dica:** comece pelo Gemini (grátis) e veja se atende. A qualidade é ótima pra conversação básica.")
    else:
        provedor = "gemini" if gem_disp else "anthropic"
        badge_provedor = "🎁 via Gemini (grátis)" if provedor == "gemini" else "💼 via Anthropic Claude"
        st.caption(f"Conectada: <span style='color:var(--primary);'>{badge_provedor}</span>", unsafe_allow_html=True)

        # Inicializa histórico
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []

        # Saudação inicial (mostrada visualmente, mas NÃO enviada à API)
        if not st.session_state.chat_messages:
            with st.chat_message("assistant", avatar="🐑"):
                st.markdown(f"Hi, **{nome_aluno}**! I'm Sheep 🐑. I'm here to chat with you in English. "
                            f"How are you today? Tell me anything — about your day, your family, "
                            f"church... I'm all ears!")
        else:
            for msg in st.session_state.chat_messages:
                avatar = "🐑" if msg["role"] == "assistant" else None
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

        # Input
        if prompt := st.chat_input("Type in English..."):
            # Adiciona mensagem do aluno
            st.session_state.chat_messages.append({"role": "user", "content": prompt.strip()})

            # Mostra imediatamente
            with st.chat_message("user"):
                st.markdown(prompt.strip())

            # Chama IA
            try:
                msgs_para_api = st.session_state.chat_messages[-30:]  # últimas 30 msgs
                with st.chat_message("assistant", avatar="🐑"):
                    with st.spinner("Sheep está pensando..."):
                        bot_reply, _provedor_usado = chat_com_ia(msgs_para_api, SHEEP_SYSTEM_PROMPT, max_tokens=400)
                        st.markdown(bot_reply)

                st.session_state.chat_messages.append({"role": "assistant", "content": bot_reply})

                # XP por enviar mensagem
                executar("UPDATE alunos SET xp_total = xp_total + 5 WHERE id = ?", (uid,))
                verificar_conquistas(uid)
                st.rerun()

            except Exception as e:
                msg_erro = str(e)
                if "API_KEY_INVALID" in msg_erro or "401" in msg_erro or "authentication" in msg_erro.lower():
                    st.error("Chave de API inválida. Verifique no painel de Secrets do Streamlit Cloud.")
                elif "quota" in msg_erro.lower() or "429" in msg_erro or "rate" in msg_erro.lower():
                    st.warning("Cota da API esgotada ou muitas mensagens. Tente de novo em alguns segundos.")
                elif "connection" in msg_erro.lower() or "timeout" in msg_erro.lower():
                    st.error("Erro de conexão. Verifique sua internet e tente de novo.")
                else:
                    st.error(f"Algo deu errado: {type(e).__name__}. Mensagem: {msg_erro[:200]}")

        # Footer
        st.markdown("<br>", unsafe_allow_html=True)
        ca, cb, cc = st.columns([1, 1, 2])
        with ca:
            if st.button("🔄 Nova conversa", use_container_width=True,
                         help="Limpa o histórico e começa de novo"):
                st.session_state.chat_messages = []
                st.rerun()
        with cb:
            n_user = sum(1 for m in st.session_state.chat_messages if m["role"] == "user")
            st.markdown(f"<div style='text-align:center;padding-top:10px;color:var(--text-dim);font-size:0.9rem;'>"
                        f"💬 <b>{n_user}</b> mensagens enviadas</div>", unsafe_allow_html=True)
        with cc:
            st.caption("💡 Tente perguntar sobre seu dia, família, igreja, sonhos. "
                       "Sheep adapta o inglês ao seu nível.")

# =========================================================
# TELA: CONCLUSÃO
# =========================================================
elif st.session_state.tela == "conclusao_trilha":
    st.markdown("<div class='premium-card' style='text-align:center;'><h1>🎉 Concluído!</h1><p>Parabéns, continue assim!</p></div>", unsafe_allow_html=True)
    novas = st.session_state.get("conquistas_novas", [])
    if novas:
        st.markdown("### 🏅 Você desbloqueou:")
        for bid in novas:
            icone, nome, desc = BADGES[bid]
            st.markdown(f"<div class='badge-card' style='border-color:var(--primary);'><div style='font-size:2rem'>{icone}</div><b>{nome}</b><br><small>{desc}</small></div>", unsafe_allow_html=True)
    if st.button("Voltar ao Menu"):
        st.session_state.conquistas_novas = []
        reset_para_inicio(); st.rerun()