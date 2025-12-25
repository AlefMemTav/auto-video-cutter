import textwrap
from pathlib import Path
from typing import List, Dict

def seconds_to_ass_time(seconds: float) -> str:
    """Converte segundos (125.5) para formato ASS (0:02:05.50)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

def generate_ass_header() -> str:
    """
    Estilo da Legenda:
    - Fonte: Sans (Geralmente segura no Linux) ou Roboto
    - Cor: Amarelo (&H0000FFFF)
    - Outline: Preto Grosso (3)
    - Posição: MarginV=250 (Evita cobrir UI do TikTok)
    """
    return """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, Outline, Shadow
Style: Default,Arial,85,&H0000FFFF,&H00000000,&H80000000,-1,0,2,20,20,250,4,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def create_ass_file(segment: Dict, output_path: Path):
    """
    Gera o arquivo .ass quebrando as palavras em linhas curtas.
    """
    words = segment.get('words', [])
    
    # Se não tiver dados de palavras (fallback), usa o texto cru
    if not words:
        start = seconds_to_ass_time(0)
        end = seconds_to_ass_time(segment['duration'])
        text = segment['text']
        content = generate_ass_header()
        content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return

    ass_content = generate_ass_header()
    
    # --- Lógica de Agrupamento de Palavras (Caption Grouping) ---
    current_group = []
    group_start_time = 0.0
    
    # Ajuste o offset relativo ao inicio do segmento
    segment_start_abs = segment['start']

    for i, w in enumerate(words):
        # Tempo relativo ao corte (O vídeo cortado começa em 00:00)
        rel_start = w['start'] - segment_start_abs
        rel_end = w['end'] - segment_start_abs
        
        if not current_group:
            group_start_time = rel_start

        current_group.append(w['word'])
        
        # Critérios para quebrar a linha:
        # 1. Se acumulou mais de 4 palavras
        # 2. OU se a frase ficou longa (> 20 chars)
        # 3. OU se tem pontuação forte
        chars = sum(len(x) for x in current_group)
        is_long = len(current_group) >= 4 or chars > 20
        has_punct = w['word'].endswith(('.', '?', '!'))
        
        if is_long or has_punct or i == len(words) - 1:
            # Fecha o grupo
            text_line = " ".join(current_group)
            start_fmt = seconds_to_ass_time(group_start_time)
            end_fmt = seconds_to_ass_time(rel_end)
            
            ass_content += f"Dialogue: 0,{start_fmt},{end_fmt},Default,,0,0,0,,{text_line}\n"
            
            # Reseta
            current_group = []

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)