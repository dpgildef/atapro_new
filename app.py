import streamlit as st
import google.generativeai as genai
import tempfile
import os
import time
from io import BytesIO
from docx import Document 
from docx.shared import Pt, RGBColor

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="AtaPro.pt | Condomínios",
    page_icon="🏢",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- ESTILO CSS ---
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
            font-size: 16px;
        }

        /* TRUQUE CSS PARA TRADUZIR O UPLOAD */
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
        
        /* Caixa de Aviso Legal */
        .legal-box {
            font-size: 0.85em;
            background-color: #f0f7fb;
            border-left: 4px solid #0056b3;
            padding: 12px;
            margin-top: 10px;
            color: #2c3e50;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. SISTEMA DE LOGIN ---
def check_password():
    if st.session_state.get("password_correct", False):
        return st.session_state.get("user_name", "Utilizador")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.title("🏢 AtaPro | Condomínios")
    st.info("Área exclusiva para Administradores de Condomínio.")
    
    password_input = st.text_input("Introduza a sua Chave de Acesso:", type="password")
    
    if st.button("🔓 Entrar", type="primary"):
        try:
            passwords = st.secrets["passwords"]
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
            st.error("Erro de configuração interna (Secrets).")
    return None

nome_utilizador = check_password()
if not nome_utilizador:
    st.stop()

# ==========================================
# LÓGICA DE ESTADO (MEMÓRIA)
# ==========================================
if "texto_ata_final" not in st.session_state:
    st.session_state["texto_ata_final"] = None

# --- 3. CONFIGURAÇÃO API ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
except Exception:
    st.error("⚠️ ERRO CRÍTICO: Chave de API Google em falta.")
    st.stop()

# --- 4. FUNÇÃO GERADORA DE WORD (.docx) ---
def criar_word(texto_ata):
    doc = Document()
    
    # Título Principal
    heading = doc.add_heading('ATA DA ASSEMBLEIA DE CONDOMÍNIO', 0)
    heading.alignment = 1 # Centro
    
    # Adiciona o texto gerado
    for paragrafo in texto_ata.split('\n'):
        if paragrafo.strip():
            doc.add_paragraph(paragrafo)
    
    # --- RODAPÉ LEGAL (ATUALIZADO PARA CONDOMÍNIOS) ---
    doc.add_paragraph("_" * 50)
    legal_note = doc.add_paragraph()
    run = legal_note.add_run("CONFORMIDADE LEGAL:\nA presente ata foi elaborada nos termos do Artigo 1.º do Decreto-Lei n.º 268/94, com as alterações introduzidas pela Lei n.º 8/2022, de 10 de janeiro, constituindo título executivo para todos os efeitos legais.")
    run.font.size = Pt(8)
    run.font.italic = True
    run.font.color.rgb = RGBColor(80, 80, 80)
            
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- 5. PROCESSAMENTO DE ÁUDIO (IA) ---
def processar_ata(files):
    status = st.status("⚙️ A processar ata de condomínio...", expanded=True)
    arquivos_temp = []
    arquivos_gemini = []
    
    try:
        files.sort(key=lambda x: x.name)
        
        # A: Upload
        status.write(f"📤 A carregar {len(files)} ficheiro(s)...")
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
        status.write("🎧 A analisar as deliberações dos condóminos...")
        for g_file in arquivos_gemini:
            while g_file.state.name == "PROCESSING":
                time.sleep(2)
                g_file = genai.get_file(g_file.name)
            if g_file.state.name == "FAILED":
                raise Exception(f"Erro ao ler o ficheiro {g_file.name}.")

        # C: Geração
        status.write("✍️ A redigir a ata segundo a Lei n.º 8/2022...")
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        
        # --- PROMPT ESPECÍFICO PARA CONDOMÍNIOS ---
        prompt = """
        Tu és um Administrador de Condomínios profissional em Portugal. 
        A tua tarefa é redigir uma ATA DE ASSEMBLEIA DE CONDOMÍNIO rigorosa.

        BASE LEGAL:
        Respeita o Decreto-Lei n.º 268/94 e a Lei n.º 8/2022.

        ESTRUTURA OBRIGATÓRIA:
        1. TÍTULO: "ATA N.º [Ano]/[N.º]"
        2. CABEÇALHO: 
           - "Aos [Dia] dias de [Mês] de [Ano], reuniu-se a Assembleia de Condóminos do prédio sito em [Local]..."
           - Indicar se é Ordinária ou Extraordinária.
           - Indicar quem presidiu à mesa (Presidente/Secretário).
        3. PRESENÇAS: Listar Condóminos presentes e representados (se dito no áudio).
        4. ORDEM DE TRABALHOS: Pontos exatos da convocatória.
        5. DELIBERAÇÕES (Muito Importante):
           - Para cada ponto, descrever a discussão e a VOTAÇÃO.
           - Usar termos: "Aprovado por unanimidade", "Aprovado por maioria", ou "Rejeitado".
        6. ENCERRAMENTO: menção de que a ata vai ser assinada.
        
        IMPORTANTE: 
        - Escreve em PT-PT.
        - Sê objetivo. Identifica frações (ex: 1º Esq, R/C Drt) se forem mencionadas.
        - Não uses Markdown complexo, usa texto limpo.
        """
        
        response = model.generate_content([prompt] + arquivos_gemini)
        texto_gerado = response.text
        
        status.update(label="✅ Ata de Condomínio Gerada!", state="complete", expanded=False)
        
        # D: Limpeza
        for g_file in arquivos_gemini:
            try: genai.delete_file(g_file.name)
            except: pass
        for path in arquivos_temp:
            try: os.remove(path)
            except: pass
            
        return texto_gerado

    except Exception as e:
        status.update(label="❌ Erro no processamento", state="error")
        st.error(f"Ocorreu um erro: {e}")
        return None

# --- 6. INTERFACE DE UTILIZADOR ---

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🏢 AtaPro | Condomínios")
    st.markdown(f"**Bem-vindo, {nome_utilizador}.**")
with col2:
    if st.button("Sair 🔒"):
        st.session_state["password_correct"] = False
        st.session_state["user_name"] = None
        st.rerun()

# --- MOSTRAR RESULTADO SE JÁ EXISTIR NA MEMÓRIA ---
if st.session_state["texto_ata_final"]:
    st.success("✅ A sua ata está pronta e guardada abaixo.")
    
    # Aviso Legal Atualizado
    st.markdown("""
    <div class="legal-box">
    ⚖️ <strong>Conformidade Legal (Portugal):</strong><br> 
    Ata gerada de acordo com o <strong>Artigo 1.º do Decreto-Lei n.º 268/94</strong> 
    e atualizações da <strong>Lei n.º 8/2022</strong> (Regime da Propriedade Horizontal).
    </div>
    """, unsafe_allow_html=True)
    
    st.write("### 📥 Descarregar Documento")
    
    # Converter para Word
    word_file = criar_word(st.session_state["texto_ata_final"])
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button(
            label="📄 Descarregar em WORD (.docx)",
            data=word_file,
            file_name="Ata_Condominio.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary"
        )
    with col_d2:
        if st.button("🔄 Começar Nova Ata"):
            st.session_state["texto_ata_final"] = None
            st.rerun()
            
    with st.expander("👁️ Ver Texto da Ata (Pré-visualização)"):
        st.markdown(st.session_state["texto_ata_final"])

# --- MOSTRAR UPLOAD SE AINDA NÃO HOUVER ATA ---
else:
    with st.expander("🎙️ GUIA: COMO GRAVAR ASSEMBLEIA DE CONDOMÍNIO", expanded=False):
        st.markdown("""
        Para validade legal (Lei n.º 8/2022), comece a gravação dizendo:
        1.  **"Assembleia do Condomínio do prédio sito em [Morada]..."**
        2.  **"Hoje é dia [X], hora [Y]."**
        3.  **"Presenças: Fração A (Sr. João), Fração B (Sra. Maria)..."**
        4.  **"Ponto 1 da Ordem de Trabalhos: [Assunto]..."**
        """)

    st.write("### 1. Carregar Gravações")

    with st.expander("📱 Ajuda para iPhone/WhatsApp"):
        st.info("No iPhone ou WhatsApp: 'Partilhar' > 'Guardar em Ficheiros'.")

    uploaded_files = st.file_uploader(
        "Selecione os ficheiros de áudio:", 
        accept_multiple_files=True
    )

    if uploaded_files:
        st.caption(f"📂 {len(uploaded_files)} ficheiro(s) selecionado(s).")
        st.warning("⚠️ Nota: O limite é **200MB por ficheiro**.")

        st.markdown("---")
        st.subheader("🛡️ Privacidade e Termos")
        
        st.markdown("""
        <div>
        <ul>
            <li><strong>Segurança:</strong> Áudio processado via Google Enterprise (encriptado).</li>
            <li><strong>Eliminação:</strong> Dados apagados imediatamente após a geração.</li>
            <li><strong>Sem Histórico:</strong> Não guardamos cópias das atas.</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
        
        autorizacao = st.checkbox("Li e aceito a Política de Privacidade.")

        if autorizacao:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📝 GERAR ATA DE CONDOMÍNIO", type="primary"):
                resultado = processar_ata(uploaded_files)
                if resultado:
                    st.session_state["texto_ata_final"] = resultado
                    st.rerun() 
        else:
            st.info("👆 Aceite os termos para continuar.")
