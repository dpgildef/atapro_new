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

# Estilo CSS 
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            height: 3.5em;
            font-weight: 600;
        }
        .info-box {
            background-color: #e8f4f9;
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #2e86c1;
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. SISTEMA DE LOGIN E UTILIZADOR ---
def check_password():
    """Gere o login e retorna o NOME do utilizador se autorizado."""
    
    if st.session_state.get("password_correct", False):
        return st.session_state.get("user_name", "Utilizador")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("⚖️ AtaPro | Área Reservada")
    st.info("Acesso exclusivo a subscritores autorizados.")
    
    password_input = st.text_input("Introduza a sua Chave de Acesso:", type="password")
    
    if st.button("🔓 Entrar", type="primary"):
        try:
            # Procura a senha nos valores e recupera o nome (chave)
            passwords = st.secrets["passwords"]
            # Inverte o dicionário para procurar por senha: {senha: nome}
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
            st.error("Erro de configuração nos Segredos (Secrets).")

    return None

# VERIFICAÇÃO DE LOGIN
nome_utilizador = check_password()
if not nome_utilizador:
    st.stop()

# ==========================================
# APP PRINCIPAL
# ==========================================

# --- 3. CONFIGURAÇÃO API ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception:
    st.error("⚠️ ERRO TÉCNICO: Chave de API em falta.")
    st.stop()

# --- 4. FUNÇÃO GERADORA DE PDF COM MARCA DE ÁGUA ---
class PDF(FPDF):
    def header(self):
        # Marca de água
        self.set_font('Arial', 'B', 50)
        self.set_text_color(220, 220, 220) # Cinzento muito claro
        self.rotate(45, x=105, y=148)
        self.text(30, 190, 'AtaPro.pt - CONFIDENCIAL')
        self.rotate(0) # Reset rotação

def criar_pdf(texto_ata):
    pdf = PDF()
    pdf.add_page()
    
    # Configurar fonte (Arial suporta latin-1 melhor que o padrão)
    pdf.set_font("Arial", size=11)
    pdf.set_text_color(0, 0, 0)
    
    # Tentar codificar o texto para evitar erros de caracteres estranhos
    # Substituímos caracteres não compatíveis com latin-1
    texto_limpo = texto_ata.encode('latin-1', 'replace').decode('latin-1')
    
    pdf.multi_cell(0, 7, txt=texto_limpo)
    
    # Retorna o PDF como string binária
    return pdf.output(dest='S').encode('latin-1')

# --- 5. FUNÇÃO DE PROCESSAMENTO (IA) ---
def processar_ata(files):
    status = st.status("⚙️ A processar a ata jurídica...", expanded=True)
    arquivos_temp = []
    arquivos_gemini = []
    
    try:
        # A: Upload
        status.write("📤 A transferir para servidor seguro (Google)...")
        for file in files:
            suffix = os.path.splitext(file.name)[1].lower()
            if not suffix: suffix = ".mp3"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file.getvalue())
                tmp_path = tmp.name
            
            g_file = genai.upload_file(tmp_path)
            arquivos_gemini.append(g_file)
            arquivos_temp.append(tmp_path) 
            status.write(f"✅ Áudio encriptado: {file.name}")

        # B: Espera
        status.write("🎧 A analisar conteúdo e intervenientes...")
        for g_file in arquivos_gemini:
            while g_file.state.name == "PROCESSING":
                time.sleep(2)
                g_file = genai.get_file(g_file.name)
            if g_file.state.name == "FAILED":
                raise Exception("Ficheiro corrompido ou formato inválido.")

        # C: Geração
        status.write("✍️ A redigir documento legal...")
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        
        prompt = """
        Tu és um Secretário Jurídico Profissional. A tua tarefa é redigir uma ATA FORMAL baseada no áudio.
        
        REQUISITOS LEGAIS E DE ESTRUTURA:
        1. A ata deve seguir a estrutura padrão de acordo com a lei geral (Código das Sociedades Comerciais/Administrativo).
        2. Usa linguagem formal, isenta e objetiva (PT-PT).
        
        ESTRUTURA OBRIGATÓRIA:
        - TÍTULO: "ATA N.º [Inserir Número/Ano]"
        - PREÂMBULO: "Aos [Dia] dias do mês de [Mês] de [Ano], pelas [Hora] horas, reuniu-se..." (Extrai do áudio ou deixa [Campos] para preencher).
        - PRESENÇAS: Listar quem estava presente (identificar vozes se possível).
        - ORDEM DE TRABALHOS: Tópicos discutidos.
        - DELIBERAÇÕES: O que foi aprovado (com contagem de votos se explícito).
        - ENCERRAMENTO: "Nada mais havendo a tratar, deu-se por encerrada a sessão..."
        
        Nota: Se não conseguires identificar a data ou local, deixa espaço sublinhado para preenchimento manual (ex: ________).
        """
        
        response = model.generate_content([prompt] + arquivos_gemini)
        texto_final = response.text
        
        status.update(label="✅ Documento Gerado!", state="complete", expanded=False)
        
        # D: Limpeza IMEDIATA (Política de Privacidade)
        for g_file in arquivos_gemini:
            try: genai.delete_file(g_file.name)
            except: pass
        for path in arquivos_temp:
            try: os.remove(path)
            except: pass
            
        return texto_final

    except Exception as e:
        status.update(label="❌ Erro no processamento", state="error")
        st.error(f"Detalhe: {e}")
        return None

# --- 6. INTERFACE (FRONTEND) ---

# Topo com Logout
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🇵🇹 AtaPro.pt")
    st.caption(f"Licença ativa: **{nome_utilizador}**")
with col2:
    if st.button("Sair 🔒"):
        st.session_state["password_correct"] = False
        st.session_state["user_name"] = None
        st.rerun()

# --- BLOCO DE INSTRUÇÕES DE GRAVAÇÃO ---
with st.expander("🎙️ IMPORTANTE: Instruções para uma Gravação Válida", expanded=False):
    st.markdown("""
    Para que a ata seja gerada com rigor jurídico, inicie a gravação dizendo:
    1.  **Data e Hora:** "Hoje é dia X, são Y horas."
    2.  **Local:** "Estamos reunidos na sede da empresa..."
    3.  **Participantes:** "Estão presentes: [Nome 1], [Nome 2]..."
    4.  **Ordem de Trabalhos:** "O objetivo desta reunião é..."
    
    *Dica: Fale perto do dispositivo e evite sobreposição de vozes.*
    """)

st.write("### Carregar Gravação da Reunião")

# Instruções Mobile
with st.expander("📱 Ajuda para iPhone/WhatsApp"):
    st.info("No iPhone/WhatsApp, escolha 'Partilhar' > 'Guardar em Ficheiros' antes de carregar aqui.")

uploaded_files = st.file_uploader("Formatos: MP3, M4A, WAV (Sem limite de tamanho)", accept_multiple_files=True)

# --- POLÍTICA DE PRIVACIDADE E TERMOS ---
st.markdown("---")
st.subheader("🛡️ Privacidade e Segurança")

st.markdown("""
<div style="font-size: 0.9em; color: #555;">
Ao utilizar este serviço, o utilizador toma conhecimento que:
<ul>
    <li><strong>Processamento Seguro:</strong> O áudio é processado temporariamente pelos servidores empresariais da Google.</li>
    <li><strong>Eliminação Imediata:</strong> Todos os ficheiros (áudio e texto) são <strong>eliminados permanentemente</strong> dos servidores após a geração.</li>
    <li><strong>Sem Cópias:</strong> O AtaPro.pt <strong>não guarda histórico</strong>. Se fechar esta aba sem descarregar o PDF, a ata perde-se para sempre.</li>
    <li><strong>Validação Legal:</strong> A ata é um esboço gerado por IA. Deve ser revista e assinada pelos intervenientes para ter validade jurídica plena.</li>
</ul>
</div>
""", unsafe_allow_html=True)

autorizacao = st.checkbox("Li e aceito a Política de Privacidade e confirmo ter autorização para processar esta gravação.")

if uploaded_files and autorizacao:
    st.markdown("---")
    if st.button("📝 GERAR ATA OFICIAL", type="primary"):
        texto_ata = processar_ata(uploaded_files)
        
        if texto_ata:
            st.success("Ata gerada com sucesso!")
            
            # Visualização rápida
            with st.expander("👁️ Ver Previsão do Texto"):
                st.markdown(texto_ata)
            
            # Gerar PDF
            pdf_bytes = criar_pdf(texto_ata)
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    label="📥 Descarregar PDF (Oficial)",
                    data=pdf_bytes,
                    file_name="Ata_Oficial.pdf",
                    mime="application/pdf"
                )
            with col_d2:
                 st.download_button(
                    label="📥 Descarregar Texto Editável",
                    data=texto_ata,
                    file_name="Ata_Editavel.txt",
                    mime="text/plain"
                )
elif uploaded_files and not autorizacao:
    st.warning("👆 Por favor, aceite os termos de privacidade para ativar o sistema.")
