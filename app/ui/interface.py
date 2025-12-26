import datetime
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import os
import time
from pathlib import Path
from redis import Redis
from rq import Queue
from app.config.settings import settings

# Configuração da Página
st.set_page_config(page_title="Auto Video Cutter", page_icon="✂️", layout="wide")

st.title("✂️ Auto Video Cutter Pro")
st.markdown("Transforme vídeos longos em Shorts virais com IA.")

# --- CONEXÃO COM A FILA ---
# Conecta no Redis usando as configurações do settings.py
try:
    redis_conn = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    q = Queue('video_jobs', connection=redis_conn)
except Exception as e:
    st.error(f"Erro ao conectar no Redis: {e}")
    st.stop()

# --- FUNÇÕES AUXILIARES ---

def generate_preview(text_color, font_size, margin_v):
    """
    Gera uma imagem dummy (9:16) simulando o Short final.
    """
    # 1. Dimensões do Short (1080x1920)
    # Vamos reduzir a escala por 3 para o preview ficar rápido e leve na tela
    scale = 0.3
    w_orig, h_orig = 1080, 1920
    w, h = int(w_orig * scale), int(h_orig * scale)
    
    # Ajusta os tamanhos recebidos (que são baseados em 1080p) para a escala do preview
    preview_font_size = int(font_size * scale)
    preview_margin_v = int(margin_v * scale)
    
    # 2. Cria o Canvas (Fundo Cinza Escuro simulando vídeo)
    img = Image.new('RGB', (w, h), color=(50, 50, 50))
    draw = ImageDraw.Draw(img)
    
    # 3. Carrega a Fonte
    # Tenta carregar a fonte do sistema Linux, se falhar usa a padrão
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", preview_font_size)
    except IOError:
        font = ImageFont.load_default()

    # 4. Texto de Exemplo
    text = "Legenda de Exemplo\nDuas Linhas de Texto"
    
    # 5. Calcula Posição (Centralizado Horizontal, MarginV Vertical)
    # No formato ASS, MarginV conta de baixo para cima
    # Precisamos calcular o tamanho do texto para centralizar
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (w - text_w) / 2
    y = h - preview_margin_v - text_h # De baixo para cima

    # 6. Desenha o Texto (Com Borda Preta igual ao FFmpeg)
    # stroke_width simula o Outline do ASS
    outline_width = int(4 * scale) # 4 é o valor que usamos no gerador ASS
    
    draw.text(
        (x, y), 
        text, 
        font=font, 
        fill=text_color, 
        stroke_width=outline_width, 
        stroke_fill="black",
        align="center"
    )
    
    # Desenha uma linha guia para mostrar onde é o fundo do vídeo
    draw.line([(0, h-1), (w, h-1)], fill="red", width=2)
    
    return img

def save_uploaded_file(uploaded_file):
    """Salva o arquivo de upload na pasta 'inputs' do Docker"""
    # Garante que a pasta inputs existe
    inputs_dir = Path("/app/inputs")
    inputs_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = inputs_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return uploaded_file.name

# Função auxiliar para empacotar as opções
def get_options():
    return {
        "min_duration": min_duration,
        "max_duration": max_duration,
        "text_color": text_color,
        "font_size": font_size,
        "margin_v": pos_vertical
    }

def enqueue_job(source):
    """Envia o trabalho para o Worker"""
    # Importante: Importar a função dentro do job para evitar erro de pickling
    from app.jobs.worker import process_video_pipeline
    
    opts = get_options()

    job = q.enqueue(
        process_video_pipeline,
        args=(source, None, opts),
        job_timeout=3600  # 1 hora de timeout
    )
    return job.id

# --- CONFIGURAÇÕES LATERAIS ---
with st.sidebar:
    st.header("⚙️ Configurações de Corte")
    
    with st.expander("⏱️ Duração e Tempo", expanded=False):
            min_duration = st.slider("Mínimo (segundos)", 10, 60, 30)
            max_duration = st.slider("Máximo (segundos)", 30, 180, 60)
    
    st.divider()
    
    st.subheader("🎨 Legendas")
    text_color = st.color_picker("Cor do Texto", "#FFFF00") # Amarelo
    font_size = st.slider("Tamanho da Fonte", 40, 120, 85)
    
    # Margin V: Quanto maior, mais alto a legenda fica
    pos_vertical = st.slider("Posição Vertical (Margin Bottom)", 50, 600, 250)

    st.markdown("### 👁️ Preview em Tempo Real")
    
    # Chamamos a função geradora passando os valores atuais dos sliders
    preview_img = generate_preview(text_color, font_size, pos_vertical)
    
    # Exibimos a imagem
    st.image(preview_img)

# --- LAYOUT DA INTERFACE ---

tab1, tab2, tab3 = st.tabs(["📺 YouTube", "📂 Upload Local", "👀 Resultados"])

# ABA 1: YOUTUBE
with tab1:
    st.header("Baixar do YouTube")
    url = st.text_input("Cole o link do vídeo aqui:")
    
    if st.button("🚀 Processar YouTube", type="primary"):
        if url:
            with st.spinner("Enviando para a fila de processamento..."):
                job_id = enqueue_job(url)
                st.success(f"Job enviado! ID: {job_id}")
                st.session_state['last_job_id'] = job_id
        else:
            st.warning("Por favor, insira uma URL.")

# ABA 2: UPLOAD
with tab2:
    st.header("Upload de Arquivo (MP4)")
    uploaded_file = st.file_uploader("Escolha um vídeo", type=["mp4", "mov", "mkv"])
    
    if st.button("🚀 Processar Arquivo", type="primary"):
        if uploaded_file:
            with st.spinner("Salvando arquivo e enviando..."):
                filename = save_uploaded_file(uploaded_file)
                job_id = enqueue_job(filename)
                st.success(f"Job enviado! ID: {job_id}")
                st.session_state['last_job_id'] = job_id
        else:
            st.warning("Por favor, faça o upload de um arquivo primeiro.")

# ABA 3: MONITORAMENTO SIMPLES
with tab3:
    st.header("📂 Histórico de Jobs")
    
    # 1. Listar pastas de Jobs
    jobs_dir = settings.JOBS_DIR
    
    # Verifica se a pasta existe
    if jobs_dir.exists():
        # Pega todas as subpastas
        all_jobs = [f for f in jobs_dir.iterdir() if f.is_dir()]
        
        # Ordena por data de modificação (mais recente primeiro)
        # Lambda explica: pega o status do arquivo (stat) e o tempo de modificação (st_mtime)
        all_jobs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Cria uma lista formatada para o Selectbox
        # Ex: "2023-12-26 15:30 - a1b2c3..."
        job_options = {}
        for j in all_jobs:
            # Converte timestamp para data legível
            ts = j.stat().st_mtime
            date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            label = f"{date_str}  |  {j.name}"
            job_options[label] = j.name # Guarda o ID real no dicionário
        
        if not job_options:
            st.info("Nenhum job encontrado ainda.")
        else:
            # O Widget de Seleção
            selected_label = st.selectbox("Selecione um Job:", list(job_options.keys()))
            
            # Recupera o ID baseado no label escolhido
            selected_job_id = job_options[selected_label]
            
            st.divider()
            
            # Lógica de Exibição (igual antes, mas agora automática)
            job_path = settings.get_job_path(selected_job_id)
            output_dir = job_path / "outputs"
            
            if output_dir.exists():
                videos = list(output_dir.glob("*.mp4"))
                if videos:
                    st.success(f"🎬 Encontrados {len(videos)} Shorts no job {selected_job_id}")
                    
                    # Grid de vídeos
                    cols = st.columns(3)
                    for i, video_path in enumerate(videos):
                        with cols[i % 3]:
                            st.video(str(video_path))
                            st.caption(f"📺 {video_path.name}")
                            
                            # Botão de Download
                            with open(video_path, "rb") as file:
                                st.download_button(
                                    label="⬇️ Baixar",
                                    data=file,
                                    file_name=video_path.name,
                                    mime="video/mp4",
                                    key=f"dl_{selected_job_id}_{i}"
                                )
                else:
                    st.warning("⏳ O Job existe, mas os vídeos ainda não estão prontos. (Processando...)")
            else:
                st.error("❌ Pasta de outputs não encontrada (o Job falhou ou ainda está baixando).")
            
    else:
        st.error("Pasta de Jobs não encontrada no sistema.")