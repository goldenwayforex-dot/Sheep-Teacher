import streamlit as st
import sqlite3

# --- CONFIGURAÇÃO DA INTERFACE VISUAL PREMIUM (LAYOUT AMPLO) ---
st.set_page_config(page_title="Sheep Teacher - Bethany Church", layout="wide", initial_sidebar_state="collapsed")

# Estilização sob medida (Dark Mode Avançado + Elementos Neon)
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Trebuchet MS', sans-serif !important;
        background-color: #0A0A0C;
    }
    
    /* Cartões de Conteúdo Relevante */
    .premium-card {
        background: linear-gradient(145deg, #121216, #1A1A22);
        padding: 35px;
        border-radius: 16px;
        border: 1px solid #2A2A35;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }
    
    /* Painéis Laterais do Top 5 */
    .ranking-box {
        background: #111115;
        padding: 15px;
        border-radius: 12px;
        border-left: 4px solid lime;
        margin-bottom: 12px;
        border-top: 1px solid #222;
        border-right: 1px solid #222;
        border-bottom: 1px solid #222;
    }
    
    /* Botões Padrão e de Fases (Estilo Duolingo Stepping Stones) */
    .stButton>button {
        background-color: #111115;
        color: #FFFFFF;
        border: 2px solid lime;
        border-radius: 12px;
        font-weight: bold;
        height: 52px;
        width: 100%;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stButton>button:hover {
        background-color: lime;
        color: #000000;
        box-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
        transform: translateY(-2px);
    }
    
    /* Customização para botões desabilitados/bloqueados */
    .stButton>button:disabled {
        background-color: #1A1A22 !important;
        color: #555566 !important;
        border: 2px solid #333344 !important;
        box-shadow: none !important;
        transform: none !important;
    }
    
    /* Botões de Alerta / Cancelamento */
    .btn-perigo>button {
        border: 2px solid #FF3B30 !important;
        color: #FF3B30 !important;
    }
    .btn-perigo>button:hover {
        background-color: #FF3B30 !important;
        color: white !important;
        box-shadow: 0 0 20px rgba(255, 59, 48, 0.5) !important;
    }
    
    .titulo-principal {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FFFFFF, #8E8E93);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    .destaque-lime { color: lime; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- ARQUITETURA DO BANCO DE DADOS LOCAL ---
def conectar(): return sqlite3.connect('banco_ingles.db')

def iniciar_banco():
    con = conectar(); cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS alunos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, xp_total INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS modulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL)')
    cur.execute('CREATE TABLE IF NOT EXISTS licoes (id INTEGER PRIMARY KEY AUTOINCREMENT, modulo_id INTEGER, titulo_botao TEXT, pergunta TEXT, opcao_1 TEXT, opcao_2 TEXT, opcao_3 TEXT, resposta_correta TEXT)')
    # Tabela essencial para rastrear quais fases cada aluno já concluiu
    cur.execute('CREATE TABLE IF NOT EXISTS progresso (aluno_id INTEGER, licao_id INTEGER, PRIMARY KEY (aluno_id, licao_id))')
    con.commit(); con.close()

iniciar_banco()

# --- VARIÁVEIS DE CONTROLE DE FLUXO ---
if "tela" not in st.session_state: st.session_state.tela = "login"
if "trilha_licoes" not in st.session_state: st.session_state.trilha_licoes = []
if "trilha_index" not in st.session_state: st.session_state.trilha_index = 0
if "respondido_sucesso" not in st.session_state: st.session_state.respondido_sucesso = False

# --- PORTAL DE ACESSO DO PROFESSOR (SIDEBAR) ---
with st.sidebar:
    st.markdown("### 👨‍🏫 Controle Docente")
    if st.text_input("Acesso Administrativo:", type="password") == "igreja123":
        st.success("Acesso Autorizado!")
        if st.button("Abrir Central de Gestão"): 
            st.session_state.tela = "admin"
            st.rerun()
    st.divider()
    if st.button("Retornar à Área do Aluno"): 
        st.session_state.tela = "inicio"
        st.rerun()

# ===================================================
# TELA 1: ENTRADA REESTRUTURADA E CENTRALIZADA
# ===================================================
if st.session_state.tela == "login":
    st.write("")
    st.write("")
    c1, c2, c3 = st.columns([1, 1.8, 1])
    with c2:
        st.markdown("""
            <div class='premium-card' style='text-align: center;'>
                <h1 class='titulo-principal'>Sheep Teacher - Bethany Church</h1>
                <p style='color: #8E8E93; margin-bottom: 30px;'>A salvação do seu inglês chegou!</p>
            </div>
        """, unsafe_allow_html=True)
        
        nome = st.text_input("Identificação:", placeholder="Digite seu nome para acessar o mapa...", label_visibility="collapsed")
        st.write("")
        if st.button("Acessar Minhas Fases 🚀", use_container_width=True):
            if nome.strip():
                con = conectar(); cur = con.cursor()
                cur.execute("SELECT id FROM alunos WHERE nome = ?", (nome.strip(),))
                res = cur.fetchone()
                if not res: 
                    cur.execute("INSERT INTO alunos (nome) VALUES (?)", (nome.strip(),))
                    st.session_state.uid = cur.lastrowid
                else: 
                    st.session_state.uid = res[0]
                st.session_state.aluno = nome.strip()
                con.commit(); con.close()
                st.session_state.tela = "inicio"
                st.rerun()
            else:
                st.error("Insira o seu nome para carregar o seu mapa de fases.")

# ===================================================
# TELA 2: CENTRAL DE GESTÃO DO PROFESSOR
# ===================================================
elif st.session_state.tela == "admin":
    st.title("⚙️ Painel de Controle e Conteúdo")
    t1, t2, t3 = st.tabs(["📁 Módulos Estruturais", "📝 Banco de Exercícios", "👥 Relatório de Alunos"])
    
    with t1:
        tit_mod = st.text_input("Título do Novo Módulo:")
        if st.button("Criar Módulo"): 
            conectar().execute("INSERT INTO modulos (titulo) VALUES (?)", (tit_mod,)).connection.commit()
            st.success("Módulo salvo!")
            st.rerun()
        st.divider()
        st.write("#### Remover Módulos:")
        for mod in conectar().execute("SELECT id, titulo FROM modulos").fetchall():
            if st.button(f"🗑️ Excluir {mod[1]}", key=f"del_mod_{mod[0]}"):
                conectar().execute("DELETE FROM modulos WHERE id = ?", (mod[0],)).connection.commit()
                conectar().execute("DELETE FROM licoes WHERE modulo_id = ?", (mod[0],)).connection.commit()
                st.rerun()

    with t2:
        mods = conectar().execute("SELECT id, titulo FROM modulos").fetchall()
        if mods:
            mid = st.selectbox("Selecione o Módulo Alvo:", options=[m[0] for m in mods], format_func=lambda x: [m[1] for m in mods if m[0] == x][0])
            with st.expander("➕ Adicionar Nova Questão à Sequência", expanded=True):
                tit = st.text_input("Identificador da Aula (Ex: Fase 1)")
                per = st.text_input("Pergunta / Enunciado do Desafio")
                o1 = st.text_input("Alternativa A (Correta)")
                o2 = st.text_input("Alternativa B")
                o3 = st.text_input("Alternativa C")
                if st.button("Inserir Questão na Trilha"):
                    conectar().execute("INSERT INTO licoes (modulo_id, titulo_botao, pergunta, opcao_1, opcao_2, opcao_3, resposta_correta) VALUES (?,?,?,?,?,?,?)", (mid, tit, per, o1, o2, o3, o1)).connection.commit()
                    st.success("Questão acoplada com sucesso!")
                    st.rerun()
            st.write("#### Questões Cadastradas neste Módulo (Clique para remover):")
            for l in conectar().execute("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ?", (mid,)).fetchall():
                c1, c2 = st.columns([4, 1])
                c1.write(f"🔹 {l[1]}")
                if c2.button("Eliminar", key=f"del_lic_{l[0]}"):
                    conectar().execute("DELETE FROM licoes WHERE id = ?", (l[0],)).connection.commit()
                    st.rerun()

    with t3:
        st.write("### Desempenho Geral dos Alunos")
        st.table(conectar().execute("SELECT nome as 'Nome do Aluno', xp_total as 'Pontuação (XP)' FROM alunos ORDER BY xp_total DESC").fetchall())

# ===================================================
# TELA 3: MAPA DE ESTUDOS COM BLOQUEIO SEQUENCIAL
# ===================================================
elif st.session_state.tela == "inicio":
    col_main, col_rank = st.columns([3, 1])
    
    with col_main:
        st.markdown(f"### Seu progresso atual, <span class='destaque-lime'>{st.session_state.aluno}</span>! 🗺️", unsafe_allow_html=True)
        st.write("Complete as fases em ordem para desbloquear os próximos desafios da trilha:")
        st.write("")
        
        modulos = conectar().execute("SELECT id, titulo FROM modulos").fetchall()
        for mod in modulos:
            with st.expander(f"📦 {mod[1]}", expanded=True):
                licoes = conectar().execute("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ?", (mod[0],)).fetchall()
                
                if not licoes:
                    st.write("*Aulas em desenvolvimento para este nível...*")
                else:
                    # Renderiza o mapa de botões horizontais no estilo "fases"
                    cols = st.columns(len(licoes))
                    bloquear_restante = False
                    
                    for idx, lic in enumerate(licoes):
                        lic_id, lic_nome = lic
                        
                        # Verifica se esta lição específica já foi feita
                        con = conectar()
                        ja_completou = con.execute("SELECT 1 FROM progresso WHERE aluno_id = ? AND licao_id = ?", (st.session_state.uid, lic_id)).fetchone()
                        con.close()
                        
                        if ja_completou:
                            status_icone = "✅"
                            esta_bloqueada = False
                        elif not bloquear_restante:
                            status_icone = "🎯"  # É a fase atual onde ele parou
                            esta_bloqueada = False
                            bloquear_restante = True  # Todas as próximas ficam trancadas
                        else:
                            status_icone = "🔒"
                            esta_bloqueada = True
                        
                        with cols[idx]:
                            if st.button(f"{status_icone}\n{lic_nome}", key=f"btn_mapa_{lic_id}", disabled=esta_bloqueada):
                                # Ao clicar na fase ativa ou concluída, inicia o fluxo dali em diante
                                trilha = conectar().execute("SELECT id, pergunta, opcao_1, opcao_2, opcao_3, resposta_correta FROM licoes WHERE modulo_id = ?", (mod[0],)).fetchall()
                                st.session_state.trilha_licoes = trilha
                                st.session_state.trilha_index = idx
                                st.session_state.respondido_sucesso = False
                                st.session_state.tela = "licao"
                                st.rerun()

    with col_rank:
        st.markdown("#### 🏆 TOP 5 PERFORMANCE")
        for i, r in enumerate(conectar().execute("SELECT nome, xp_total FROM alunos ORDER BY xp_total DESC LIMIT 5").fetchall()):
            st.markdown(f"""
                <div class='ranking-box'>
                    <b>{i+1}º {r[0]}</b><br>
                    <span style='color: #8E8E93;'>Mestria: {r[1]} XP</span>
                </div>
            """, unsafe_allow_html=True)

# ===================================================
# TELA 4: MOTOR DUOLINGO RÍTMICO (PRÓXIMA FASE DIRETO)
# ===================================================
elif st.session_state.tela == "licao":
    trilha = st.session_state.trilha_licoes
    idx = st.session_state.trilha_index
    total_perguntas = len(trilha)
    
    st.write("")
    col_back, col_info = st.columns([1, 4])
    with col_back:
        st.markdown('<div class="btn-perigo">', unsafe_allow_html=True)
        if st.button("⬅️ Sair do Jogo"):
            st.session_state.tela = "inicio"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_info:
        # Barra de progresso baseada na quantidade de itens da sequência
        st.progress((idx) / total_perguntas)
        st.write(f"<p style='text-align: right; color:#8E8E93; margin:0;'>Fase {idx + 1} de {total_perguntas}</p>", unsafe_allow_html=True)
    
    st.divider()
    
    lic_id, pergunta, o1, o2, o3, correta = trilha[idx]
    alternativas = sorted([o1, o2, o3])
    
    st.markdown(f"<div class='premium-card'><h3>{pergunta}</h3></div>", unsafe_allow_html=True)
    st.write("")
    
    resposta_selecionada = st.radio("Selecione a resposta correta:", alternativas, index=None, key=f"play_{lic_id}")
    st.write("")
    
    if not st.session_state.respondido_sucesso:
        if st.button("Validar Resposta 🎯", use_container_width=True):
            if resposta_selecionada == correta:
                st.balloons()
                con = conectar()
                # Registra na tabela de progresso para salvar a fase concluída permanentemente
                con.execute("INSERT OR IGNORE INTO progresso (aluno_id, licao_id) VALUES (?, ?)", (st.session_state.uid, lic_id))
                con.execute("UPDATE alunos SET xp_total = xp_total + 20 WHERE id = ?", (st.session_state.uid,))
                con.commit(); con.close()
                st.session_state.respondido_sucesso = True
                st.rerun()
            elif resposta_selecionada is None:
                st.warning("Selecione uma das alternativas antes de verificar.")
            else:
                st.error("❌ Resposta incorreta. Revise os termos e tente de novo!")
    else:
        st.success("✨ Excelente! Você dominou este nível e faturou +20 XP.")
        # Fluxo contínuo: Avança imediatamente para a próxima pergunta da fila
        if st.button("Avançar para a Próxima Fase ➡️", use_container_width=True):
            st.session_state.respondido_sucesso = False
            if st.session_state.trilha_index + 1 < total_perguntas:
                st.session_state.trilha_index += 1
                st.rerun()
            else:
                st.session_state.tela = "conclusao_trilha"
                st.rerun()

# ===================================================
# TELA 5: TELA DE CELEBRAÇÃO DO MÓDULO CONCLUÍDO
# ===================================================
elif st.session_state.tela == "conclusao_trilha":
    st.write("")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
            <div class='premium-card' style='text-align: center;'>
                <h1 style='color: lime; font-size: 3.5rem;'>🎉 INCRÍVEL!</h1>
                <h3>Trilha Concluída com Sucesso</h3>
                <p style='color: #8E8E93; margin-top: 15px;'>Você completou a sequência de exercícios de ponta a ponta.</p>
                <h2 style='margin: 25px 0;'>🏆 Recompensas Atualizadas!</h2>
            </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Voltar ao Mapa de Fases", use_container_width=True):
            st.session_state.tela = "inicio"
            st.rerun()