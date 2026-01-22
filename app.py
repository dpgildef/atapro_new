import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="AtaPro.pt",
    page_icon="🇵🇹",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Estilo CSS (Melhorado para esconder elementos padrão e estilizar login)
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stButton>button {
            width: 100%;
            border-radius: 10px;
            height: 3em;
            font-weight: bold;
        }
        /* Estilo para a caixa de login */
        .login-box {
            padding: 20px;
            border-radius: 10px;
            background-color: #f0f2f6;
            text-align: center;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. SISTEMA DE LOGIN (PAY-WALL) ---
def check_password():
    """Retorna True se o utilizador tiver a senha correta."""

    # Se já validou antes na mesma sessão, deixa passar
    if st.session_state.get("password_correct", False):
        return True

    # Interface de Login
    st.title("🔒 AtaPro.pt | Acesso Restrito")
    
    st.markdown("""
    Esta ferramenta é exclusiva para clientes subscritores.
    <br>Para adquirir uma licença, contacte: **comercial@atapro.pt**
    """, unsafe_allow_html=True)
    
    password_input = st.text_input("Insira a sua Chave de Acesso:", type="password")

    if st.button("Entrar", type="primary"):
        # Vai buscar as senhas aos Secrets do Streamlit
        # Estrutura esperada no secrets.toml:
        # [passwords]
        # "cliente1" = "senha123"
        try:
            senhas_validas = st.secrets["passwords"].values()
        except KeyError:
            # Fallback se não houver senhas configuradas (para não dar erro)
            senhas_validas = ["admin"] 

        if password_input in senhas_validas:
            st.session_state["password_correct"] = True
            st.success("Acesso autorizado! A carregar...")
            time.sleep(1)
            st.rerun()  # Recarrega a página para mostrar a app
        else:
            st.error("❌ Chave de acesso inválida ou expirada.")

    return False

# SE NÃO TIVER LOGADO, PARA O CÓDIGO AQUI
if not check_password():
    st.stop()

# ==========================================
# DAQUI PARA BAIXO É A APP NORMAL (SÓ APARECE SE LOGADO)
# ==========================================

# --- 3. AUTENTICAÇÃO GOOGLE GEMINI ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception:
    st.error("⚠️ ERRO TÉCNICO: Chave de API Google em falta.")
    st.stop()

# --- 4. FUNÇÃO DE PROCESSAMENTO (BACKEND) ---
def gerar_ata_inteligente(files):
    status = st.status("🚀 A iniciar o motor de IA...", expanded=True)
    
    arquivos_para_apagar = []
    arquivos_gemini = []
    
    try:
        # PASSO A: Upload
        status.write("📤 A enviar áudios para processamento...")
        for file in files:
            suffix = os.path.splitext(file.name)[1].lower()
            if not suffix: suffix = ".mp3"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file.getvalue())
                tmp_path = tmp.name
            
            g_file = genai.upload_file(tmp_path)
            arquivos_gemini.append(g_file)
            arquivos_para_apagar.append(tmp_path) 
            status.write(f"✅ Recebido: {file.name}")

        # PASSO B: Processamento
        status.write("🎧 A analisar o conteúdo das gravações...")
        for g_file in arquivos_gemini:
            while g_file.state.name == "PROCESSING":
                time.sleep(2)
                g_file = genai.get_file(g_file.name)
            if g_file.state.name == "FAILED":
                raise Exception("Erro na leitura do áudio.")

        # PASSO C: Geração
        status.write("✍️ A redigir a ata profissional...")
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        
        prompt_sistema = """
        Tu és um Secretário Executivo profissional. Ouve o áudio e cria uma ATA FORMAL em PT-PT.
        Estrutura: Cabeçalho, Resumo, Discussão (pontos), Decisões, Próximos Passos.
        Sê direto, formal e ignora conversas irrelevantes.
        """
        
        response = model.generate_content([prompt_sistema] + arquivos_gemini)
        
        # Limpeza
        status.update(label="✅ Concluído!", state="complete", expanded=False)
        for g_file in arquivos_gemini:
            try: genai.delete_file(g_file.name)
            except: pass
        for path in arquivos_para_apagar:
            try: os.remove(path)
            except: pass
            
        return response.text

    except Exception as e:
        status.update(label="❌ Erro", state="error")
        st.error(f"Detalhe: {e}")
        return None

# --- 5. INTERFACE DO UTILIZADOR ---
# Botão de Logout no canto
col1, col2 = st.columns([4,1])
with col1:
    st.title("🇵🇹 AtaPro.pt")
with col2:
    if st.button("Sair 🔒"):
        st.session_state["password_correct"] = False
        st.rerun()

st.markdown("Bem-vindo(a) à área reservada. Transforme reuniões em atas instantaneamente.")

with st.container():
    st.write("### Carregar Gravações")
    
    with st.expander("📱 Instruções para iPhone/WhatsApp"):
        st.markdown("""
        Se o ficheiro estiver cinzento:
        1. Vá ao WhatsApp/Gravações.
        2. Clique "Partilhar" > **Guardar em Ficheiros**.
        3. Volte aqui e selecione.
        """)
    
    uploaded_files = st.file_uploader(
        "Selecione os ficheiros:", 
        accept_multiple_files=True
    )

if uploaded_files:
    st.info(f"📂 {len(uploaded_files)} ficheiros selecionados.")
    st.divider()
    
    autorizacao = st.checkbox("Confirmo que tenho autorização para processar estes dados.")
    
    if autorizacao:
        if st.button("📝 GERAR ATA", type="primary"):
            texto_final = gerar_ata_inteligente(uploaded_files)
            if texto_final:
                st.markdown("---")
                st.subheader("Resultado")
                st.markdown(texto_final)
                st.download_button("📥 Download (.txt)", texto_final, "ata.txt")
