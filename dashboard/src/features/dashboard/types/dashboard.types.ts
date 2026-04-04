export interface DashboardStatus {
  status: 'online' | 'offline' | 'error';
  listening: boolean;
  skills: {
    active: number;
    total: number;
  };
  providers: {
    llm: string[];
    stt: string[];
    tts: string[];
  };
  stats: {
    daily_commands: number;
    avg_latency_ms: number;
    uptime_seconds: number;
  };
}
