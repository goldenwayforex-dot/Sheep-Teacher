import streamlit as st
import sqlite3
import random

# IMPORTANTE: Se você já tem o arquivo "banco_ingles.db" da versão antiga,
# delete-o antes de rodar esta nova versão (ou execute o script,
# que tenta migrar automaticamente).

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
    .audio-btn { background:#111115; color:#FFF; border:2px solid lime; border-radius:8px; padding:8px 16px; font-weight:bold; cursor:pointer; }
    </style>
""", unsafe_allow_html=True)

# --- HELPERS DE BANCO ---
DB_PATH = 'banco_ingles.db'

def conectar():
    return sqlite3.connect(DB_PATH)

def executar(query, params=()):
    """Executa INSERT/UPDATE/DELETE com commit e retorna lastrowid."""
    con = conectar()
    cur = con.execute(query, params)
    last = cur.lastrowid
    con.commit()
    con.close()
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

def exibir_ranking():
    st.markdown("#### 🏆 TOP 5 GERAL")
    for r in consultar("SELECT nome, xp_total FROM alunos ORDER BY xp_total DESC LIMIT 5"):
        st.markdown(f"<div class='ranking-box'><b>{r[0]}</b> - {r[1]} XP</div>", unsafe_allow_html=True)

def botao_audio(texto, key):
    """Usa o sintetizador de voz do navegador (grátis) para pronunciar o texto em inglês."""
    safe = texto.replace("'", " ").replace('"', " ")
    html = f"""
    <button class="audio-btn" onclick="
        const u = new SpeechSynthesisUtterance('{safe}');
        u.lang='en-US'; u.rate=0.9;
        speechSynthesis.cancel(); speechSynthesis.speak(u);
    ">🔊 Ouvir em inglês</button>
    """
    st.components.v1.html(html, height=60)

# --- TRILHA DE APRENDIZADO ---
# Formato de cada lição: (titulo_botao, pergunta_pt, correta_en, errada1, errada2, errada3)
TRILHA = [
    ("Módulo 1: To Be - Presente", [
        ("Fase 1", "Eu sou um professor", "I am a teacher", "I is a teacher", "I are a teacher", "I be a teacher"),
        ("Fase 2", "Ela é minha irmã", "She is my sister", "She was my sister", "She are my sister", "She be my sister"),
        ("Fase 3", "Nós estamos felizes", "We are happy", "We am happy", "We is happy", "We be happy"),
        ("Fase 4", "Eles estão em casa", "They are at home", "They was at home", "They be at home", "They is at home"),
        ("Fase 5", "Ele é inteligente", "He is smart", "He are smart", "He am smart", "He be smart"),
        ("Fase 6", "É um dia lindo", "It is a beautiful day", "It was a beautiful day", "It be a beautiful day", "It are a beautiful day"),
        ("Fase 7", "Você está atrasado", "You are late", "You is late", "You am late", "You be late"),
        ("Fase 8", "Eu estou com fome", "I am hungry", "I was hungry", "I be hungry", "I are hungry"),
    ]),
    ("Módulo 2: To Be - Negativo", [
        ("Fase 1", "Eu não estou cansado", "I am not tired", "I don't am tired", "I not am tired", "I no am tired"),
        ("Fase 2", "Você não está pronto", "You are not ready", "You don't ready", "You no ready", "You not are ready"),
        ("Fase 3", "Ele não é o gerente", "He is not the manager", "He not is the manager", "He are not the manager", "He don't is the manager"),
        ("Fase 4", "Ela não é minha amiga", "She is not my friend", "She not is my friend", "She are not my friend", "She don't is my friend"),
        ("Fase 5", "Nós não estamos atrasados", "We are not late", "We not are late", "We isn't late", "We don't are late"),
        ("Fase 6", "Eles não estão aqui", "They are not here", "They not are here", "They isn't here", "They am not here"),
        ("Fase 7", "Não está funcionando", "It is not working", "It not is working", "It don't is working", "It are not working"),
        ("Fase 8", "Eu não estou errado", "I am not wrong", "I not am wrong", "I don't am wrong", "I no am wrong"),
    ]),
    ("Módulo 3: To Be - Passado", [
        ("Fase 1", "Eu estava no parque", "I was at the park", "I were at the park", "I am at the park", "I be at the park"),
        ("Fase 2", "Eles eram amigos", "They were friends", "They was friends", "They are friends", "They is friends"),
        ("Fase 3", "Ela estava feliz", "She was happy", "She were happy", "She is happy", "She be happy"),
        ("Fase 4", "Nós estávamos lá", "We were there", "We was there", "We are there", "We be there"),
        ("Fase 5", "Ele era um ótimo jogador", "He was a great player", "He were a great player", "He is a great player", "He be a great player"),
        ("Fase 6", "Foi uma festa legal", "It was a nice party", "It were a nice party", "It is a nice party", "It be a nice party"),
        ("Fase 7", "Você estava certo", "You were right", "You was right", "You are right", "You be right"),
        ("Fase 8", "Eu estava pronto", "I was ready", "I were ready", "I am ready", "I be ready"),
    ]),
    ("Módulo 4: To Be - Futuro", [
        ("Fase 1", "Eu estarei lá", "I will be there", "I would be there", "I was there", "I be there"),
        ("Fase 2", "Ela será médica", "She will be a doctor", "She would be a doctor", "She was a doctor", "She is be a doctor"),
        ("Fase 3", "Nós estaremos ocupados", "We will be busy", "We would be busy", "We are busy", "We was busy"),
        ("Fase 4", "Eles estarão felizes", "They will be happy", "They would be happy", "They were happy", "They was happy"),
        ("Fase 5", "Ele estará em casa", "He will be at home", "He would be at home", "He is at home", "He was at home"),
        ("Fase 6", "Será divertido", "It will be fun", "It would be fun", "It was fun", "It are fun"),
        ("Fase 7", "Você estará pronto", "You will be ready", "You would be ready", "You are ready", "You was ready"),
        ("Fase 8", "Amanhã eu estarei trabalhando", "Tomorrow I will be working", "Tomorrow I would be working", "Tomorrow I was working", "Tomorrow I am working"),
    ]),
    ("Módulo 5: Dias da Semana", [
        ("Fase 1", "Segunda-feira", "Monday", "Tuesday", "Wednesday", "Sunday"),
        ("Fase 2", "Terça-feira", "Tuesday", "Monday", "Thursday", "Wednesday"),
        ("Fase 3", "Quarta-feira", "Wednesday", "Friday", "Sunday", "Tuesday"),
        ("Fase 4", "Quinta-feira", "Thursday", "Saturday", "Monday", "Friday"),
        ("Fase 5", "Sexta-feira", "Friday", "Wednesday", "Tuesday", "Saturday"),
        ("Fase 6", "Sábado", "Saturday", "Sunday", "Thursday", "Friday"),
        ("Fase 7", "Domingo", "Sunday", "Monday", "Friday", "Saturday"),
        ("Fase 8", "Fim de semana", "Weekend", "Weekday", "Day off", "Weeknight"),
    ]),
    ("Módulo 6: Números 1-20", [
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
    ("Módulo 7: Cores", [
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
    ("Módulo 8: Termos da Igreja", [
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
    ("Módulo 9: Saudações e Diálogos", [
        ("Fase 1", "Olá, como vai?", "Hello, how are you?", "Hi, what is up?", "Hey, how is it?", "Hello, how do you?"),
        ("Fase 2", "Qual é o seu nome?", "What is your name?", "What is the name?", "Who is your name?", "How is your name?"),
        ("Fase 3", "Meu nome é...", "My name is...", "I name is...", "The name is...", "Me name is..."),
        ("Fase 4", "Prazer em conhecer você", "Nice to meet you", "Nice to know you", "Good to meet", "Pleasure for meet you"),
        ("Fase 5", "Bom dia", "Good morning", "Good day", "Good night", "Good afternoon"),
        ("Fase 6", "Boa noite (despedida)", "Good night", "Good evening", "Good day", "Good morning"),
        ("Fase 7", "De onde você é?", "Where are you from?", "Where are you?", "From where you?", "Where you from?"),
        ("Fase 8", "Eu sou do Brasil", "I am from Brazil", "I from Brazil", "I am Brazil", "Me from Brazil"),
    ]),
    # --- NOVOS MÓDULOS ---
    ("Módulo 10: Pronomes Pessoais", [
        ("Fase 1", "Eu", "I", "Me", "My", "You"),
        ("Fase 2", "Você / Tu", "You", "He", "We", "Your"),
        ("Fase 3", "Ele", "He", "She", "It", "His"),
        ("Fase 4", "Ela", "She", "He", "Her", "Hers"),
        ("Fase 5", "Nós", "We", "They", "Us", "Our"),
        ("Fase 6", "Eles / Elas", "They", "We", "Them", "Those"),
        ("Fase 7", "Isso (objeto/animal)", "It", "He", "This", "That"),
        ("Fase 8", "Me / Mim (objeto)", "Me", "I", "My", "Mine"),
    ]),
    ("Módulo 11: Pronomes Possessivos", [
        ("Fase 1", "Meu / Minha", "My", "Me", "Mine", "I"),
        ("Fase 2", "Seu / Sua", "Your", "Yours", "You", "Yourself"),
        ("Fase 3", "Dele", "His", "Him", "He", "Hers"),
        ("Fase 4", "Dela", "Her", "Hers", "She", "His"),
        ("Fase 5", "Nosso / Nossa", "Our", "Ours", "Us", "We"),
        ("Fase 6", "Deles / Delas", "Their", "Theirs", "Them", "They"),
        ("Fase 7", "Esta é a minha Bíblia", "This is my Bible", "This is mine Bible", "This is me Bible", "This is I Bible"),
        ("Fase 8", "Aquele livro é dele", "That book is his", "That book is him", "That book is he", "That book is hers"),
    ]),
    ("Módulo 12: Família", [
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
    ("Módulo 13: Comida e Bebida", [
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
    ("Módulo 14: Partes do Corpo", [
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
    ("Módulo 15: Meses do Ano", [
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
    ("Módulo 16: Clima e Tempo", [
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
    ("Módulo 17: Question Words", [
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
    ("Módulo 18: Verbos Comuns (Infinitivo)", [
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
    ("Módulo 19: Frases de Oração", [
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
    ("Módulo 20: Frases Bíblicas Conhecidas", [
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
    ("Módulo 21: Adoração e Louvor", [
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
    ("Módulo 22: Preposições de Lugar", [
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

# --- INICIALIZAÇÃO DO BANCO ---
def iniciar_banco():
    con = conectar(); cur = con.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS alunos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, xp_total INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS modulos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL UNIQUE)')
    cur.execute('''CREATE TABLE IF NOT EXISTS licoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        modulo_id INTEGER,
        titulo_botao TEXT, pergunta TEXT,
        opcao_1 TEXT, opcao_2 TEXT, opcao_3 TEXT, opcao_4 TEXT,
        resposta_correta TEXT
    )''')
    cur.execute('CREATE TABLE IF NOT EXISTS progresso (aluno_id INTEGER, licao_id INTEGER, PRIMARY KEY (aluno_id, licao_id))')

    # Migração: adicionar coluna opcao_4 caso o banco antigo exista
    try:
        cur.execute("ALTER TABLE licoes ADD COLUMN opcao_4 TEXT")
        cur.execute("UPDATE licoes SET opcao_4 = 'None of the above' WHERE opcao_4 IS NULL")
    except sqlite3.OperationalError:
        pass  # coluna já existe

    # Inserir só módulos que ainda não existem (por título)
    for titulo, licoes in TRILHA:
        cur.execute("SELECT id FROM modulos WHERE titulo = ?", (titulo,))
        if cur.fetchone():
            continue
        cur.execute("INSERT INTO modulos (titulo) VALUES (?)", (titulo,))
        mid = cur.lastrowid
        for l in licoes:
            cur.execute(
                "INSERT INTO licoes (modulo_id, titulo_botao, pergunta, opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta) VALUES (?,?,?,?,?,?,?,?)",
                (mid, l[0], l[1], l[2], l[3], l[4], l[5], l[2])
            )
    con.commit(); con.close()

iniciar_banco()

# --- ESTADOS DA SESSÃO ---
for k, v in [("tela", "login"), ("vidas", 3), ("respondido", False), ("opcoes_atuais", [])]:
    if k not in st.session_state:
        st.session_state[k] = v

# --- TELA: LOGIN ---
if st.session_state.tela == "login":
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div class='premium-card' style='text-align: center;'><h1 class='titulo-principal'>Sheep Teacher</h1><p style='color:#8E8E93;'>Bethany Church English School</p></div>", unsafe_allow_html=True)
        exibir_ranking()
        st.divider()
        nome = st.text_input("Identificação:")
        if st.button("Acessar 🚀", use_container_width=True):
            if nome.strip():
                nome = nome.strip()
                st.session_state.aluno = nome
                res = consultar_um("SELECT id FROM alunos WHERE nome = ?", (nome,))
                if res:
                    st.session_state.uid = res[0]
                else:
                    st.session_state.uid = executar("INSERT INTO alunos (nome) VALUES (?)", (nome,))
                st.session_state.tela = "inicio"
                st.rerun()
            else:
                st.warning("Digite seu nome para acessar.")

# --- TELA: MAPA DE MÓDULOS ---
elif st.session_state.tela == "inicio":
    st.markdown(f"### Bem-vindo, {st.session_state.aluno}!", unsafe_allow_html=True)
    c_main, c_rank = st.columns([3, 1])

    with c_main:
        modulos = consultar("SELECT id, titulo FROM modulos ORDER BY id")
        for mod in modulos:
            with st.expander(f"📦 {mod[1]}"):
                licoes = consultar("SELECT id, titulo_botao FROM licoes WHERE modulo_id = ? ORDER BY id", (mod[0],))
                if not licoes:
                    continue
                num_cols = min(len(licoes), 5)
                cols = st.columns(num_cols)
                for i, lic in enumerate(licoes):
                    # i > 0 -> precisa ter passado a lição anterior
                    if i > 0:
                        passou_anterior = consultar_um(
                            "SELECT 1 FROM progresso WHERE aluno_id = ? AND licao_id = ?",
                            (st.session_state.uid, licoes[i-1][0])
                        )
                    else:
                        passou_anterior = True
                    ja_fez = consultar_um(
                        "SELECT 1 FROM progresso WHERE aluno_id = ? AND licao_id = ?",
                        (st.session_state.uid, lic[0])
                    )

                    with cols[i % num_cols]:
                        if ja_fez:
                            st.button(f"✅ {lic[1]}", key=f"btn_check_{lic[0]}")
                        elif i > 0 and not passou_anterior:
                            st.button(f"🔒 {lic[1]}", key=f"btn_lock_{lic[0]}", disabled=True)
                        else:
                            if st.button(f"🎯 {lic[1]}", key=f"btn_{lic[0]}"):
                                st.session_state.trilha = consultar(
                                    "SELECT id, pergunta, opcao_1, opcao_2, opcao_3, opcao_4, resposta_correta FROM licoes WHERE modulo_id = ? ORDER BY id",
                                    (mod[0],)
                                )
                                st.session_state.idx = i
                                st.session_state.vidas = 3
                                st.session_state.respondido = False
                                st.session_state.opcoes_atuais = []
                                st.session_state.tela = "licao"
                                st.rerun()

    with c_rank:
        exibir_ranking()
        st.divider()
        if st.button("Sair / Trocar de aluno"):
            for k in ["tela", "aluno", "uid"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state.tela = "login"
            st.rerun()

# --- TELA: LIÇÃO ---
elif st.session_state.tela == "licao":
    trilha = st.session_state.trilha
    idx = st.session_state.idx
    lic_id, pergunta, o1, o2, o3, o4, correta = trilha[idx]

    c_sair, c_prog = st.columns([1, 4])
    with c_sair:
        if st.button("⬅️ Menu Principal"):
            st.session_state.tela = "inicio"
            st.rerun()
    with c_prog:
        st.progress((idx + 1) / len(trilha))
        st.write(f"Fase {idx + 1} de {len(trilha)}")

    st.markdown(f"### Vidas: {'❤️' * st.session_state.vidas}")

    if not st.session_state.opcoes_atuais:
        ops = [o1, o2, o3, o4]
        random.shuffle(ops)
        st.session_state.opcoes_atuais = ops

    if st.session_state.vidas <= 0:
        st.error("Game Over! Tente novamente.")
        if st.button("Voltar ao Mapa"):
            st.session_state.tela = "inicio"
            st.rerun()
    else:
        st.markdown(f"<div class='premium-card'><h3>{pergunta}</h3></div>", unsafe_allow_html=True)

        if not st.session_state.respondido:
            with st.form("pergunta_form"):
                resp = st.radio("Selecione a resposta:", st.session_state.opcoes_atuais, index=None)
                enviou = st.form_submit_button("Validar")
                if enviou:
                    if not resp:
                        st.warning("Escolha uma opção!")
                    else:
                        if resp == correta:
                            st.session_state.feedback = "✅ Correto! +10 XP"
                            executar("UPDATE alunos SET xp_total = xp_total + 10 WHERE id = ?", (st.session_state.uid,))
                            executar("INSERT OR IGNORE INTO progresso VALUES (?,?)", (st.session_state.uid, lic_id))
                        else:
                            st.session_state.vidas -= 1
                            st.session_state.feedback = f"❌ Errado! A correta era: **{correta}**"
                        st.session_state.respondido = True
                        st.rerun()
        else:
            st.write(st.session_state.feedback)
            # Botão de áudio para a resposta correta (ajuda na pronúncia)
            botao_audio(correta, f"audio_{lic_id}")
            if st.button("Avançar ➡️"):
                if idx + 1 < len(trilha):
                    st.session_state.idx += 1
                    st.session_state.respondido = False
                    st.session_state.opcoes_atuais = []
                    st.rerun()
                else:
                    st.session_state.tela = "conclusao_trilha"
                    st.rerun()

# --- TELA: CONCLUSÃO ---
elif st.session_state.tela == "conclusao_trilha":
    st.markdown("<div class='premium-card' style='text-align: center;'><h1>🎉 Módulo Concluído!</h1><p>Parabéns, continue assim!</p></div>", unsafe_allow_html=True)
    if st.button("Voltar ao Mapa"):
        st.session_state.tela = "inicio"
        st.rerun()