import React from 'react';
import { MainLayout } from '@shared/components';

const MOCK_CONVERSATIONS = [
  { id: 1, role: 'user', content: 'Mở Chrome đi', time: '2 phút trước' },
  { id: 2, role: 'assistant', content: 'Đã mở Chrome rồi nha.', time: '2 phút trước' },
  { id: 3, role: 'user', content: 'Tăng âm lượng lên 80', time: '5 phút trước' },
  { id: 4, role: 'assistant', content: 'Đã chỉnh âm lượng ở mức 80 phần trăm.', time: '5 phút trước' },
];

export const MemoryView: React.FC = () => {
  return (
    <MainLayout breadcrumbPaths={['VOXAGENT', 'Memory']}>
      <div className="flex flex-col gap-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold font-headline text-[#FAFAFA]">Agent Memory</h1>
            <p className="text-zinc-400 mt-1">
              Conversation history and user preferences stored in encrypted SQLite.
            </p>
          </div>
          <span className="px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-medium border border-amber-500/20">
            Coming in Phase 2
          </span>
        </div>

        {/* Preview conversation history */}
        <div className="space-y-3">
          {MOCK_CONVERSATIONS.map((msg) => (
            <div
              key={msg.id}
              className={`p-3 rounded-lg opacity-60 cursor-not-allowed ${
                msg.role === 'user'
                  ? 'bg-primary/5 border border-primary/10 ml-8'
                  : 'bg-surface-container/40 border border-outline-variant/20 mr-8'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-zinc-400">
                  {msg.role === 'user' ? '👤 You' : '🤖 VoxAgent'}
                </span>
                <span className="text-xs text-zinc-600">{msg.time}</span>
              </div>
              <p className="text-sm text-[#FAFAFA]">{msg.content}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-outline-variant/20 bg-surface-container/40 opacity-60">
            <p className="text-xs text-zinc-500 mb-1">Total Conversations</p>
            <p className="text-2xl font-bold text-[#FAFAFA]">—</p>
          </div>
          <div className="p-4 rounded-xl border border-outline-variant/20 bg-surface-container/40 opacity-60">
            <p className="text-xs text-zinc-500 mb-1">Preferences Saved</p>
            <p className="text-2xl font-bold text-[#FAFAFA]">—</p>
          </div>
        </div>

        <div className="p-6 rounded-xl border border-dashed border-outline-variant/30 bg-surface-container/20 text-center">
          <p className="text-zinc-500 text-sm">
            Memory module will store conversation history, user preferences, and per-skill state.
          </p>
          <p className="text-zinc-600 text-xs mt-2">
            Data encrypted with SQLCipher, keys stored in OS keyring.
          </p>
        </div>
      </div>
    </MainLayout>
  );
};
