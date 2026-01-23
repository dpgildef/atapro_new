import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
from fpdf import FPDF

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="AtaPro.pt",
    page_icon="🇵🇹",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- ESTILO CSS (Design e Traduções) ---
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Botões grandes e profissionais */
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            height: 3.5em;
            font-weight: 600;
            font-size: 16px;
        }

        /* TRUQUE CSS PARA TRADUZIR O UPLOAD (Visual) */
        [data-testid='stFileUploaderDropzone'] div div span {display: none;}
        [data-testid='stFileUploaderDropzone'] div div::after {
           content: "Arraste e largue os ficheiros aqui";
           font-size: 1.2em; font-weight: bold;
        }
        [data-testid='stFileUploaderDropzone'] small {display: none;}
        [data-testid='stFileUploaderDropzone']::after {
           content: "Limite: 200MB por ficheiro • MP3, M4A, WAV";
           font-size: 0.9em; display: block; text-align: center; margin-top: 5px; color: #333;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. SISTEMA DE LOGIN ---
def check_password():
    """Gere o login e retorna o nome do utilizador."""
    
    if st.session_state.get("password_correct", False):
        return st.session_state.get("user_name", "Utilizador")

    # Ecrã de Login
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("⚖️ AtaPro | Área Reservada")
    st.info("Plataforma exclusiva para subscritores autorizados.")
    
    password_input = st.text_input("Introduza a sua Chave de Acesso:", type="password")
    
    if st.button("🔓 Entrar", type="primary"):
        try:
            # Procura a senha nos Secrets
            passwords = st.secrets["passwords"]
            # Mapeia senha -> nome
            senha_para_nome = {v: k for k, v in passwords.items()}
            
            if password_input in senha_para_nome:
                st.session_state["password_correct"] = True
                st.session_state["user_name"] = senha_para_nome[password_input]
                st.toast(f"Bem-vindo(a), {st.session_state['user_name']}!", icon="👋")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Chave de acesso incorreta.")
        except KeyError:
            st.error("Erro de configuração interna (Secrets). Contacte o suporte.")

    return None

# VERIFICA SE ESTÁ LOGADO
nome_utilizador = check_password()
if not nome_utilizador:
    st.stop()

# ==========================================
# APP PRINCIPAL (SÓ CARREGA APÓS LOGIN)
# ==========================================

# --- 3. CONFIGURAÇÃO API ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception:
    st.error("⚠️ ERRO CRÍTICO: Chave de API Google em falta.")
    st.stop()

# --- 4. CLASSE PDF (MARCA DE ÁGUA) ---
class PDF(FPDF):
    def header(self):
        # Marca de água diagonal
        self.set_font('Arial', 'B', 50)
        self.set_text_color(240, 240, 240) # Cinzento muito claro (quase branco)
        self.rotate(45, x=105, y=148)
        self.text(30, 190, 'AtaPro.pt - CONFIDENCIAL')
        self.rotate(0) # Reset rotação

def criar_pdf(texto_ata):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    pdf.set_text_color(0, 0, 0) # Texto preto
    
    # Tratamento de caracteres especiais (PT)
    try:
        texto_limpo = texto_ata.encode('latin-1', 'replace').decode('latin-1')
    except:
        texto_limpo = texto_ata # Fallback
    
    pdf.multi_cell(0, 7, txt=texto_limpo)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. PROCESSAMENTO DE ÁUDIO (IA) ---
def processar_ata(files):
    status = st.status("⚙️ A iniciar processamento seguro...", expanded=True)
    arquivos_temp = []
    arquivos_gemini = []
    
    try:
        # ORDENAR FICHEIROS (Parte 1, Parte 2...)
        # Garante que a ata segue a cronologia correta se houver vários áudios
        files.sort(key=lambda x: x.name)
        
        # A: Upload
        status.write(f"📤 A carregar {len(files)} ficheiro(s) por ordem cronológica...")
        for file in files:
            suffix = os.path.splitext(file.name)[1].lower()
            if not suffix: suffix = ".mp3"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file.getvalue())
                tmp_path = tmp.name
            
            g_file = genai.upload_file(tmp_path)
            arquivos_gemini.append(g_file)
            arquivos_temp.append(tmp_path) 
            status.write(f"✅ Recebido: {file.name}")

        # B: Espera
        status.write("🎧 A IA está a ouvir e a transcrever o conteúdo...")
        for g_file in arquivos_gemini:
            while g_file.state.name == "PROCESSING":
                time.sleep(2)
                g_file = genai.get_file(g_file.name)
            if g_file.state.name == "FAILED":
                raise Exception(f"Erro ao ler o ficheiro {g_file.name}. Formato inválido.")

        # C: Geração
        status.write("✍️ A redigir a ata jurídica (PT-PT)...")
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        
        prompt = """
        Tu és um Secretário Jurídico Sénior. A tua tarefa é ouvir o áudio e redigir uma ATA FORMAL.
        
        REGRAS DE OURO:
        - Usa Português de Portugal (PT-PT) formal.
        - Sê isento e objetivo.
        - Se existirem múltiplos ficheiros, trata-os como uma sequência contínua da mesma reunião.

        ESTRUTURA OBRIGATÓRIA:
        1. TÍTULO: "ATA [Inserir Número/Ano se dito, ou deixar ___]"
        2. CABEÇALHO: "Aos [Dia] dias do mês de [Mês] de [Ano], pelas [Hora] horas, reuniu-se [Entidade/Local]..."
        3. PRESENÇAS: Lista de nomes identificados.
        4. ORDEM DE TRABALHOS: Tópicos principais.
        5. DELIBERAÇÕES: Descrição detalhada do que foi discutido e decidido.
        6. ENCERRAMENTO: "Nada mais havendo a tratar, a sessão foi encerrada às [Hora]..."
        
        Nota: Se faltarem dados (como data ou hora exata), deixa um espaço sublinhado (_______) para preenchimento manual posterior.
        """
        
        response = model.generate_content([prompt] + arquivos_gemini)
        texto_final = response.text
        
        status.update(label="✅ Documento Gerado!", state="complete", expanded=False)
        
        # D: Limpeza de Segurança (RGPD)
        for g_file in arquivos_gemini:
            try: genai.delete_file(g_file.name)
            except: pass
        for path in arquivos_temp:
            try: os.remove(path)
            except: pass
            
        return texto_final

    except Exception as e:
        status.update(label="❌ Erro no processamento", state="error")
        st.error(f"Ocorreu um erro: {e}")
        return None

# --- 6. INTERFACE DE UTILIZADOR ---

# Cabeçalho
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🇵🇹 AtaPro.pt")
    st.markdown(f"**Bem-vindo, {nome_utilizador}.**")
with col2:
    if st.button("Sair 🔒"):
        st.session_state["password_correct"] = False
        st.session_state["user_name"] = None
        st.rerun()

# Instruções de Gravação (Importante para qualidade)
with st.expander("🎙️ COMO GRAVAR UMA REUNIÃO VÁLIDA (Ler Antes)", expanded=False):
    st.markdown("""
    Para garantir uma ata perfeita, comece a gravação dizendo:
    1.  **"Hoje é dia [X], são [Y] horas."**
    2.  **"Estamos reunidos em [Local] para a reunião de [Nome da Entidade]."**
    3.  **"Estão presentes: [Nome 1], [Nome 2], [Nome 3]..."**
    4.  **"A ordem de trabalhos é..."**
    
    *Dica: Coloque o telemóvel no centro da mesa.*
    """)

st.divider()

# Área de Upload
st.write("### 1. Carregar Gravações")

# Instruções Rápidas (Mobile)
with st.expander("📱 Dificuldade no iPhone/WhatsApp? Clique aqui."):
    st.info("No iPhone ou WhatsApp, escolha a opção **'Partilhar' > 'Guardar em Ficheiros'**. Depois volte aqui e selecione o ficheiro dessa pasta.")

# Uploader (Sem restrição de 'type' para mobile funcionar, mas avisa sobre limite)
uploaded_files = st.file_uploader(
    "Selecione os ficheiros de áudio:", 
    accept_multiple_files=True,
    help="Se a reunião tiver várias partes, carregue todas de uma vez. A IA vai ordená-las."
)

if uploaded_files:
    # Aviso sobre tamanho (já que mantivemos o limite de 200MB)
    st.caption(f"📂 {len(uploaded_files)} ficheiro(s) selecionado(s). A IA irá processá-los por ordem alfabética.")
    st.warning("⚠️ Nota: O limite é **200MB por ficheiro**. Se tiver um ficheiro WAV muito grande, converta para MP3 antes de enviar.")

    # --- PRIVACIDADE E TERMOS ---
    st.markdown("---")
    st.subheader("🛡️ Privacidade e Termos Legais")
    
    # Texto de privacidade com cor visível (sem estilo 'grey')
    st.markdown("""
    <div>
    Ao prosseguir, o utilizador declara estar ciente que:
    <ul>
        <li><strong>Segurança:</strong> O áudio é processado de forma encriptada pelos servidores Enterprise da Google.</li>
        <li><strong>Eliminação de Dados:</strong> Os ficheiros de áudio e as atas geradas são <strong>apagados imediatamente</strong> dos nossos servidores após a entrega.</li>
        <li><strong>Sem Histórico:</strong> O AtaPro.pt não mantém cópias. Se fechar esta página sem descarregar, o documento perde-se.</li>
        <li><strong>Validade:</strong> O documento gerado é um auxiliar administrativo. Deve ser validado e assinado pelos intervenientes para efeitos legais.</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    autorizacao = st.checkbox("Li e aceito a Política de Privacidade e confirmo ter autorização de todos os intervenientes.")

    if autorizacao:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📝 GERAR ATA OFICIAL", type="primary"):
            texto_ata = processar_ata(uploaded_files)
            
            if texto_ata:
                st.success("Processo concluído com sucesso!")
                
                # Pré-visualização
                with st.expander("👁️ Pré-visualizar Texto"):
                    st.markdown(texto_ata)
                
                # Botões de Download
                pdf_bytes = criar_pdf(texto_ata)
                
                col_down1, col_down2 = st.columns(2)
                with col_down1:
                    st.download_button(
                        label="📄 Descarregar PDF (Oficial)",
                        data=pdf_bytes,
                        file_name="Ata_Oficial.pdf",
                        mime="application/pdf"
                    )
                with col_down2:
                     st.download_button(
                        label="📝 Descarregar Editável (.txt)",
                        data=texto_ata,
                        file_name="Ata_Editavel.txt",
                        mime="text/plain"
                    )
    else:
        st.info("👆 Por favor, aceite os termos acima para desbloquear o botão de geração.")
