import React, { useMemo, useState } from 'react';
import { MainLayout, Input, Select } from '@shared/components';
import {
  SkillCard,
  AddSkillCard,
  SkillsFooter,
} from '@features/skills/components/organisms';
import { SKILL_CATEGORIES } from '@features/skills/constants';
import { useSkills, useToggleSkill } from '@features/skills/hooks/useSkills';

export const SkillsView: React.FC = () => {
  const { skills, loading, error, setSkills } = useSkills();
  const { toggleSkill } = useToggleSkill();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All Categories');

  const filteredSkills = useMemo(() => {
    let result = skills;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          s.permissions.some((p) => p.name.toLowerCase().includes(q))
      );
    }
    if (category !== 'All Categories') {
      const cat = category.toLowerCase();
      result = result.filter(
        (s) =>
          s.description.toLowerCase().includes(cat) ||
          s.permissions.some((p) => p.name.toLowerCase().includes(cat))
      );
    }
    return result;
  }, [skills, search, category]);

  const activeCount = skills.filter((s) => s.enabled).length;

  const handleToggle = async (skillId: string, enabled: boolean) => {
    setSkills(
      skills.map((s) => (s.id === skillId ? { ...s, enabled } : s))
    );
    void toggleSkill(skillId, enabled);
  };

  if (loading) {
    return (
      <MainLayout breadcrumbPaths={['VOXAGENT', 'Skills']}>
        <div className="flex items-center justify-center min-h-[400px]">
          <span className="text-zinc-500 font-mono text-sm animate-pulse uppercase tracking-widest">
            Loading skills...
          </span>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Skills']}>
      <div className="flex flex-col min-h-[calc(100vh-64px)]">
        <section className="p-8 flex-1">
          {error && (
            <div className="mb-8 px-4 py-2 rounded-lg bg-tertiary/10 border border-tertiary/20 text-tertiary text-[11px] font-mono uppercase tracking-wider">
              {error}
            </div>
          )}

          {/* ── Control Bar ── */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-10">
            <div className="flex-1 max-w-xl">
              <Input
                type="text"
                placeholder="Search skills, capabilities, or permissions..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                leftIcon="search"
              />
            </div>
            <div className="flex items-center gap-3">
              <Select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {SKILL_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </Select>
              <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-outline-variant/20 bg-zinc-900/50 text-xs font-label text-text-on-surface hover:bg-zinc-800 transition-colors group">
                <span className="material-symbols-outlined text-sm group-active:rotate-180 transition-transform duration-500">
                  refresh
                </span>
                Reload Skills
              </button>
            </div>
          </div>

          {/* ── Skills Grid ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredSkills.map((skill) => (
              <SkillCard
                key={skill.id}
                name={skill.name}
                icon={skill.icon}
                version={skill.version}
                author={skill.author}
                description={skill.description}
                enabled={skill.enabled}
                permissions={skill.permissions}
                onToggle={(enabled) => void handleToggle(skill.id, enabled)}
              />
            ))}
            <AddSkillCard onClick={() => console.log('[Skills] Install new plugin')} />
          </div>
        </section>

        <SkillsFooter
          activeCount={activeCount}
          systemHealth="99.8%"
          lastUpdate={new Date().toISOString().replace('T', ' ').slice(0, 19)}
        />
      </div>
    </MainLayout>
  );
};
