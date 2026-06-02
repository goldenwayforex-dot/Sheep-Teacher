import streamlit as st
import sqlite3
import random
import hashlib
import json
from datetime import date, datetime, timedelta

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
st.set_page_config(page_title="Sheep Teacher - Bethany Church", layout="wide", initial_sidebar_state="collapsed")

DB_PATH = 'banco_ingles.db'
PROFESSOR_NOME = "professor"           # nome reservado para o painel admin
PROFESSOR_PIN  = "1234"                # MUDE este PIN antes de usar de verdade
XP_POR_ACERTO  = 10
XP_REVISAO     = 5
# --- Duelo ---
DUELO_QUESTOES   = 10   # quantas questões por duelo
DUELO_XP_VITORIA = 30
DUELO_XP_DERROTA = 10
DUELO_XP_EMPATE  = 15
DUELO_MAX_PENDENTES = 5  # máx. de duelos enviados aguardando resposta

# --- CSS ---
st.markdown("""
<style>
html, body, [class*="css"] { font-family: 'Trebuchet MS', sans-serif !important; background-color: #0A0A0C; }
.premium-card { background: linear-gradient(145deg, #121216, #1A1A22); padding: 30px; border-radius: 16px; border: 1px solid #2A2A35; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }
.ranking-box { background: #111115; padding: 12px; border-radius: 12px; border-left: 4px solid lime; margin-bottom: 10px; border: 1px solid #222; }
.badge-card { background:#111115; padding:14px; border-radius:12px; border:1px solid #2A2A35; margin-bottom:8px; text-align:center; }
.badge-locked { opacity: 0.35; }
.stat-box { background: linear-gradient(145deg, #121216, #1A1A22); padding:20px; border-radius:12px; border:1px solid #2A2A35; text-align:center; }
.stat-num { font-size: 2rem; font-weight: 800; color: lime; }
.stat-label { color:#8E8E93; font-size:0.85rem; text-transform: uppercase; letter-spacing: 1px; }
.stButton>button { background-color: #111115; color: #FFFFFF; border: 2px solid lime; border-radius: 12px; font-weight: bold; height: 52px; width: 100%; transition: all 0.3s; }
.stButton>button:hover { background-color: lime; color: #000000; box-shadow: 0 0 20px rgba(0, 255, 0, 0.5); transform: translateY(-2px); }
.titulo-principal { font-size: 3rem; font-weight: 800; background: linear-gradient(90deg, #FFFFFF, #8E8E93); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.subtitulo { color: #8E8E93; font-size: 1.05rem; }
.tag-nivel { display:inline-block; padding:3px 10px; border-radius:12px; font-size:0.75rem; font-weight:bold; margin-left:8px; }
.nivel-1 { background:#1B3A1B; color:#7CFC7C; border:1px solid #2D5A2D; }
.nivel-2 { background:#3A2D1B; color:#FFC97C; border:1px solid #5A472D; }
.nivel-3 { background:#3A1B1B; color:#FF7C7C; border:1px solid #5A2D2D; }
.streak-fire { font-size:1.4rem; font-weight:bold; color:#FF8C00; }
.explicacao { background:#0F1A0F; border-left:4px solid lime; padding:12px 16px; border-radius:8px; margin-top:10px; color:#CFE9CF; }
.audio-btn { background:#111115; color:#FFF; border:2px solid lime; border-radius:8px; padding:6px 14px; font-weight:bold; cursor:pointer; font-size:0.9rem; }
@media (max-width: 768px) {
    .titulo-principal { font-size: 2rem !important; }
    .premium-card { padding: 18px !important; }
    .stat-num { font-size: 1.4rem !important; }
}
</style>
""", unsafe_allow_html=True)

# --- HELPERS DE BANCO ---
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
    rows = consultar("SELECT nome, xp_total, streak FROM alunos WHERE nome != ? ORDER BY xp_total DESC LIMIT 5", (PROFESSOR_NOME,))
    if not rows:
        st.caption("Ainda sem alunos cadastrados.")
    for r in rows:
        nome, xp, streak = r
        fire = f" 🔥{streak}" if streak and streak > 0 else ""
        st.markdown(f"<div class='ranking-box'><b>{nome}</b>{fire}<br><span style='color:lime;'>{xp} XP</span></div>", unsafe_allow_html=True)

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
    aluno = consultar_um("SELECT xp_total, streak FROM alunos WHERE id = ?", (uid,))
    if not aluno:
        return novas
    xp, streak = aluno
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

def criar_duelo(desafiante_id, desafiado_id, questoes_ids, score):
    return executar("""
        INSERT INTO duelos (desafiante_id, desafiado_id, questoes_ids,
                            score_desafiante, status, criado_em)
        VALUES (?,?,?,?,?,?)
    """, (desafiante_id, desafiado_id, json.dumps(questoes_ids),
          score, 'aguardando_desafiado', datetime.now().isoformat(timespec='seconds')))

def finalizar_duelo(duelo_id, score_desafiado):
    """Salva o score do desafiado, calcula vencedor e distribui XP."""
    d = consultar_um("SELECT desafiante_id, desafiado_id, score_desafiante FROM duelos WHERE id = ?", (duelo_id,))
    if not d:
        return None
    desafiante_id, desafiado_id, score_des = d
    if score_desafiado > score_des:
        vencedor = desafiado_id
    elif score_des > score_desafiado:
        vencedor = desafiante_id
    else:
        vencedor = None
    executar("""UPDATE duelos SET score_desafiado = ?, vencedor_id = ?, status = ?, atualizado_em = ?
                WHERE id = ?""",
             (score_desafiado, vencedor, 'finalizado',
              datetime.now().isoformat(timespec='seconds'), duelo_id))

    if vencedor is None:  # empate
        executar("UPDATE alunos SET xp_total = xp_total + ?, empates_duelo = empates_duelo + 1 WHERE id = ?",
                 (DUELO_XP_EMPATE, desafiante_id))
        executar("UPDATE alunos SET xp_total = xp_total + ?, empates_duelo = empates_duelo + 1 WHERE id = ?",
                 (DUELO_XP_EMPATE, desafiado_id))
    else:
        perdedor = desafiante_id if vencedor == desafiado_id else desafiado_id
        executar("UPDATE alunos SET xp_total = xp_total + ?, vitorias_duelo = vitorias_duelo + 1 WHERE id = ?",
                 (DUELO_XP_VITORIA, vencedor))
        executar("UPDATE alunos SET xp_total = xp_total + ?, derrotas_duelo = derrotas_duelo + 1 WHERE id = ?",
                 (DUELO_XP_DERROTA, perdedor))
    return vencedor

def cancelar_duelo(duelo_id, uid):
    """Permite cancelar um duelo enviado que ninguém respondeu ainda."""
    d = consultar_um("SELECT desafiante_id, status FROM duelos WHERE id = ?", (duelo_id,))
    if not d:
        return False
    if d[0] != uid or d[1] != 'aguardando_desafiado':
        return False  # só o desafiante e só se ainda não foi respondido
    executar("DELETE FROM duelos WHERE id = ?", (duelo_id,))
    return True

def carregar_duelo(duelo_id):
    return consultar_um("""
        SELECT id, desafiante_id, desafiado_id, questoes_ids,
               score_desafiante, score_desafiado, vencedor_id, status, criado_em, atualizado_em
        FROM duelos WHERE id = ?
    """, (duelo_id,))

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
]

# Explicações pedagógicas - só onde realmente ajuda (gramática)
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
    cur.execute('CREATE TABLE IF NOT EXISTS modulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL UNIQUE, nivel INTEGER DEFAULT 1)')
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
        ("modulos", "nivel", "INTEGER", 1),
        ("licoes", "opcao_4", "TEXT", None),
        ("licoes", "explicacao", "TEXT", None),
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
        cur.execute("SELECT id FROM modulos WHERE titulo = ?", (titulo,))
        if cur.fetchone():
            # módulo já existe - atualizar o nível caso tenha mudado
            cur.execute("UPDATE modulos SET nivel = ? WHERE titulo = ?", (nivel, titulo))
            continue
        cur.execute("INSERT INTO modulos (titulo, nivel) VALUES (?, ?)", (titulo, nivel))
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
             ("duelo_questoes", []), ("duelo_idx", 0)]:
    if k not in st.session_state:
        st.session_state[k] = v

def reset_para_inicio():
    """Volta para a tela principal limpando estado de lição."""
    st.session_state.tela = "inicio"
    st.session_state.respondido = False
    st.session_state.opcoes_atuais = []
    st.session_state.erros_na_licao = 0
    st.session_state.modo_revisao = False
    st.session_state.duelo_id = None
    st.session_state.duelo_modo = None
    st.session_state.duelo_score = 0
    st.session_state.duelo_questoes = []
    st.session_state.duelo_idx = 0

# --- Funções auxiliares da tela de lição ---
def processar_resposta(resp, correta, lic_id, explicacao, forcar=None):
    """Trata acerto/erro. Se forcar=True/False, ignora comparação direta (caso typing)."""
    uid = st.session_state.uid
    if forcar is None:
        acertou = (resp == correta)
    else:
        acertou = forcar
    if acertou:
        xp_ganho = XP_REVISAO if st.session_state.modo_revisao else XP_POR_ACERTO
        st.session_state.feedback = f"✅ Correto! +{xp_ganho} XP"
        executar("UPDATE alunos SET xp_total = xp_total + ? WHERE id = ?", (xp_ganho, uid))
        if not st.session_state.modo_revisao:
            executar("INSERT OR IGNORE INTO progresso VALUES (?,?)", (uid, lic_id))
        if st.session_state.modo_revisao:
            executar("UPDATE erros SET count = MAX(count - 1, 0) WHERE aluno_id = ? AND licao_id = ?", (uid, lic_id))
    else:
        st.session_state.vidas -= 1
        st.session_state.erros_na_licao += 1
        st.session_state.feedback = f"❌ Não foi dessa vez. Resposta correta: **{correta}**"
        registrar_erro(uid, lic_id)
    st.session_state.respondido = True

def mostrar_feedback(correta, explicacao):
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
# TELA: LOGIN (redesenhada)
# =========================================================
if st.session_state.tela == "login":
    # Hero
    st.markdown("<br>", unsafe_allow_html=True)
    h1, h2, h3 = st.columns([1, 2, 1])
    with h2:
        st.markdown("""
        <div class='premium-card' style='text-align:center;'>
            <h1 class='titulo-principal'>🐑 Sheep Teacher</h1>
            <p class='subtitulo'>Bethany Church English School<br>
            <span style='color:lime;'>Learn English. Grow in Faith.</span></p>
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
        st.markdown("### Acessar")
        with st.form("login_form"):
            nome = st.text_input("Nome", placeholder="Seu nome").strip()
            pin = st.text_input("PIN (4 dígitos)", type="password", max_chars=8, placeholder="Ex: 1234")
            st.caption("Primeira vez? Digite seu nome e crie um PIN. Ele será sua senha pra entrar de novo.")
            entrou = st.form_submit_button("Acessar 🚀", use_container_width=True)
            if entrou:
                if not nome or not pin:
                    st.warning("Preencha nome e PIN.")
                elif len(pin) < 4:
                    st.warning("O PIN precisa ter pelo menos 4 caracteres.")
                else:
                    # Caso especial: professor
                    if nome.lower() == PROFESSOR_NOME:
                        if pin == PROFESSOR_PIN:
                            st.session_state.tela = "admin"
                            st.session_state.aluno = "Professor"
                            st.rerun()
                        else:
                            st.error("PIN do professor incorreto.")
                    else:
                        existente = consultar_um("SELECT id, pin_hash FROM alunos WHERE nome = ?", (nome,))
                        if existente:
                            uid, pin_h = existente
                            # Aluno antigo (sem PIN) → cria agora
                            if not pin_h:
                                executar("UPDATE alunos SET pin_hash = ? WHERE id = ?", (hash_pin(pin), uid))
                                st.session_state.uid = uid
                                st.session_state.aluno = nome
                                st.success("PIN cadastrado! Bem-vindo de volta.")
                                streak = atualizar_streak_no_login(uid)
                                verificar_conquistas(uid)
                                reset_para_inicio()
                                st.rerun()
                            elif pin_h == hash_pin(pin):
                                st.session_state.uid = uid
                                st.session_state.aluno = nome
                                streak = atualizar_streak_no_login(uid)
                                verificar_conquistas(uid)
                                reset_para_inicio()
                                st.rerun()
                            else:
                                st.error("PIN incorreto. Tente de novo.")
                        else:
                            # Novo aluno
                            uid = executar("INSERT INTO alunos (nome, pin_hash, criado_em) VALUES (?, ?, ?)",
                                           (nome, hash_pin(pin), date.today().isoformat()))
                            st.session_state.uid = uid
                            st.session_state.aluno = nome
                            atualizar_streak_no_login(uid)
                            verificar_conquistas(uid)
                            st.success(f"Conta criada! Bem-vindo, {nome}.")
                            reset_para_inicio()
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
                <div class='ranking-box'>
                <b>{nome_a}</b> &nbsp;|&nbsp; {xp_a} XP &nbsp;|&nbsp;
                🔥 {streak_a or 0} (melhor: {melhor_a or 0}) &nbsp;|&nbsp;
                ✅ {licoes_a} lições &nbsp;|&nbsp; 🏅 {badges_a} conquistas<br>
                <small style='color:#777;'>Último acesso: {ult_a or '—'} &nbsp;|&nbsp; Cadastrado: {crio_a or '—'}</small>
                </div>
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
            <b>{pergunta}</b> → <span style='color:lime;'>{correta}</span><br>
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
            st.markdown(f"<div class='ranking-box'>{n1} vs {n2}<br>{res}<br><small style='color:#999;'>{criado}</small></div>", unsafe_allow_html=True)

    with aba4:
        st.markdown("### Conteúdo atual")
        for mod in consultar("SELECT id, titulo, nivel FROM modulos ORDER BY id"):
            mid, tit, niv = mod
            niv_label = {1: "Básico", 2: "Intermediário", 3: "Avançado"}.get(niv, "—")
            with st.expander(f"📦 {tit} — Nível: {niv_label}"):
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
    st.markdown(f"### 👋 Bem-vindo, **{st.session_state.aluno}**!")
    sa, sb, sc, sd = st.columns(4)
    with sa: st.markdown(f"<div class='stat-box'><div class='stat-num'>{xp_a}</div><div class='stat-label'>XP</div></div>", unsafe_allow_html=True)
    with sb: st.markdown(f"<div class='stat-box'><div class='stat-num'>🔥 {streak_a or 0}</div><div class='stat-label'>Streak (dias)</div></div>", unsafe_allow_html=True)
    with sc: st.markdown(f"<div class='stat-box'><div class='stat-num'>{licoes_done}</div><div class='stat-label'>Lições</div></div>", unsafe_allow_html=True)
    with sd: st.markdown(f"<div class='stat-box'><div class='stat-num'>🏅 {badges_qtd}</div><div class='stat-label'>Conquistas</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Notificação de desafios pendentes
    pendentes_qtd = len(duelos_pendentes_para_responder(uid))
    if pendentes_qtd > 0:
        st.markdown(f"<div style='background:#3A1B1B;border-left:4px solid #FF5252;padding:14px;border-radius:8px;margin-bottom:14px;'><b>🥊 Você foi desafiado!</b> Você tem <b>{pendentes_qtd}</b> duelo(s) esperando sua resposta.</div>", unsafe_allow_html=True)

    # Botões de ação rápida
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("🧠 Revisão", use_container_width=True):
            revisao = obter_revisao_inteligente(uid, n=10)
            if not revisao:
                st.warning("Faça pelo menos uma lição para liberar a revisão.")
            else:
                st.session_state.trilha = revisao
                st.session_state.idx = 0
                st.session_state.vidas = 3
                st.session_state.respondido = False
                st.session_state.opcoes_atuais = []
                st.session_state.modo_revisao = True
                st.session_state.tela = "licao"
                st.rerun()
    with b2:
        label = f"🥊 Duelos ({pendentes_qtd})" if pendentes_qtd > 0 else "🥊 Duelos"
        if st.button(label, use_container_width=True):
            st.session_state.tela = "duelo_lobby"; st.rerun()
    with b3:
        if st.button("🏅 Conquistas", use_container_width=True):
            st.session_state.tela = "conquistas"; st.rerun()
    with b4:
        if st.button("🚪 Sair", use_container_width=True):
            for k in ["tela", "aluno", "uid"]:
                if k in st.session_state: del st.session_state[k]
            st.session_state.tela = "login"; st.rerun()

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
            label_expander = f"📦 {mod_tit}  —  {feitas}/{total} ({pct}%)"

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
            st.markdown(f"<div class='{cls}'><div style='font-size:2rem'>{icone}</div><b>{nome}</b><br><small style='color:#999;'>{desc}</small><br><small>{status}</small></div>", unsafe_allow_html=True)

# =========================================================
# TELA: LIÇÃO
# =========================================================
elif st.session_state.tela == "licao":
    trilha = st.session_state.trilha
    idx = st.session_state.idx
    # Cada item: id, pergunta, o1, o2, o3, o4, correta, explicacao
    lic_id, pergunta, o1, o2, o3, o4, correta, explicacao = trilha[idx]

    # Tipo de exercício
    # Modo revisão: rotaciona MC, LISTEN, TYPE para mais variedade.
    # Modo normal: só MC (mais previsível para aprendizado inicial).
    if st.session_state.modo_revisao:
        tipo = ["mc", "listen", "type"][idx % 3]
    else:
        tipo = "mc"

    # Header
    c_sair, c_prog = st.columns([1, 4])
    with c_sair:
        if st.button("⬅️ Menu"):
            reset_para_inicio(); st.rerun()
    with c_prog:
        st.progress((idx + 1) / len(trilha))
        modo_label = "🧠 Revisão" if st.session_state.modo_revisao else "📘 Aprendizado"
        st.write(f"{modo_label} — Fase {idx + 1} de {len(trilha)}")

    st.markdown(f"### Vidas: {'❤️' * st.session_state.vidas}")

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
            st.markdown(f"<div class='premium-card'><h3>Traduza:</h3><h2 style='color:lime;'>{pergunta}</h2></div>", unsafe_allow_html=True)
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
            st.markdown(f"<div class='premium-card'><h3>Digite em inglês:</h3><h2 style='color:lime;'>{pergunta}</h2></div>", unsafe_allow_html=True)
            if not st.session_state.respondido:
                with st.form("form_type"):
                    resp = st.text_input("Sua resposta:", placeholder="Digite aqui...")
                    enviou = st.form_submit_button("Validar")
                    if enviou:
                        if not resp.strip():
                            st.warning("Digite uma resposta.")
                        else:
                            # Comparação tolerante: minúsculas, sem espaços extras, sem pontuação no fim
                            limpa = lambda s: s.strip().lower().rstrip(".!?,;:")
                            acertou = limpa(resp) == limpa(correta)
                            processar_resposta(resp if acertou else resp, correta, lic_id, explicacao, forcar=acertou)
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
    for d_id, oponente, score_op, criado in pendentes:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"<div class='ranking-box' style='border-left-color:#FF5252;'><b>{oponente}</b> te desafiou! Acertou <b>{score_op}/{DUELO_QUESTOES}</b>.<br><small style='color:#999;'>{criado}</small></div>", unsafe_allow_html=True)
        with c2:
            if st.button("Aceitar ⚔️", key=f"aceitar_{d_id}", use_container_width=True):
                duelo = carregar_duelo(d_id)
                ids = json.loads(duelo[3])
                st.session_state.duelo_id = d_id
                st.session_state.duelo_modo = "desafiado"
                st.session_state.duelo_questoes = carregar_questoes(ids)
                st.session_state.duelo_idx = 0
                st.session_state.duelo_score = 0
                st.session_state.respondido = False
                st.session_state.opcoes_atuais = []
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
            st.markdown(f"<div class='ranking-box' style='border-left-color:#FFC97C;'>Aguardando <b>{oponente}</b>... Você acertou <b>{meu_score}/{DUELO_QUESTOES}</b>.<br><small style='color:#999;'>{criado}</small></div>", unsafe_allow_html=True)
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
            emoji, cor, status = "🏆", "lime", "Vitória"
        else:
            emoji, cor, status = "💀", "#FF5252", "Derrota"
        st.markdown(f"<div class='ranking-box' style='border-left-color:{cor};'>{emoji} <b>{status}</b> contra <b>{oponente}</b> — {meu_score} x {score_op}<br><small style='color:#999;'>{quando}</small></div>", unsafe_allow_html=True)

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
        st.markdown(f"<div class='ranking-box'><b>{nome_d}</b> &nbsp;|&nbsp; 🏆 {v_d} &nbsp;|&nbsp; 💀 {d_d} &nbsp;|&nbsp; 🤝 {e_d}</div>", unsafe_allow_html=True)

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
                st.caption(f"⚔️ Serão {DUELO_QUESTOES} questões aleatórias. Você joga primeiro, depois o oponente. Vencedor leva {DUELO_XP_VITORIA} XP, perdedor {DUELO_XP_DERROTA}, empate {DUELO_XP_EMPATE} cada.")
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
        # Acabou o duelo
        if st.session_state.duelo_modo == "desafiante":
            # Salva o duelo (1ª vez no DB)
            duelo_id = criar_duelo(
                uid,
                st.session_state.duelo_oponente_id,
                [q[0] for q in questoes],
                st.session_state.duelo_score
            )
            st.session_state.duelo_id = duelo_id
        else:
            # Finaliza o duelo (atualiza com score do desafiado)
            finalizar_duelo(st.session_state.duelo_id, st.session_state.duelo_score)
        st.session_state.tela = "duelo_resultado"
        st.rerun()
    else:
        q = questoes[idx]
        lic_id, pergunta, o1, o2, o3, o4, correta, explicacao = q

        c_sair, c_prog = st.columns([1, 4])
        with c_sair:
            modo_emoji = "⚔️" if st.session_state.duelo_modo == "desafiante" else "🛡️"
            st.markdown(f"### {modo_emoji} Duelo")
        with c_prog:
            st.progress((idx + 1) / len(questoes))
            st.write(f"Questão {idx + 1} de {len(questoes)} — Acertos: {st.session_state.duelo_score}")

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
                    st.markdown(f"<div style='background:#1B3A1B;border-left:4px solid lime;padding:10px;border-radius:6px;margin-bottom:10px;'>🔥 Você já garantiu pelo menos o empate!</div>", unsafe_allow_html=True)

        if not st.session_state.opcoes_atuais:
            ops = [o1, o2, o3, o4]
            random.shuffle(ops)
            st.session_state.opcoes_atuais = ops

        st.markdown(f"<div class='premium-card'><h3>Traduza:</h3><h2 style='color:lime;'>{pergunta}</h2></div>", unsafe_allow_html=True)

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
        d_id, des_id, dou_id, q_ids, sc_des, sc_dou, vencedor, status, criado, atualizado = duelo
        nome_des = consultar_um("SELECT nome FROM alunos WHERE id = ?", (des_id,))[0]
        nome_dou = consultar_um("SELECT nome FROM alunos WHERE id = ?", (dou_id,))[0]

        if status == "aguardando_desafiado":
            # Desafiante acabou de jogar, mas o outro ainda não respondeu
            st.markdown(f"""
            <div class='premium-card' style='text-align:center;'>
                <h1>⚔️ Desafio enviado!</h1>
                <h2 style='color:lime;'>{sc_des}/{len(json.loads(q_ids))}</h2>
                <p>Agora é só esperar <b>{nome_dou}</b> aceitar e responder.</p>
                <p>Você ganha XP só depois que ele jogar.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Finalizado
            if vencedor is None:
                emoji, titulo, cor = "🤝", "EMPATE!", "#FFC97C"
                msg = f"Vocês empataram com <b>{sc_des}</b> acertos cada."
            elif vencedor == uid:
                emoji, titulo, cor = "🏆", "VITÓRIA!", "lime"
                meu = sc_des if uid == des_id else sc_dou
                op = sc_dou if uid == des_id else sc_des
                op_nome = nome_dou if uid == des_id else nome_des
                msg = f"Você venceu <b>{op_nome}</b> por <b>{meu} a {op}</b>! +{DUELO_XP_VITORIA} XP"
            else:
                emoji, titulo, cor = "💀", "DERROTA", "#FF5252"
                meu = sc_des if uid == des_id else sc_dou
                op = sc_dou if uid == des_id else sc_des
                op_nome = nome_dou if uid == des_id else nome_des
                msg = f"<b>{op_nome}</b> venceu por <b>{op} a {meu}</b>. +{DUELO_XP_DERROTA} XP de consolação."

            st.markdown(f"""
            <div class='premium-card' style='text-align:center;border-color:{cor};'>
                <div style='font-size:4rem'>{emoji}</div>
                <h1 style='color:{cor};'>{titulo}</h1>
                <p style='font-size:1.1rem;'>{msg}</p>
                <p style='color:#8E8E93;'><b>{nome_des}</b> {sc_des} &nbsp;×&nbsp; {sc_dou} <b>{nome_dou}</b></p>
            </div>
            """, unsafe_allow_html=True)

            # Verificar novas conquistas
            verificar_conquistas(uid)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🥊 Voltar ao Lobby", use_container_width=True):
                st.session_state.tela = "duelo_lobby"
                st.session_state.duelo_id = None
                st.session_state.duelo_modo = None
                st.session_state.duelo_score = 0
                st.session_state.duelo_questoes = []
                st.session_state.duelo_idx = 0
                st.rerun()
        with c2:
            if st.button("🏠 Menu Principal", use_container_width=True):
                reset_para_inicio(); st.rerun()

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
            st.markdown(f"<div class='badge-card' style='border-color:lime;'><div style='font-size:2rem'>{icone}</div><b>{nome}</b><br><small>{desc}</small></div>", unsafe_allow_html=True)
    if st.button("Voltar ao Menu"):
        st.session_state.conquistas_novas = []
        reset_para_inicio(); st.rerun()