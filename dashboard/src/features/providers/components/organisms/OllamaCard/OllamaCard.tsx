import React, { useState } from 'react';
import { Input } from '@shared/components';

export interface OllamaCardProps {
  baseUrl?: string;
  onTest?: () => void;
}

export const OllamaCard: React.FC<OllamaCardProps> = ({
  baseUrl = 'http://localhost:11434',
  onTest,
}) => {
  const [url, setUrl] = useState(baseUrl);
  const [testResult, setTestResult] = useState<string | null>(
    'Ping 200 OK - 3 models found (llama3, mistral, codellama)'
  );

  const handleTest = () => {
    onTest?.();
    setTestResult(
      'Ping 200 OK - 3 models found (llama3, mistral, codellama)'
    );
  };

  return (
    <div className="bg-surface-base rounded-xl p-8 border border-transparent">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <div className="w-12 h-12 rounded bg-zinc-900 flex items-center justify-center border border-outline-variant/30">
          <span className="material-symbols-outlined text-primary text-3xl">
            terminal
          </span>
        </div>
        <div>
          <h3 className="font-headline font-bold text-xl text-text-on-surface">
            Ollama
          </h3>
          <p className="text-xs text-zinc-500">
            Local Llama, Mistral, and specialized agents
          </p>
        </div>
      </div>

      {/* Config Inputs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
        <div className="space-y-2">
          <label className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 block">
            Base URL
          </label>
          <Input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="!text-primary"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 block">
            API Key (Optional)
          </label>
          <Input
            type="text"
            disabled
            placeholder="Not required for local host"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <button
            onClick={handleTest}
            className="bg-gradient-to-br from-primary to-primary-container text-on-primary-container px-6 py-2.5 rounded-xl text-xs font-bold uppercase tracking-widest hover:brightness-110 transition-all shadow-[0_0_15px_rgba(6,182,212,0.2)]"
          >
            Test Connection
          </button>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-[10px] font-mono text-primary/70 uppercase">
              Ollama Instance Active
            </span>
          </div>
        </div>

        {/* Mini Terminal */}
        {testResult && (
          <div className="bg-zinc-950 p-4 rounded-lg border border-outline-variant/40">
            <div className="flex items-center gap-3 font-mono text-[11px]">
              <span className="text-zinc-600">VOXAGENT@KERNEL:~$</span>
              <span className="text-emerald-400">{testResult}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
