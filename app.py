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

# Estilo CSS para parecer uma App Nativa no telemóvel (esconde menus desnecessários)
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
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTENTICAÇÃO GOOGLE GEMINI ---
# Tenta carregar a chave dos "Secrets" do Streamlit
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception:
    st.error("⚠️ ERRO CRÍTICO: Chave de API não configurada.")
    st.info("Vá às definições do Streamlit Cloud > Secrets e adicione: GOOGLE_API_KEY = 'sua_chave'")
    st.stop()

# --- 3. FUNÇÃO DE PROCESSAMENTO (BACKEND) ---
def gerar_ata_inteligente(files):
    status = st.status("🚀 A iniciar o motor de IA...", expanded=True)
    
    arquivos_para_apagar = []
    arquivos_gemini = []
    
    try:
        # PASSO A: Upload para o Google
        status.write("📤 A enviar áudios para o servidor seguro...")
        for file in files:
            # Criar ficheiro temporário
            suffix = os.path.splitext(file.name)[1].lower()
            if not suffix: suffix = ".mp3"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file.getvalue())
                tmp_path = tmp.name
            
            # Upload
            g_file = genai.upload_file(tmp_path)
            arquivos_gemini.append(g_file)
            arquivos_para_apagar.append(tmp_path) # Marcar para apagar do disco local
            status.write(f"✅ Recebido: {file.name}")

        # PASSO B: Esperar Processamento do Áudio
        status.write("🎧 A IA está a ouvir as gravações...")
        for g_file in arquivos_gemini:
            while g_file.state.name == "PROCESSING":
                time.sleep(2)
                g_file = genai.get_file(g_file.name)
            
            if g_file.state.name == "FAILED":
                raise Exception("O Google não conseguiu ler o ficheiro de áudio.")

        # PASSO C: Gerar a Ata
        status.write("✍️ A redigir a ata profissional...")
        
        model = genai.GenerativeModel("models/gemini-flash-latest")
        
        prompt_sistema = """
        Tu és um Secretário Executivo de topo em Portugal.
        A tua tarefa é ouvir estas gravações de uma reunião (que podem estar divididas em partes) e redigir uma ATA FORMAL.
        
        ESTRUTURA OBRIGATÓRIA DA ATA:
        1. **Cabeçalho**: Título sugerido para a reunião e Data (se mencionada, senão mete a data de hoje).
        2. **Resumo Executivo**: Um parágrafo denso com o objetivo principal da reunião.
        3. **Pontos de Discussão**: Lista detalhada dos temas abordados. Usa bullet points.
        4. **Decisões Tomadas**: O que ficou fechado/decidido? (Muito importante).
        5. **Próximos Passos (Action Items)**: Quem ficou responsável pelo quê? (Se houver).
        
        TOM DE VOZ:
        - Formal, corporativo, direto.
        - Usa Português de Portugal (PT-PT) correto (ex: "Ficheiro" e não "Arquivo", "Ecrã" e não "Tela").
        - Ignora conversas de café, piadas ou "hum", "ah". Foca-te no conteúdo.
        """
        
        response = model.generate_content([prompt_sistema] + arquivos_gemini)
        
        # PASSO D: Limpeza
        status.update(label="✅ Ata Concluída!", state="complete", expanded=False)
        
        # Apagar ficheiros da nuvem do Google
        for g_file in arquivos_gemini:
            genai.delete_file(g_file.name)
        # Apagar ficheiros temporários do sistema
        for path in arquivos_para_apagar:
            os.remove(path)
            
        return response.text

    except Exception as e:
        status.update(label="❌ Ocorreu um erro", state="error")
        st.error(f"Detalhe do erro: {e}")
        return None

# --- 4. INTERFACE (FRONTEND) ---
st.title("🇵🇹 AtaPro.pt")
st.markdown("Transforme gravações de reuniões em **Atas Formais** em segundos.")

with st.container():
    st.write("### 1. Carregar Gravações")
    uploaded_files = st.file_uploader(
        "Selecione os ficheiros (Pode carregar vários: WhatsApp, MP3, M4A...)", 
        type=['mp3', 'wav', 'm4a', 'ogg', 'opus'], 
        accept_multiple_files=True
    )

    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} ficheiros selecionados prontos para processar.")
        
        st.write("### 2. Gerar Documento")
        if st.button("📝 CRIAR ATA AGORA", type="primary"):
            texto_ata = gerar_ata_inteligente(uploaded_files)
            
            if texto_ata:
                st.markdown("---")
                st.subheader("📄 Resultado Final")
                st.markdown(texto_ata)
                
                # Botão de Download
                st.download_button(
                    label="📥 Descarregar Ata (.txt)",
                    data=texto_ata,
                    file_name="Ata_Reuniao_AtaPro.txt",
                    mime="text/plain"
                )
