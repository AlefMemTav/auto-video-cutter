import datetime
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
def save_uploaded_file(uploaded_file):
    """Salva o arquivo de upload na pasta 'inputs' do Docker"""
    # Garante que a pasta inputs existe
    inputs_dir = Path("/app/inputs")
    inputs_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = inputs_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return uploaded_file.name

def enqueue_job(source):
    """Envia o trabalho para o Worker"""
    # Importante: Importar a função dentro do job para evitar erro de pickling
    from app.jobs.worker import process_video_pipeline
    
    job = q.enqueue(
        process_video_pipeline,
        args=(source,),
        job_timeout=3600  # 1 hora de timeout
    )
    return job.id

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