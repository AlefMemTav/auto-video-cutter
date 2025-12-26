from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import logging
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MODELOS DE DADOS ---
@dataclass
class Phrase:
    start: float
    end: float
    text: str
    words: List[Dict] = field(default_factory=list)

@dataclass
class Segment:
    start: float
    end: float
    text: str
    duration: float
    words: List[Dict]

# --- CLASSE DO SEGMENTADOR ---
class Segmenter:
    def __init__(self, min_duration: float = 30.0, max_duration: float = 60.0):
        self.min_duration = min_duration
        self.max_duration = max_duration

    def segment(self, phrases: List[Phrase]) -> List[Segment]:
        segments: List[Segment] = []
        current_phrases: List[Phrase] = []
        block_start = 0.0

        for phrase in phrases:
            if not current_phrases:
                block_start = phrase.start

            current_phrases.append(phrase)
            current_duration = phrase.end - block_start

            # Lógica de Decisão Híbrida
            # 1. Se estourou o tempo máximo -> Corta forçado
            # 2. Se está no tempo ideal E tem pontuação -> Corta bonito
            force_cut = current_duration >= self.max_duration
            nice_cut = (current_duration >= self.min_duration) and self._ends_sentence(phrase.text)

            if force_cut or nice_cut:
                seg = self._build_segment(current_phrases)
                if seg:
                    segments.append(seg)
                current_phrases = [] # Reseta para o próximo

        return segments

    def _ends_sentence(self, text: str) -> bool:
        return text.strip().endswith((".", "?", "!"))

    def _build_segment(self, phrases: List[Phrase]) -> Optional[Segment]:
        if not phrases: return None
        
        start = phrases[0].start
        end = phrases[-1].end
        full_text = " ".join(p.text.strip() for p in phrases)
        all_words = [w for p in phrases for w in p.words]

        return Segment(
            start=start, 
            end=end, 
            duration=end - start, 
            text=full_text, 
            words=all_words
        )

# --- FUNÇÕES AUXILIARES DE IO ---
def load_phrases(job_id: str) -> List[Phrase]:
    path = settings.get_job_path(job_id) / "transcript.json"
    if not path.exists():
        raise FileNotFoundError(f"Transcript não encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Converte JSON cru para Objetos Phrase
    return [
        Phrase(
            start=item["start"],
            end=item["end"],
            text=item["text"],
            words=item.get("words", [])
        ) for item in data
    ]

def save_segments(segments: List[Segment], job_id: str) -> str:
    path = settings.get_job_path(job_id) / "segments.json"
    data_out = [
        {
            "start": s.start,
            "end": s.end,
            "duration": s.duration,
            "text": s.text,
            "words": s.words
        } for s in segments
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data_out, f, ensure_ascii=False, indent=2)
    return str(path)