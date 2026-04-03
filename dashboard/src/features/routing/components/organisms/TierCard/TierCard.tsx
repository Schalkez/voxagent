import React from 'react';
import { Select } from '@shared/components';

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

export const TierCard: React.FC<TierCardProps> = ({
  tier,
  title,
  description,
  provider,
  model,
  providerOptions,
  modelOptions,
  onProviderChange,
  onModelChange,
  warning,
}) => {
  return (
    <div className="flex flex-col lg:flex-row items-start lg:items-center gap-8 p-8 rounded-xl bg-surface-base border border-outline-variant/30 hover:border-outline-variant/50 transition-colors group">
      {/* Left: Tier badge + info */}
      <div className="flex items-center gap-6 flex-1 w-full">
        <div className="w-12 h-12 rounded-lg bg-zinc-900 border border-outline-variant/30 flex items-center justify-center shrink-0">
          <span className="text-primary font-bold font-mono">T{tier}</span>
        </div>
        <div className="flex flex-col">
          <h3 className="text-text-on-surface font-bold text-lg font-headline">
            {title}
          </h3>
          <p className="text-zinc-500 text-sm">{description}</p>
        </div>
      </div>

      {/* Right: Dropdowns */}
      <div className="flex flex-col sm:flex-row gap-4 w-full lg:w-auto">
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] text-zinc-600 font-bold uppercase tracking-widest px-1">
            Provider
          </label>
          <Select
            value={provider}
            onChange={(e) => onProviderChange?.(e.target.value)}
            className="min-w-[140px]"
          >
            {providerOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] text-zinc-600 font-bold uppercase tracking-widest px-1">
            Model
          </label>
          <div className="flex flex-col gap-2">
            <Select
              value={model}
              onChange={(e) => onModelChange?.(e.target.value)}
              className="min-w-[220px] font-mono"
            >
              {modelOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </Select>
            {warning && (
              <div className="flex items-center gap-1.5 px-1">
                <span className="material-symbols-outlined text-tertiary text-[14px]">
                  warning
                </span>
                <span className="text-[10px] text-tertiary font-bold uppercase tracking-tighter">
                  {warning}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
