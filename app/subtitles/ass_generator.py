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

def hex_to_ass_color(hex_color: str) -> str:
    """Converte HEX (#RRGGBB) para ASS (&H00BBGGRR)"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[:2], hex_color[2:4], hex_color[4:]
        # ASS usa BGR e o prefixo &H00
        return f"&H00{b}{g}{r}"
    return "&H0000FFFF" # Amarelo padrão fallback

def generate_ass_header(
    font_name="Arial", 
    font_size=85, 
    primary_color="#FFFF00", 
    outline_color="#000000", 
    margin_v=250,
    play_res_x=1080,
    play_res_y=1920
) -> str:
    
    ass_primary = hex_to_ass_color(primary_color)
    ass_outline = hex_to_ass_color(outline_color)
    
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, Outline, Shadow
Style: Default,{font_name},{font_size},{ass_primary},{ass_outline},&H80000000,-1,0,2,20,20,{margin_v},4,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def create_ass_file(segment: Dict, output_path: Path, options: Dict = None):
    if options is None:
        options = {}
    
    """
    Gera o arquivo .ass quebrando as palavras em linhas curtas.
    """
    words = segment.get('words', [])

    res_x = options.get('res_x', 1080)
    res_y = options.get('res_y', 1920)

    # Se não tiver dados de palavras (fallback), usa o texto cru
    if not words:
        start = seconds_to_ass_time(0)
        end = seconds_to_ass_time(segment['duration'])
        text = segment['text']

        content = generate_ass_header(play_res_x=res_x, play_res_y=res_y)

        content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return
    
    f_name = options.get('font_name', 'Arial')
    if f_name == "Padrão":
        f_name = "Arial"

    ass_content = generate_ass_header(
        font_name=f_name,
        font_size=options.get('font_size', 85),
        primary_color=options.get('text_color', '#FFFF00'),
        margin_v=options.get('margin_v', 250),
        play_res_x=res_x,
        play_res_y=res_y
    )
    
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