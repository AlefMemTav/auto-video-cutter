import datetime
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

if 'pending_job' not in st.session_state:
    st.session_state.pending_job = None

if 'last_active_tab' not in st.session_state:
    st.session_state.last_active_tab = "youtube"

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

# --- FUNÇÕES AUXILIARES ---

@st.cache_data(ttl=2, show_spinner=False)
def get_logs(lines=50):
    log_path = settings.STORAGE_DIR / "logs" / "worker.log"
    if not log_path.exists():
        return ["Aguardando início dos logs..."]
    try:
        with open(log_path, "r") as f:
            return f.readlines()[-lines:]
    except Exception:
        return ["Erro ao ler logs."]

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
        try:
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            draw.text((w/2, y_pos - 15), "Fundo Borrado", font=small_font, fill="white", anchor="ms")
        except:
            pass

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
    job = q.enqueue(process_video_pipeline, args=(source, None, options), job_timeout=3600)
    return job.id

# --- CONFIGURAÇÕES LATERAIS ---
with st.sidebar:
    st.header("⚙️ Configurações de Corte")
    st.subheader("📐 Formato do Vídeo")
    
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

with left:
    if is_reviewing:
        p_job = st.session_state.pending_job
        opts = p_job['options']
        
        with st.container(border=True):
            st.markdown("### 🕵️ Confirmação")
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
                # CONFIRMAR (Envia o job)
                if st.button("✅ PROCESSAR", type="primary", use_container_width=True):
                    with st.spinner("Enviando..."):
                        job_id = enqueue_job(p_job['source'], opts)
                        st.success(f"Enviado! ID: {job_id}")
                        st.session_state['last_job_id'] = job_id
                        st.session_state.pending_job = None
                        st.rerun()
            with b2:
                # CANCELAR (Só limpa o estado, inputs abaixo voltam a ficar ativos)
                if st.button("❌ Editar Configurações"):
                    if p_job['type'] == 'file':
                        st.session_state.last_active_tab = "file"
                    else:
                        st.session_state.last_active_tab = "youtube"
                
                    st.session_state.pending_job = None
                    st.rerun()
    
    if st.session_state.last_active_tab == "file":
        tab2, tab1, tab3 = st.tabs(["📂 Upload Local (Andamento)", "📺 YouTube", "👀 Resultados"])
    else:
        tab1, tab2, tab3 = st.tabs(["📺 YouTube (Andamento)", "📂 Upload Local", "👀 Resultados"])

    with tab1:
        st.header("Baixar do YouTube")
        # Input travado na revisão
        url = st.text_input("Cole o link do vídeo aqui:", key="yt_url", disabled=is_reviewing)
        
        if not is_reviewing:
            if st.button("🔍 Revisar Configurações", type="primary", key="btn_yt"):
                if url:
                    st.session_state.last_active_tab = "youtube"
                    st.session_state.pending_job = {
                        "source": url,
                        "type": "youtube",
                        "options": get_options()
                    }
                    st.rerun()
                else:
                    st.warning("Insira uma URL.")

    with tab2:
        st.header("Upload de Arquivo (MP4)")
        uploaded_file = st.file_uploader("Escolha um vídeo", type=["mp4", "mov", "mkv"], key="file_up", disabled=is_reviewing)
        
        if not is_reviewing:
            if st.button("🔍 Revisar Configurações", type="primary", key="btn_up"):
                if uploaded_file:
                    st.session_state.last_active_tab = "file"
                    
                    filename = save_uploaded_file(uploaded_file)
                    st.session_state.pending_job = {
                        "source": filename,
                        "type": "file",
                        "options": get_options()
                    }
                    st.rerun()
                else:
                    st.warning("Faça o upload primeiro.")

    with tab3:
        st.header("📂 Gerenciador de Jobs")
        job_options = list_jobs_data() 
        
        if not job_options:
            st.info("Nenhum job encontrado ainda.")
        else:
            selected_label = st.selectbox("Selecione um Job:", list(job_options.keys()), disabled=is_reviewing)
            selected_job_id = job_options[selected_label]
            st.divider()
            
            job_path = settings.get_job_path(selected_job_id)
            output_dir = job_path / "outputs"
            
            if output_dir.exists():
                videos = list(output_dir.glob("*.mp4"))
                if videos:
                    st.success(f"🎬 {len(videos)} Shorts")
                    zip_file = create_zip(selected_job_id)
                    if zip_file:
                        with open(zip_file, "rb") as f:
                            st.download_button("📦 BAIXAR TUDO (ZIP)", f, f"shorts_{selected_job_id}.zip", "application/zip", type="primary", disabled=is_reviewing)
                    
                    cols = st.columns(3)
                    for i, video_path in enumerate(videos):
                        with cols[i % 3]:
                            st.video(str(video_path))
                            with open(video_path, "rb") as file:
                                st.download_button("⬇️ Baixar", file, video_path.name, "video/mp4", key=f"dl_{selected_job_id}_{i}", disabled=is_reviewing)
                else:
                    st.warning("⏳ Processando...")
            else:
                st.error("Pasta não encontrada.")

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