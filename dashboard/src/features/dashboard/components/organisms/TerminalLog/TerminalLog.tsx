import React from 'react';

export const TerminalLog: React.FC = () => {
  return (
    <div className="bg-black border border-white/10 rounded-lg overflow-hidden shadow-[0_24px_48px_-12px_rgba(0,0,0,0.5)]">
      <div className="bg-white/5 px-4 py-2 border-b border-white/5 flex justify-between items-center">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-white/10"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-white/10"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-white/10"></div>
          <span className="text-[10px] text-text-on-surface-variant ml-4 font-mono">SYSTEM_LOG_STREAM_0.1</span>
        </div>
        <span className="text-[10px] uppercase text-primary-container font-mono">Live Output</span>
      </div>
      <div className="p-6 text-[13px] leading-relaxed flex flex-col gap-2 font-mono">
        <div className="flex gap-4">
          <span className="text-text-on-surface-variant/70 shrink-0">[10:42:01 AM]</span>
          <p>
            User: <span className="text-gray-200">"skip ad"</span> <span className="text-white/20 px-2">-&gt;</span> VoxAgent: <span className="text-primary-container">Executed youtube_ad_skipper (Tier 0)</span>
          </p>
        </div>
        <div className="flex gap-4">
          <span className="text-text-on-surface-variant/70 shrink-0">[10:41:55 AM]</span>
          <p>
            User: <span className="text-gray-200">"play lofi radio"</span> <span className="text-white/20 px-2">-&gt;</span> VoxAgent: <span className="text-primary-container">Initialised Spotify_Controller_Module</span>
          </p>
        </div>
        <div className="mt-4 animate-pulse">
          <span className="text-primary-container">_</span>
        </div>
      </div>
    </div>
  );
};
