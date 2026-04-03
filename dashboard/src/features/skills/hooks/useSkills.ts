/**
 * React hooks for Skills API integration.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchApi } from '@shared/api/client';
import type { SkillInfo } from '@features/skills/types';
import { MOCK_SKILLS } from '@features/skills/constants';

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
