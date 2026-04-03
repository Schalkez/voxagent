import React from 'react';
import type { AddSkillCardProps } from '@features/skills/types';

export const AddSkillCard: React.FC<AddSkillCardProps> = ({ onClick }) => {
  return (
    <button
      onClick={onClick}
      className="bg-zinc-950 border border-outline-variant/30 border-dashed rounded-xl flex flex-col items-center justify-center p-8 group hover:bg-zinc-900/30 transition-all cursor-pointer min-h-[280px]"
    >
      <div className="w-12 h-12 rounded-full border border-outline-variant/30 flex items-center justify-center text-zinc-600 group-hover:text-primary group-hover:border-primary/50 transition-all">
        <span className="material-symbols-outlined">add</span>
      </div>
      <span className="mt-4 text-zinc-500 font-label text-xs uppercase tracking-widest">
        Install New Plugin
      </span>
    </button>
  );
};
