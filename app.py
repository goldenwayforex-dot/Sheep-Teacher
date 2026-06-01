import streamlit as st
import sqlite3
import random

# --- CONFIGURAÇÃO DA INTERFACE ---
st.set_page_config(page_title="Sheep Teacher - Bethany Church", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Trebuchet MS', sans-serif !important; background-color: #0A0A0C; }
    .premium-card { background: linear-gradient(145deg, #121216, #1A1A22); padding: 35px; border-radius: 16px; border: 1px solid #2A2A35; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }
    .ranking-box { background: #111115; padding: 15px; border-radius: 12px; border-left: 4px solid lime; margin-bottom: 12px; border: 1px solid #222; }
    .stButton>button { background-color: #111115; color: #FFFFFF; border: 2px solid lime; border-radius: 12px; font-weight: bold; height: 52px; width: 100%; transition: all 0.3s; }
    .stButton>button:hover { background-color: lime; color: #000000; box-shadow: 0 0 20px rgba(0, 255, 0, 0.5); transform: translateY(-2px); }
    .titulo-principal { font-size: 3rem; font-weight: 800; background: linear-gradient(90deg, #FFFFFF, #8E8E93); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .destaque-lime { color: lime; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
def conectar(): return sqlite3.connect('banco_ingles.db')

def exibir_ranking():
    st.markdown("#### 🏆 TOP 5 GERAL")
    for r in conectar().execute("SELECT nome, xp_total FROM alunos ORDER BY xp_total DESC LIMIT 5").fetchall():
        st.markdown(f"<div class='ranking-box'><b>{r[0]}</b> - {r[1]} XP</div>", unsafe_allow_html=True)

def iniciar_banco():
    con = conectar(); cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS alunos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, xp_total INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS modulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL)')
    cur.execute('CREATE TABLE IF NOT EXISTS licoes (id INTEGER PRIMARY KEY AUTOINCREMENT, modulo_id INTEGER, titulo_botao TEXT, pergunta TEXT, opcao_1 TEXT, opcao_2 TEXT, opcao_3 TEXT, resposta_correta TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS progresso (aluno_id INTEGER, licao_id INTEGER, PRIMARY KEY (aluno_id, licao_id))')
    
    cur.execute("SELECT COUNT(*) FROM modulos")
    if cur.fetchone()[0] == 0:
        trilha = [
            ("Módulo 1: To Be - Presente", [("Fase 1", "Como se diz 'Eu sou um professor'?", "I am a teacher", "I is a teacher", "I are a teacher"), ("Fase 2", "Ela é minha irmã", "She is my sister", "She was my sister", "She seria my sister"), ("Fase 3", "Nós estamos felizes", "We are happy", "We am happy", "We is happy"), ("Fase 4", "Eles estão em casa", "They are at home", "They was at home", "They be at home"), ("Fase 5", "Ele é inteligente", "He is smart", "He are smart", "He am smart"), ("Fase 6", "É um dia lindo", "It is a beautiful day", "It was a beautiful day", "It be a beautiful day"), ("Fase 7", "Você está atrasado", "You are late", "You is late", "You am late"), ("Fase 8", "Eu estou com fome", "I am hungry", "I was hungry", "I be hungry")]),
            ("Módulo 2: To Be - Negativo", [("Fase 1", "Eu não estou cansado", "I am not tired", "I don't am tired", "I not am tired"), ("Fase 2", "Você não está pronto", "You are not ready", "You don't ready", "You no ready"), ("Fase 3", "Ele não é o gerente", "He is not the manager", "He not is the manager", "He are not the manager"), ("Fase 4", "Ela não é minha amiga", "She is not my friend", "She not is my friend", "She are not my friend"), ("Fase 5", "Nós não estamos atrasados", "We are not late", "We not are late", "We isn't late"), ("Fase 6", "Eles não estão aqui", "They are not here", "They not are here", "They isn't here"), ("Fase 7", "Não está funcionando", "It is not working", "It not is working", "It don't is working"), ("Fase 8", "Eu não estou errado", "I am not wrong", "I not am wrong", "I don't am wrong")]),
            ("Módulo 3: To Be - Passado", [("Fase 1", "Eu estava no parque", "I was at the park", "I were at the park", "I am at the park"), ("Fase 2", "Eles eram amigos", "They were friends", "They was friends", "They are friends"), ("Fase 3", "Ela estava feliz", "She was happy", "She were happy", "She is happy"), ("Fase 4", "Nós estávamos lá", "We were there", "We was there", "We are there"), ("Fase 5", "Ele era um ótimo jogador", "He was a great player", "He were a great player", "He is a great player"), ("Fase 6", "Foi uma festa legal", "It was a nice party", "It were a nice party", "It is a nice party"), ("Fase 7", "Você estava certo", "You were right", "You was right", "You are right"), ("Fase 8", "Eu estava pronto", "I was ready", "I were ready", "I am ready")]),
            ("Módulo 4: To Be - Futuro", [("Fase 1", "Eu estarei lá", "I will be there", "I would be there", "I was there"), ("Fase 2", "Ela será médica", "She will be a doctor", "She would be a doctor", "She was a doctor"), ("Fase 3", "Nós estaremos ocupados", "We will be busy", "We would be busy", "We are busy"), ("Fase 4", "Eles estarão felizes", "They will be happy", "They would be happy", "They were happy"), ("Fase 5", "Ele estará em casa", "He will be at home", "He would be at home", "He is at home"), ("Fase 6", "Será divertido", "It will be fun", "It would be fun", "It was fun"), ("Fase 7", "Você estará pronto", "You will be ready", "You would be ready", "You are ready"), ("Fase 8", "Eu estarei lá", "I will be there", "I would be there", "I was there")]),
            ("Módulo 5: Dias da Semana", [("Fase 1", "Segunda-feira", "Monday", "Tuesday", "Wednesday"), ("Fase 2", "Terça-feira", "Tuesday", "Monday", "Thursday"), ("Fase 3", "Quarta-feira", "Wednesday", "Friday", "Sunday"), ("Fase 4", "Quinta-feira", "Thursday", "Saturday", "Monday"), ("Fase 5", "Sexta-feira", "Friday", "Wednesday", "Tuesday"), ("Fase 6", "Sábado", "Saturday", "Sunday", "Thursday"), ("Fase 7", "Domingo", "Sunday", "Monday", "Friday"), ("Fase 8", "Fim de semana", "Weekend", "Weekday", "Day off")]),
            ("Módulo 6: Números 1-30", [(f"Fase {i}", f"{i}", f"{['One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen','Twenty','Twenty-one','Twenty-two','Twenty-three','Twenty-four','Twenty-five','Twenty-six','Twenty-seven','Twenty-eight','Twenty-nine','Thirty'][i-1]}", "Wrong", "Wrong") for i in range(1, 31)]),
            ("Módulo 7: Cores", [("Fase 1", "Vermelho", "Red", "Blue", "Green"), ("Fase 2", "Azul", "Blue", "Red", "Yellow"), ("Fase 3", "Amarelo", "Yellow", "Green", "White"), ("Fase 4", "Verde", "Green", "Black", "Purple"), ("Fase 5", "Branco", "White", "Orange", "Red"), ("Fase 6", "Preto", "Black", "Blue", "Yellow"), ("Fase 7", "Roxo", "Purple", "Green", "White"), ("Fase 8", "Laranja", "Orange", "Red", "Blue"), ("Fase 9", "Cinza", "Grey", "Brown", "Gold"), ("Fase 10", "Rosa", "Pink", "Silver", "Brown")]),
            ("Módulo 8: Termos da Igreja", [("Fase 1", "Deus", "God", "Bible", "Church"), ("Fase 2", "Bíblia", "Bible", "God", "Pastor"), ("Fase 3", "Espírito Santo", "Holy Spirit", "Faith", "Gospel"), ("Fase 4", "Igreja", "Church", "Prayer", "Bible"), ("Fase 5", "Oração", "Prayer", "Pastor", "God"), ("Fase 6", "Pastor", "Pastor", "Faith", "Church"), ("Fase 7", "Fé", "Faith", "Gospel", "Prayer"), ("Fase 8", "Evangelho", "Gospel", "Holy Spirit", "Bible"), ("Fase 9", "Graça", "Grace", "Sin", "Mercy"), ("Fase 10", "Salvação", "Salvation", "Grace", "Faith"), ("Fase 11", "Pecado", "Sin", "Mercy", "Grace"), ("Fase 12", "Misericórdia", "Mercy", "Salvation", "Praise"), ("Fase 13", "Adoração", "Worship", "Sermon", "Bible"), ("Fase 14", "Sermão", "Sermon", "Worship", "Prayer")]),
            ("Módulo 9: Saudações e Diálogos", [("Fase 1", "Olá, como vai?", "Hello, how are you?", "Hi, what is up?", "Hey, how is it?"), ("Fase 2", "Qual é o seu nome?", "What is your name?", "What is the name?", "Who is your name?"), ("Fase 3", "Meu nome é...", "My name is...", "I name is...", "The name is..."), ("Fase 4", "Prazer em conhecer você", "Nice to meet you", "Nice to know you", "Good to meet"), ("Fase 5", "Bom dia", "Good morning", "Good day", "Good night"), ("Fase 6", "Boa noite", "Good evening", "Good night", "Good day"), ("Fase 7", "De onde você é?", "Where are you from?", "Where are you?", "From where you?"), ("Fase 8", "Eu sou do Brasil", "I am from Brazil", "I from Brazil", "I am Brazil")])
        ]
        for tit, licoes in trilha:
            cur.execute("INSERT INTO modulos (titulo) VALUES (?)", (tit,))
            mid = cur.lastrowid
            for l in licoes: cur.execute("INSERT INTO licoes (modulo_id, titulo_botao, pergunta, opcao_1, opcao_2, opcao_3, resposta_correta) VALUES (?,?,?,?,?,?,?)", (mid, l[0], l[1], l[2], l[3], l[4], l[2]))
    con.commit(); con.close()

iniciar_banco()

# --- ESTADOS ---
if "tela" not in st.session_state: st.session_state.tela = "login"
if "vidas" not in st.session_state: st.session_state.vidas = 3
if "respondido" not in st.session_state: st.session_state.respondido = False
if "opcoes_atuais" not in st.session_state: st.session_state.opcoes_atuais = []

# --- TELA: LOGIN ---
if st.session_state.tela == "login":
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div class='premium-card' style='text-align: center;'><h1 class='titulo-principal'>Sheep Teacher</h1></div>", unsafe_allow_html=True)
        exibir_ranking()
        st.divider()
        nome = st.text_input("Identificação:")
        if st.button("Acessar 🚀", use_container_width=True):
            if nome: 
                st.session_state.aluno = nome
                con = conectar(); cur = con.cursor()
                cur.execute("SELECT id FROM alunos WHERE nome = ?", (nome,))
                res = cur.fetchone()
                st.session_state.uid = res[0] if res else cur.execute("INSERT INTO alunos (nome) VALUES (?)", (nome,)).lastrowid
                con.commit(); con.close()
                st.session_state.tela = "inicio"; st.rerun()

# --- TELA: MAPA ---
elif st.session_state.tela == "inicio":
    st.markdown(f"### Bem-vindo, {st.session_state.aluno}!", unsafe_allow_html=True)
    c_main, c_rank = st.columns([3, 1])
    
    with c_main:
        for mod in conectar().execute("SELECT id, titulo FROM modulos").fetchall():
            with st.expander(f"📦 {mod[1]}"):
                licoes = conectar().execute("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ?", (mod[0],)).fetchall()
                cols = st.columns(len(licoes) if len(licoes) < 5 else 5)
                for i, lic in enumerate(licoes):
                    con = conectar()
                    passou_anterior = con.execute("SELECT 1 FROM progresso WHERE aluno_id = ? AND licao_id = ?", (st.session_state.uid, licoes[i-1][0])).fetchone() if i > 0 else True
                    ja_fez = con.execute("SELECT 1 FROM progresso WHERE aluno_id = ? AND licao_id = ?", (st.session_state.uid, lic[0])).fetchone()
                    con.close()
                    
                    with cols[i % 5]:
                        if ja_fez:
                            st.button(f"✅ {lic[1]}", key=f"btn_check_{lic[0]}")
                        elif i > 0 and not passou_anterior:
                            st.button(f"🔒 {lic[1]}", key=f"btn_lock_{lic[0]}", disabled=True)
                        else:
                            if st.button(f"🎯 {lic[1]}", key=f"btn_{lic[0]}"):
                                st.session_state.trilha = conectar().execute("SELECT id, pergunta, opcao_1, opcao_2, opcao_3, resposta_correta FROM licoes WHERE modulo_id = ?", (mod[0],)).fetchall()
                                st.session_state.idx = i
                                st.session_state.vidas = 3
                                st.session_state.respondido = False
                                st.session_state.opcoes_atuais = []
                                st.session_state.tela = "licao"; st.rerun()
                                
    with c_rank:
        exibir_ranking()

# --- TELA: LIÇÃO ---
elif st.session_state.tela == "licao":
    trilha = st.session_state.trilha
    idx = st.session_state.idx
    lic_id, pergunta, o1, o2, o3, correta = trilha[idx]
    
    c_sair, c_prog = st.columns([1, 4])
    with c_sair:
        if st.button("⬅️ Menu Principal"): st.session_state.tela = "inicio"; st.rerun()
    with c_prog:
        st.progress((idx + 1) / len(trilha))
        st.write(f"Fase {idx + 1} de {len(trilha)}")
    
    st.markdown(f"### Vidas: {'❤️' * st.session_state.vidas}")
    
    if not st.session_state.opcoes_atuais:
        ops = [o1, o2, o3]
        random.shuffle(ops)
        st.session_state.opcoes_atuais = ops

    if st.session_state.vidas <= 0:
        st.error("Game Over!")
        if st.button("Voltar ao Mapa"): st.session_state.tela = "inicio"; st.rerun()
    else:
        st.markdown(f"<div class='premium-card'><h3>{pergunta}</h3></div>", unsafe_allow_html=True)
        if not st.session_state.respondido:
            with st.form("pergunta_form"):
                resp = st.radio("Selecione:", st.session_state.opcoes_atuais, index=None)
                if st.form_submit_button("Validar"):
                    if not resp: st.warning("Escolha uma!"); st.rerun()
                    if resp == correta:
                        st.session_state.feedback = "✅ Correto! +10 XP"
                        conectar().execute("UPDATE alunos SET xp_total = xp_total + 10 WHERE id = ?", (st.session_state.uid,)).connection.commit()
                        conectar().execute("INSERT OR IGNORE INTO progresso VALUES (?,?)", (st.session_state.uid, lic_id)).connection.commit()
                    else:
                        st.session_state.vidas -= 1
                        st.session_state.feedback = f"❌ Errado! A correta era: {correta}"
                    st.session_state.respondido = True
                    st.rerun()
        else:
            st.write(st.session_state.feedback)
            if st.button("Avançar"):
                if idx + 1 < len(trilha):
                    st.session_state.idx += 1
                    st.session_state.respondido = False
                    st.session_state.opcoes_atuais = []
                    st.rerun()
                else:
                    st.session_state.tela = "conclusao_trilha"; st.rerun()

elif st.session_state.tela == "conclusao_trilha":
    st.markdown("<div class='premium-card' style='text-align: center;'><h1>🎉 Módulo Concluído!</h1></div>", unsafe_allow_html=True)
    if st.button("Voltar ao Mapa"): st.session_state.tela = "inicio"; st.rerun()