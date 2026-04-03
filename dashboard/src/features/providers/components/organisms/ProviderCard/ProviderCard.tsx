import React, { useState } from 'react';
import { Input } from '@shared/components';

export interface ProviderCardProps {
  name: string;
  icon: string;
  status: 'connected' | 'missing';
  apiKey?: string;
  onSave?: (key: string) => void;
}

export const ProviderCard: React.FC<ProviderCardProps> = ({
  name,
  icon,
  status,
  apiKey,
  onSave,
}) => {
  const [showKey, setShowKey] = useState(false);
  const [keyValue, setKeyValue] = useState(apiKey || '');

  const isConnected = status === 'connected';

  return (
    <div className="bg-surface-base rounded-xl p-6 border border-transparent hover:border-primary/10 transition-all">
      {/* Header */}
      <div className="flex justify-between items-start mb-8">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded bg-zinc-900 flex items-center justify-center border border-outline-variant/30">
            <span className="material-symbols-outlined text-zinc-400">
              {icon}
            </span>
          </div>
          <h3 className="font-headline font-bold text-lg text-text-on-surface">
            {name}
          </h3>
        </div>
        <span
          className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${
            isConnected
              ? 'bg-primary-container/10 text-primary-container'
              : 'bg-error/10 text-error'
          }`}
        >
          {isConnected ? 'Connected' : 'Missing Key'}
        </span>
      </div>

      {/* API Key Input */}
      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 block">
            API Key
          </label>
          <Input
            type={showKey ? 'text' : 'password'}
            value={keyValue}
            onChange={(e) => setKeyValue(e.target.value)}
            readOnly={isConnected}
            placeholder={isConnected ? undefined : 'Enter API Key'}
            rightIcon={showKey ? 'visibility_off' : 'visibility'}
            onRightIconClick={() => setShowKey((v) => !v)}
            className="!border-0"
          />
        </div>

        {/* Save Button */}
        <div className="flex justify-end pt-2">
          <button
            onClick={() => onSave?.(keyValue)}
            className="px-4 py-2 rounded-xl border border-outline-variant/50 text-[10px] font-bold uppercase tracking-widest text-zinc-400 hover:border-primary hover:text-primary transition-all"
          >
            Save to Keyring
          </button>
        </div>
      </div>
    </div>
  );
};
