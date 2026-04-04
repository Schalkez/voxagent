export interface ProviderInfo {
  id: string;
  name: string;
  icon: string;
  provider_type: string;
  status: 'connected' | 'missing';
  has_key: boolean;
}

export interface TestResult {
  ok: boolean;
  latency_ms: number;
  message: string;
}
