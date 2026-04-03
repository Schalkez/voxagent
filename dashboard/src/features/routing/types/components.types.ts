/**
 * Component prop types for the Routing feature.
 */

import type { PresetId } from './routing.types';

export interface RoutingPresetCardProps {
  id: PresetId;
  icon: string;
  title: string;
  subtitle: string;
  active?: boolean;
  onClick?: (id: PresetId) => void;
}

export interface TierCardProps {
  tier: number;
  title: string;
  description: string;
  provider: string;
  model: string;
  providerOptions: string[];
  modelOptions: string[];
  onProviderChange?: (value: string) => void;
  onModelChange?: (value: string) => void;
  warning?: string;
}

export interface RoutingStatusChipProps {
  status?: string;
}
