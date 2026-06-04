from enum import Enum, auto


class TaskStatus(str, Enum):
    PENDING = "pending"
    TRANSLATING = "translating"
    GENERATING_TTS = "generating_tts"
    ASSEMBLING_AUDIO = "assembling_audio"
    MUXING_VIDEO = "muxing_video"
    COMPLETED = "completed"
    FAILED = "failed"


class OutputMode(str, Enum):
    REPLACE = "replace"
    ADD_TRACK = "add_track"
