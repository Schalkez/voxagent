/**
 * React hooks for Skills API integration.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@shared/api/client';
import type { PermissionLevel } from '@features/skills/components/organisms/SkillCard/SkillCard';

// ── Types ──

export interface SkillPermission {
  name: string;
  level: PermissionLevel;
}

export interface SkillInfo {
  id: string;
  name: string;
  icon: string;
  version: string;
  author: string;
  description: string;
  enabled: boolean;
  permissions: SkillPermission[];
}

// ── Mock Data ──

const MOCK_SKILLS: SkillInfo[] = [
  {
    id: 'youtube_ad_skipper',
    name: 'YouTube Ad Skipper',
    icon: 'ads_click',
    version: 'v1.0.0',
    author: 'minhtq',
    description: 'Automatically skips YouTube ads using browser control.',
    enabled: true,
    permissions: [
      { name: 'browser:control', level: 'safe' },
      { name: 'screen:read', level: 'elevated' },
    ],
  },
  {
    id: 'terminal_control',
    name: 'Terminal Control',
    icon: 'terminal',
    version: 'v0.9.4',
    author: 'jarvis_core',
    description: 'Execute terminal commands and manage system processes safely.',
    enabled: false,
    permissions: [
      { name: 'terminal:write', level: 'dangerous' },
      { name: 'system:info', level: 'safe' },
    ],
  },
  {
    id: 'spotify_controller',
    name: 'Spotify Controller',
    icon: 'music_note',
    version: 'v2.1.0',
    author: 'audio_team',
    description: 'Seamless playback control and playlist management for Spotify.',
    enabled: true,
    permissions: [
      { name: 'media:control', level: 'safe' },
      { name: 'account:read', level: 'safe' },
    ],
  },
  {
    id: 'browser_automation',
    name: 'Browser Automation',
    icon: 'robot_2',
    version: 'v1.2.3',
    author: 'web_bot',
    description: 'Automate repetitive web tasks and data scraping.',
    enabled: true,
    permissions: [
      { name: 'browser:control', level: 'safe' },
      { name: 'network:access', level: 'elevated' },
    ],
  },
  {
    id: 'voice_recognition',
    name: 'Voice Recognition',
    icon: 'keyboard_voice',
    version: 'v3.0.1',
    author: 'ai_labs',
    description: 'Advanced voice-to-text processing for voice commands.',
    enabled: true,
    permissions: [
      { name: 'audio:record', level: 'dangerous' },
    ],
  },
];

// ── Hooks ──

export function useSkills() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchApi<SkillInfo[]>('/api/skills');
        if (!cancelled) {
          setSkills(data);
          setError(null);
        }
      } catch {
        if (!cancelled) {
          setSkills(MOCK_SKILLS);
          setError('API offline — using mock data');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => { cancelled = true; };
  }, []);

  return { skills, loading, error, setSkills };
}

export function useToggleSkill() {
  const [toggling, setToggling] = useState(false);

  const toggleSkill = useCallback(async (skillId: string, enabled: boolean) => {
    setToggling(true);
    try {
      await fetchApi(`/api/skills/${skillId}/toggle`, {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      });
      return { success: true };
    } catch (err) {
      console.error('[Skills] Toggle failed:', err);
      return { success: false };
    } finally {
      setToggling(false);
    }
  }, []);

  return { toggleSkill, toggling };
}
