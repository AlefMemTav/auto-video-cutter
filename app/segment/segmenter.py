import json
import logging
from dataclasses import dataclass
from typing import List, Dict

logger = logging.getLogger(__name__)

STRONG_PUNCTUATION = ('.', '?', '!')

WEAK_ENDINGS = ("e", "mas", "porque", "entao", "então", "assim", "ne", "né", "tipo", "ou", "que")

BAD_STARTERS = ("e", "mas", "entao", "então", "tipo", "assim", "bom", "ai", "aí", "cara", "olha")

LONG_PAUSE_THRESHOLD = 0.7  # Segundos para considerar silêncio relevante

# Pesos da Heurística
SCORE_STRONG_PUNCT = 10     # Ponto final é ouro
SCORE_LONG_PAUSE = 8        # Silêncio é prata
SCORE_WEAK_ENDING = -20     # Terminar com "e" é proibido
SCORE_TIME_BONUS_MAX = 5    # Incentivo para vídeos mais longos

@dataclass
class Segment:
    start: float
    end: float
    text: str
    duration: float
    words: List[Dict]

def load_phrases(job_id: str):
    from app.config.settings import settings
    path = settings.get_job_path(job_id) / "transcript.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_segments(segments: List[Segment], job_id: str):
    from app.config.settings import settings
    path = settings.get_job_path(job_id) / "segments.json"
    data = [{
        "start": s.start, "end": s.end, "duration": s.duration,
        "text": s.text, "words": s.words
    } for s in segments]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class Segmenter:
    def __init__(self, min_duration=30, max_duration=60):
        self.min_duration = min_duration
        self.max_duration = max_duration
    
    def segment(self, transcription_data: Dict) -> List[Segment]:
        # Flatten
        all_words = []
        if 'segments' in transcription_data:
            for seg in transcription_data['segments']:
                if 'words' in seg:
                    all_words.extend(seg['words'])
        
        # --- DEBUG LINE ---
        logger.info(f"🔍 DEBUG: Total de palavras encontradas no JSON: {len(all_words)}")
        
        if not all_words: 
            logger.warning("❌ ERRO: Nenhuma palavra encontrada! Verifique se o Whisper está gerando 'word_timestamps'.")
            return []

        video_segments = []
        index = 0
        total_words = len(all_words)

        while index < total_words:
            # Encontra o MELHOR ponto de corte olhando adiante
            best_cut_index = self._find_best_cut_in_window(all_words, index)
            
            if best_cut_index == -1:
                break
            
            # Extrai o segmento bruto
            segment_words = all_words[index : best_cut_index + 1]
            
            # Limpa o início (Remove "Então...", "E...")
            segment_words = self._clean_hook(segment_words)
            
            if segment_words:
                self._create_segment(video_segments, segment_words)
            
            # Avança o cursor para a próxima palavra após o corte
            index = best_cut_index + 1

        return video_segments

    def _find_best_cut_in_window(self, all_words, start_index):
        """
        Analisa o futuro (Lookahead) para encontrar o corte com maior Score.
        """
        best_score = float('-inf')
        best_index = -1
        
        start_time = all_words[start_index]['start']
        max_idx = len(all_words) - 1

        for i in range(start_index, len(all_words)):
            word = all_words[i]
            current_duration = word['end'] - start_time
            
            # 1. Muito curto? Ignora e continua avançando.
            if current_duration < self.min_duration:
                continue
            
            # 2. Estourou o tempo máximo?
            if current_duration > self.max_duration:
                if best_index == -1:
                    return i - 1  # Safety Cut
                else:
                    return best_index 

            # --- CÁLCULO DE SCORE ---
            score = 0
            text = word['word'].lower().strip()
            text_clean = ''.join(c for c in text if c.isalnum())
            
            # Checa Pausa
            pause_duration = 0
            if i < max_idx:
                pause_duration = all_words[i+1]['start'] - word['end']
            
            # Critério 1: Pontuação (Usa o text com pontuação)
            if any(text.endswith(p) for p in STRONG_PUNCTUATION):
                score += SCORE_STRONG_PUNCT
            
            # Critério 2: Pausa de Áudio
            if pause_duration > LONG_PAUSE_THRESHOLD:
                score += SCORE_LONG_PAUSE
            
            # Critério 3: Terminação Ruim (Usa text_clean)
            if text_clean in WEAK_ENDINGS:
                score += SCORE_WEAK_ENDING

            # Critério 4: Bônus de Tempo
            time_bonus = (current_duration / self.max_duration) * SCORE_TIME_BONUS_MAX
            score += time_bonus

            if score > best_score:
                best_score = score
                best_index = i
        
        if best_index != -1:
            return best_index
        
        return -1

    def _clean_hook(self, words):
        """
        Remove vícios de linguagem do início.
        Limite de segurança (max 2 palavras) para não perder contexto.
        """
        removed_count = 0
        while len(words) > 1 and removed_count < 2:
            first_text = words[0]['word'].strip().lower()
            clean_word = ''.join(c for c in first_text if c.isalnum())
            
            if clean_word in BAD_STARTERS:
                # Só remove se não deixar o vídeo curto demais
                dur = words[-1]['end'] - words[1]['start']
                if dur >= self.min_duration:
                    words.pop(0)
                    removed_count += 1
                    continue
            break
        return words

    def _create_segment(self, segments_list, words):
        start = words[0]['start']
        end = words[-1]['end']
        duration = end - start
        text = "".join([w['word'] for w in words]).strip()
        
        new_seg = Segment(start=start, end=end, text=text, duration=duration, words=words)
        segments_list.append(new_seg)