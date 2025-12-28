import uuid
import datetime
import time
import shutil
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
from pathlib import Path
from redis import Redis
from rq import Queue
from app.config.settings import settings

# Configuração da Página
st.set_page_config(page_title="Auto Video Cutter", page_icon="✂️", layout="wide")

st.title("✂️ Auto Video Cutter Pro")
st.markdown("Transforme vídeos longos em Shorts virais com IA.")

# --- ESTADOS ---
if 'pending_job' not in st.session_state:
    st.session_state.pending_job = None

if 'last_active_tab' not in st.session_state:
    st.session_state.last_active_tab = "youtube"

# Estado que controla se os inputs estão bloqueados
# Só bloqueamos se o usuário estiver com o painel de REVISÃO aberto.
# Se estiver apenas processando (barra de progresso), os inputs ficam livres.
is_reviewing = st.session_state.pending_job is not None

@st.cache_resource
def get_redis_queue():
    try:
        redis_conn = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        q = Queue('video_jobs', connection=redis_conn)
        return q
    except Exception as e:
        return None

q = get_redis_queue()
if not q:
    st.error("Erro fatal: Não foi possível conectar ao Redis.")
    st.stop()

# --- FUNÇÕES ---

def get_job_progress(job_id):
    """Lê o progresso do Redis (Sem Cache para ser Real-Time)"""
    try:
        redis_conn = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        # Verifica se a chave existe
        if not redis_conn.exists(f"job_status:{job_id}"):
            return 0, "Na fila de processamento..."
            
        data = redis_conn.hgetall(f"job_status:{job_id}")
        if data:
            pct = int(data.get(b'progress', 0))
            status = data.get(b'status', b'Iniciando...').decode('utf-8')
            return pct, status
    except Exception:
        pass
    return 0, "Aguardando worker..."

@st.cache_data(ttl=5, show_spinner=False)
def list_jobs_data():
    jobs_dir = settings.JOBS_DIR
    if not jobs_dir.exists():
        return {}
    all_jobs = [f for f in jobs_dir.iterdir() if f.is_dir()]
    all_jobs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    formatted_jobs = {}
    for j in all_jobs:
        ts = j.stat().st_mtime
        date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
        label = f"{date_str}  |  {j.name}"
        formatted_jobs[label] = j.name
    return formatted_jobs

def create_zip(job_id):
    job_path = settings.get_job_path(job_id)
    output_dir = job_path / "outputs"
    zip_path = job_path / f"shorts_{job_id}"
    if output_dir.exists():
        shutil.make_archive(str(zip_path), 'zip', output_dir)
        return f"{zip_path}.zip"
    return None

@st.cache_data(show_spinner=False) 
def generate_preview(text_color, font_size, margin_v, is_vertical=True, show_text=True, use_blur=False):
    scale = 0.3
    if is_vertical:
        w_orig, h_orig = 1080, 1920
    else:
        w_orig, h_orig = 1920, 1080 
    w, h = int(w_orig * scale), int(h_orig * scale)
    
    bg_color = (50, 50, 50)
    if is_vertical and use_blur:
        bg_color = (30, 30, 40) 
        
    img = Image.new('RGB', (w, h), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    if is_vertical and use_blur:
        video_h = int(w * (9/16))
        y_pos = (h - video_h) // 2
        draw.rectangle([0, y_pos, w, y_pos + video_h], fill=(60, 60, 60), outline="black")
    
    if show_text:
        preview_font_size = int(font_size * scale)
        preview_margin_v = int(margin_v * scale)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", preview_font_size)
        except IOError:
            font = ImageFont.load_default()

        text = "Legenda Aqui\nTexto Exemplo"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (w - text_w) / 2
        y = h - preview_margin_v - text_h 
        draw.text((x, y), text, font=font, fill=text_color, stroke_width=2, stroke_fill="black", align="center")
    
    draw.line([(0, h-1), (w, h-1)], fill="red", width=2)
    draw.line([(0, 0), (w, 0)], fill="red", width=2)
    return img

def save_uploaded_file(uploaded_file):
    inputs_dir = Path("/app/inputs")
    inputs_dir.mkdir(parents=True, exist_ok=True)
    file_path = inputs_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return uploaded_file.name

def get_options():
    is_short = "Short" in video_format
    return {
        "min_duration": min_duration,
        "max_duration": max_duration,
        "text_color": text_color,
        "font_size": font_size,
        "margin_v": pos_vertical,
        "format": "vertical" if is_short else "horizontal",
        "use_subs": use_subtitles,
        "use_blur": use_blur if is_short else False
    }

def enqueue_job(source, options):
    from app.jobs.worker import process_video_pipeline
    
    my_job_id = str(uuid.uuid4())
    
    job = q.enqueue(
        process_video_pipeline,
        args=(source, my_job_id, options),
        job_id=my_job_id,
        job_timeout=3600
    )
    return job.id

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configurações de Corte")
    
    def update_slider_defaults():
        fmt = st.session_state.video_format
        if fmt == "Short (9:16)":
            st.session_state.min_val = 30
            st.session_state.max_val = 60
            st.session_state.subs_default = True
        else: # Medium (16:9)
            st.session_state.min_val = 60
            st.session_state.max_val = 180
            st.session_state.subs_default = False

    if 'min_val' not in st.session_state: st.session_state.min_val = 30
    if 'max_val' not in st.session_state: st.session_state.max_val = 60
    if 'subs_default' not in st.session_state: st.session_state.subs_default = True
    
    video_format = st.radio(
        "Escolha o tipo de saída:",
        ["Short (9:16)", "Medium (16:9)"],
        key="video_format",
        on_change=update_slider_defaults,
        disabled=is_reviewing
    )

    use_blur = False 
    if "Short" in video_format:
        st.caption("Estilo do Short:")
        use_blur = st.checkbox("Usar Fundo Borrado (Fit)", value=False, disabled=is_reviewing)
    
    st.divider()
    with st.expander("⏱️ Duração e Tempo", expanded=True):
        min_duration = st.slider("Mínimo (segundos)", 10, 300, key="min_val", disabled=is_reviewing)
        max_duration = st.slider("Máximo (segundos)", 30, 600, key="max_val", disabled=is_reviewing)
    
    st.divider()
    st.header("🎨 Legendas")
    use_subtitles = st.checkbox("Adicionar Legendas Queimadas", key="subs_default", disabled=is_reviewing)
    if use_subtitles:
        text_color = st.color_picker("Cor do Texto", "#FFFF00", disabled=is_reviewing) 
        font_size = st.slider("Tamanho da Fonte", 30, 150, 85, disabled=is_reviewing)
        pos_vertical = st.slider("Posição Vertical", 50, 800, 150, disabled=is_reviewing)
    else:
        text_color, font_size, pos_vertical = "#FFFF00", 85, 150

# --- LAYOUT PRINCIPAL ---
left, right = st.columns([4, 1])

should_refresh = False

with left:
    # ---------------------------------------------------------
    # BARRA DE PROGRESSO (Sempre no topo, se existir job ativo)
    # ---------------------------------------------------------
    if 'last_job_id' in st.session_state and st.session_state.last_job_id:
        job_id = st.session_state.last_job_id
        pct, status = get_job_progress(job_id)
        
        # Usamos st.status para agrupar visualmente e economizar espaço
        # expanded=True deixa aberto enquanto processa
        state_expanded = pct < 100
        
        with st.status(f"🚀 Processando Job...", expanded=state_expanded):
            st.info(f"{status}")
            st.progress(pct / 100)
            
            # Botão pequeno para limpar se travar ou terminar
            if st.button("Limpar / Fechar Status"):
                st.session_state.last_job_id = None
                st.rerun()

        if pct < 100:
            should_refresh = True
        elif pct == 100:
            # Não limpamos o ID automaticamente aqui para o usuário ver que acabou
            st.success("✅ Finalizado! Veja os vídeos na aba Resultados abaixo.")

    # ---------------------------------------------------------
    # PAINEL DE REVISÃO (Aparece abaixo do progresso, se houver)
    # ---------------------------------------------------------
    if is_reviewing:
        p_job = st.session_state.pending_job
        opts = p_job['options']
        
        with st.container(border=True):
            st.markdown("### 🕵️ Confirmar Envio")
            st.info(f"Fonte: **{p_job['source']}**")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**Formato:**\n{opts['format'].upper()}")
                st.markdown(f"**Legendas:**\n{'✅ Sim' if opts['use_subs'] else '❌ Não'}")
            with c2:
                st.markdown(f"**Duração:**\n{opts['min_duration']}s - {opts['max_duration']}s")
                st.markdown(f"**Estilo:**\n{'Fit (Blur)' if opts.get('use_blur') else 'Fill (Zoom)'}")
            with c3:
                if opts['use_subs']:
                    st.caption(f"Cor: {opts['text_color']} | Tamanho: {opts['font_size']}")
            
            st.divider()
            
            b1, b2 = st.columns([1, 4])
            with b1:
                # AO CLICAR AQUI:
                # 1. pending_job vira None (Review fecha)
                # 2. last_job_id é preenchido (Progresso abre no topo)
                if st.button("✅ PROCESSAR", type="primary", use_container_width=True):
                    with st.spinner("Enviando..."):
                        job_id = enqueue_job(p_job['source'], opts)
                        st.session_state['last_job_id'] = job_id
                        st.session_state.pending_job = None
                        st.rerun()
            with b2:
                if st.button("❌ Editar"):
                    if p_job['type'] == 'file': st.session_state.last_active_tab = "file"
                    else: st.session_state.last_active_tab = "youtube"
                    st.session_state.pending_job = None
                    st.rerun()

    # ---------------------------------------------------------
    # ABAS DE INPUT (Sempre visíveis, para iniciar OUTRO job)
    # ---------------------------------------------------------
    # Se estiver revisando, os inputs ficam disabled (ver sidebar e inputs abaixo)
    # Mas se estiver PROCESSANDO (Barra ativa), os inputs ficam LIVRES.
    
    if st.session_state.last_active_tab == "file":
        tab2, tab1, tab3 = st.tabs(["📂 Upload Local", "📺 YouTube", "👀 Resultados"])
    else:
        tab1, tab2, tab3 = st.tabs(["📺 YouTube", "📂 Upload Local", "👀 Resultados"])

    with tab1:
        st.header("Baixar do YouTube")
        url = st.text_input("Cole o link do vídeo aqui:", key="yt_url", disabled=is_reviewing)
        if not is_reviewing:
            if st.button("🔍 Revisar Envio", type="primary", key="btn_yt"):
                if url:
                    st.session_state.last_active_tab = "youtube"
                    st.session_state.pending_job = {"source": url, "type": "youtube", "options": get_options()}
                    st.rerun()
                else:
                    st.warning("Insira uma URL.")

    with tab2:
        uploaded_file = st.file_uploader("Upload de Arquivo (MP4, MOV)", type=["mp4", "mov"], key="file_up", disabled=is_reviewing)
        if not is_reviewing:
            if st.button("🔍 Revisar Envio", type="primary", key="btn_up"):
                if uploaded_file:
                    st.session_state.last_active_tab = "file"
                    filename = save_uploaded_file(uploaded_file)
                    st.session_state.pending_job = {"source": filename, "type": "file", "options": get_options()}
                    st.rerun()
                else:
                    st.warning("Faça o upload primeiro.")

    with tab3:
        st.header("📂 Uploads")
       
        job_options = list_jobs_data() 
        if not job_options:
            st.info("Nenhum job encontrado ainda.")
        else:
            s_label = st.selectbox("Selecione:", list(job_options.keys()), disabled=is_reviewing)
            s_id = job_options[s_label]
            out_dir = settings.get_job_path(s_id) / "outputs"
            
            if out_dir.exists():
                videos = list(out_dir.glob("*.mp4"))
                if videos:
                    zip_f = create_zip(s_id)
                    if zip_f:
                        with open(zip_f, "rb") as f:
                            st.download_button("📦 Baixar ZIP", f, f"shorts_{s_id}.zip", "application/zip", type="primary", disabled=is_reviewing)
                    
                    cols = st.columns(3)
                    for i, v in enumerate(videos):
                        with cols[i % 3]:
                            st.video(str(v))
                            with open(v, "rb") as f:
                                st.download_button("⬇️ Baixar", f, v.name, "video/mp4", key=f"dl_{s_id}_{i}", disabled=is_reviewing)
                else:
                    st.warning("Aguardando vídeos...")

# Preview Lateral
with right:
    st.markdown("### 👁️ Preview")
    if is_reviewing:
        preview_opts = st.session_state.pending_job['options']
        is_vert = preview_opts['format'] == 'vertical'
        blur_val = preview_opts.get('use_blur', False)
        subs_val = preview_opts['use_subs']
        
        preview_img = generate_preview(
            preview_opts['text_color'], 
            preview_opts['font_size'], 
            preview_opts['margin_v'], 
            is_vert, 
            show_text=subs_val, 
            use_blur=blur_val
        )
        st.image(preview_img, caption="REVISÃO (Como será gerado)", width="stretch")
        
    else:
        is_vertical = "Short" in video_format
        current_blur = use_blur if "Short" in video_format else False
        
        preview_img = generate_preview(
            text_color, font_size, pos_vertical, is_vertical, 
            show_text=use_subtitles, use_blur=current_blur
        )
        st.image(preview_img, caption=f"Simulação ({video_format})", width="stretch") 
        if not use_subtitles:
            st.caption("ℹ️ Modo sem legendas")

if should_refresh:
    time.sleep(2)
    st.rerun()