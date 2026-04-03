/**
 * Routing preset definitions.
 */

import type { PresetId } from '@features/routing/types';

export const ROUTING_PRESETS: { id: PresetId; icon: string; title: string; subtitle: string }[] = [
  { id: 'local', icon: 'cloud_off', title: 'Fully Local (Offline)', subtitle: 'Privacy Focus' },
  { id: 'balanced', icon: 'bolt', title: 'Speed & Free Cloud', subtitle: 'Efficiency Balanced' },
  { id: 'performance', icon: 'rocket_launch', title: 'Max Performance', subtitle: 'Complex Reasoner' },
];
