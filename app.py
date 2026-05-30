import streamlit as st
import sqlite3

# --- BANCO DE DADOS ---
st.set_page_config(page_title="Holy English Academy", layout="wide")

def conectar(): return sqlite3.connect('banco_ingles.db')

def iniciar_banco():
    con = conectar(); cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS alunos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, xp_total INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS modulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL)')
    cur.execute('CREATE TABLE IF NOT EXISTS licoes (id INTEGER PRIMARY KEY AUTOINCREMENT, modulo_id INTEGER, titulo_botao TEXT, pergunta TEXT, opcao_1 TEXT, opcao_2 TEXT, opcao_3 TEXT, resposta_correta TEXT)')
    con.commit(); con.close()

iniciar_banco()

# --- ESTADO ---
if "tela" not in st.session_state: st.session_state.tela = "login"

# --- SIDEBAR PROFESSOR ---
with st.sidebar:
    st.title("👨‍🏫 Professor")
    if st.text_input("Senha Admin:", type="password") == "igreja123":
        if st.button("Painel de Gestão"): st.session_state.tela = "admin"
    if st.button("Voltar ao Início"): st.session_state.tela = "inicio"; st.rerun()

# --- TELAS ---
if st.session_state.tela == "login":
    st.markdown("""
        <style>
        .login-card { background-color: #1a1a1a; padding: 40px; border-radius: 20px; border: 1px solid #333; text-align: center; }
        </style>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div class='login-card'><h1>Holy English</h1><p>A jornada começa aqui.</p></div>", unsafe_allow_html=True)
        nome = st.text_input("Identificação do Aluno", placeholder="Digite seu nome...")
        if st.button("Acessar Academy", use_container_width=True):
            if nome:
                con = conectar(); cur = con.cursor()
                cur.execute("SELECT id FROM alunos WHERE nome = ?", (nome,))
                res = cur.fetchone()
                if not res: cur.execute("INSERT INTO alunos (nome) VALUES (?)", (nome,))
                st.session_state.uid = cur.execute("SELECT id FROM alunos WHERE nome = ?", (nome,)).fetchone()[0]
                st.session_state.aluno = nome
                con.commit(); con.close()
                st.session_state.tela = "inicio"; st.rerun()

elif st.session_state.tela == "admin":
    st.title("⚙️ Painel de Gestão")
    t1, t2, t3 = st.tabs(["📁 Módulos", "📝 Criar/Excluir Aulas", "👥 Alunos"])
    with t1:
        tit = st.text_input("Nome do Módulo")
        if st.button("Salvar Módulo"): conectar().execute("INSERT INTO modulos (titulo) VALUES (?)", (tit,)).connection.commit(); st.rerun()
    with t2:
        mods = conectar().execute("SELECT id, titulo FROM modulos").fetchall()
        if mods:
            mid = st.selectbox("Escolha o Módulo:", options=[m[0] for m in mods], format_func=lambda x: [m[1] for m in mods if m[0] == x][0])
            with st.expander("Nova Aula"):
                tit = st.text_input("Título"); per = st.text_input("Pergunta"); o1 = st.text_input("Opção 1"); o2 = st.text_input("Opção 2"); o3 = st.text_input("Opção 3")
                resp = st.selectbox("Correta", [o1, o2, o3])
                if st.button("Salvar Aula"): conectar().execute("INSERT INTO licoes (modulo_id, titulo_botao, pergunta, opcao_1, opcao_2, opcao_3, resposta_correta) VALUES (?,?,?,?,?,?,?)", (mid, tit, per, o1, o2, o3, resp)).connection.commit(); st.rerun()
            for l in conectar().execute("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ?", (mid,)).fetchall():
                c1, c2 = st.columns([4, 1])
                c1.write(l[1])
                if c2.button("❌", key=f"d{l[0]}"): conectar().execute("DELETE FROM licoes WHERE id = ?", (l[0],)).connection.commit(); st.rerun()
    with t3:
        st.table(conectar().execute("SELECT nome, xp_total FROM alunos ORDER BY xp_total DESC").fetchall())

elif st.session_state.tela == "inicio":
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title(f"Bem-vindo, {st.session_state.aluno}!")
        for m in conectar().execute("SELECT id, titulo FROM modulos").fetchall():
            with st.expander(m[1], expanded=True):
                for l in conectar().execute("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ?", (m[0],)).fetchall():
                    if st.button(l[1], key=f"a{l[0]}"): st.session_state.l_atual = l[0]; st.session_state.tela = "licao"; st.rerun()
    with c2:
        st.write("### 🏆 Top 5")
        for i, r in enumerate(conectar().execute("SELECT nome, xp_total FROM alunos ORDER BY xp_total DESC LIMIT 5").fetchall()):
            st.write(f"{i+1}. {r[0]} ({r[1]} XP)")

elif st.session_state.tela == "licao":
    d = conectar().execute("SELECT pergunta, opcao_1, opcao_2, opcao_3, resposta_correta FROM licoes WHERE id = ?", (st.session_state.l_atual,)).fetchone()
    st.write(f"### {d[0]}")
    res = st.radio("Escolha:", [d[1], d[2], d[3]], index=None)
    if "verificado" not in st.session_state: st.session_state.verificado = False
    if st.button("Verificar"):
        if res == d[4]:
            conectar().execute("UPDATE alunos SET xp_total = xp_total + 20 WHERE id = ?", (st.session_state.uid,)).connection.commit()
            st.success("✅ Correto! Você ganhou 20 XP."); st.session_state.verificado = True
        else: st.error("❌ Errado! Tente de novo.")
    if st.session_state.get("verificado"):
        if st.button("Continuar"): st.session_state.verificado = False; st.session_state.tela = "inicio"; st.rerun()
    if st.button("Voltar ao Menu"): st.session_state.verificado = False; st.session_state.tela = "inicio"; st.rerun()