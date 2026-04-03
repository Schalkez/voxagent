/**
 * Domain types for the Routing feature.
 */

export type PresetId = 'local' | 'balanced' | 'performance';

export interface TierConfig {
  tier: number;
  title: string;
  description: string;
  provider: string;
  model: string;
  provider_options: string[];
  model_options: string[];
  warning?: string | undefined;
}

export interface RoutingConfig {
  preset: PresetId;
  tiers: TierConfig[];
  status: string;
}
