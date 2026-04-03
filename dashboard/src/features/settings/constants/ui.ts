export const STT_PROVIDERS = [
  { value: 'local', label: 'Local (Faster-Whisper)' },
  { value: 'openai', label: 'OpenAI Whisper API' },
  { value: 'groq', label: 'Groq Whisper' }
];

export const TTS_PROVIDERS = [
  { value: 'piper', label: 'Piper (Local, Fast)' },
  { value: 'edge', label: 'Edge TTS (Cloud, Free)' },
  { value: 'openai', label: 'OpenAI TTS (Cloud)' }
];

export const WAKE_WORD_ENGINES = [
  { value: 'openwakeword', label: 'OpenWakeWord (Recommended)' },
  { value: 'porcupine', label: 'Picovoice Porcupine' }
];

export const SUPPORTED_LANGUAGES = [
  { value: 'vi', label: 'Tiếng Việt' },
  { value: 'en', label: 'English' }
];
