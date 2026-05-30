import streamlit as st
import sqlite3

st.set_page_config(page_title="Holy English Academy", layout="wide")

# --- BANCO DE DADOS ---
def conectar(): return sqlite3.connect('banco_ingles.db')

def iniciar_banco():
    con = conectar(); cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS alunos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, xp_total INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS modulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL)')
    cur.execute('CREATE TABLE IF NOT EXISTS licoes (id INTEGER PRIMARY KEY AUTOINCREMENT, modulo_id INTEGER, titulo_botao TEXT, pergunta TEXT, opcao_1 TEXT, opcao_2 TEXT, opcao_3 TEXT, resposta_correta TEXT)')
    con.commit(); con.close()

iniciar_banco()

# --- ESTADO DE SESSÃO ---
if "tela" not in st.session_state: st.session_state.tela = "login"

# --- SIDEBAR PROFESSOR (ACESSO TOTAL) ---
with st.sidebar:
    st.title("👨‍🏫 Professor")
    if st.text_input("Senha Admin:", type="password") == "igreja123":
        if st.button("Painel de Gestão"): st.session_state.tela = "admin"
    if st.button("Voltar ao Início"): st.session_state.tela = "inicio"

# --- TELAS ---
if st.session_state.tela == "login":
    st.title("🎓 Holy English Academy")
    nome = st.text_input("Seu nome:")
    if st.button("Entrar"):
        st.session_state.aluno = nome
        con = conectar(); cur = con.cursor()
        cur.execute("SELECT id FROM alunos WHERE nome = ?", (nome,))
        res = cur.fetchone()
        if not res: cur.execute("INSERT INTO alunos (nome) VALUES (?)", (nome,))
        st.session_state.uid = cur.execute("SELECT id FROM alunos WHERE nome = ?", (nome,)).fetchone()[0]
        con.commit(); con.close()
        st.session_state.tela = "inicio"; st.rerun()

elif st.session_state.tela == "admin":
    st.title("⚙️ Painel de Gestão")
    t1, t2, t3 = st.tabs(["📁 Módulos", "📝 Gerenciar Aulas", "👥 Alunos"])
    
    with t1:
        tit_mod = st.text_input("Nome do Novo Módulo")
        if st.button("Salvar Módulo"): conectar().execute("INSERT INTO modulos (titulo) VALUES (?)", (tit_mod,)).connection.commit(); st.rerun()
        st.write("### Módulos Existentes:")
        for mod in conectar().execute("SELECT id, titulo FROM modulos").fetchall():
            if st.button(f"🗑️ Excluir Módulo: {mod[1]}", key=f"del_m{mod[0]}"):
                conectar().execute("DELETE FROM modulos WHERE id = ?", (mod[0],)).connection.commit(); st.rerun()

    with t2:
        mods = conectar().execute("SELECT id, titulo FROM modulos").fetchall()
        if mods:
            m_id = st.selectbox("Selecione o Módulo", options=[m[0] for m in mods], format_func=lambda x: [m[1] for m in mods if m[0] == x][0])
            with st.expander("Nova Aula"):
                tit = st.text_input("Título"); per = st.text_input("Pergunta"); o1 = st.text_input("Opção 1"); o2 = st.text_input("Opção 2"); o3 = st.text_input("Opção 3")
                resp = st.selectbox("Correta", [o1, o2, o3])
                if st.button("Salvar Aula"): conectar().execute("INSERT INTO licoes (modulo_id, titulo_botao, pergunta, opcao_1, opcao_2, opcao_3, resposta_correta) VALUES (?,?,?,?,?,?,?)", (m_id, tit, per, o1, o2, o3, resp)).connection.commit(); st.rerun()
            st.write("### Aulas:")
            for l in conectar().execute("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ?", (m_id,)).fetchall():
                c1, c2 = st.columns([4, 1])
                c1.write(l[1])
                if c2.button("❌ Excluir", key=f"d{l[0]}"): conectar().execute("DELETE FROM licoes WHERE id = ?", (l[0],)).connection.commit(); st.rerun()

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
        for i, row in enumerate(conectar().execute("SELECT nome, xp_total FROM alunos ORDER BY xp_total DESC LIMIT 5").fetchall()):
            st.markdown(f"**{i+1}. {row[0]}** - {row[1]} XP")

elif st.session_state.tela == "licao":
    l = conectar().execute("SELECT pergunta, opcao_1, opcao_2, opcao_3, resposta_correta FROM licoes WHERE id = ?", (st.session_state.l_atual,)).fetchone()
    st.write(f"### {l[0]}")
    res = st.radio("Escolha:", [l[1], l[2], l[3]], index=None)
    
    if st.button("Verificar"):
        if res == l[4]:
            conectar().execute("UPDATE alunos SET xp_total = xp_total + 20 WHERE id = ?", (st.session_state.uid,)).connection.commit()
            st.success("✅ Resposta Correta! Você ganhou 20 XP.")
        else: st.error("❌ Resposta incorreta. Tente novamente!")
        
        if st.button("Continuar / Voltar"): st.session_state.tela = "inicio"; st.rerun()