export interface STTConfig {
  provider: string;
  model: string;
  language: string;
}

export interface TTSConfig {
  provider: string;
  voice: string;
  speed: number;
}

export interface WakeWordConfig {
  engine: string;
  phrase: string;
  sensitivity: number;
}

export interface SecurityConfig {
  confirm_dangerous_actions: boolean;
  max_file_delete_without_confirm: number;
}

export interface SystemSettings {
  stt: STTConfig;
  tts: TTSConfig;
  wake_word: WakeWordConfig;
  security: SecurityConfig;
}

// Re-export specific settings pieces if needed by components
export type UpdateSettingsPayload = SystemSettings;
