import { useState, useEffect } from 'react';
import { Topbar } from '@shared/components/organisms';
import { useSettings } from '@features/settings/hooks/useSettings';
import { AudioSettingsCard } from '@features/settings/components/organisms/AudioSettingsCard/AudioSettingsCard';
import { SecurityCard } from '@features/settings/components/organisms/SecurityCard/SecurityCard';
import type { SystemSettings, UpdateSettingsPayload } from '@features/settings/types';

export function SettingsView() {
  const { settings, isLoading, isError, updateSettings, isUpdating } = useSettings();
  
  // Local state for edits
  const [localSettings, setLocalSettings] = useState<SystemSettings | null>(null);
  
  // Sync when fetch completes
  useEffect(() => {
    if (settings) {
      setLocalSettings(settings); // NOTE: Safe to run on sync because it handles external API updates vs local edits
    }
  }, [settings]);

  const handleChange = (group: keyof SystemSettings, key: string, value: string | number | boolean) => {
    if (!localSettings) return;
    setLocalSettings(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        [group]: {
          ...prev[group],
          [key]: value
        }
      };
    });
  };

  const handleSave = () => {
    if (localSettings) {
      void updateSettings(localSettings as UpdateSettingsPayload);
    }
  };

  if (isLoading) return <div className="p-8 text-slate-400">Loading settings...</div>;
  if (isError || !localSettings) return <div className="p-8 text-rose-400">Failed to load settings. Ensure backend is running.</div>;

  return (
    <div className="flex flex-col h-full bg-slate-900 overflow-y-auto w-full">
      <Topbar 
        paths={['VoxAgent', 'Settings']}
      />

      <div className="flex-1 p-8 max-w-4xl w-full mx-auto space-y-8 mt-4">
        
        {/* Save Bar */}
        <div className="flex items-center justify-between bg-slate-800/80 backdrop-blur border border-slate-700/50 p-4 rounded-xl sticky top-4 z-10 shadow-lg">
          <div>
            <h4 className="text-white font-medium">Device Configuration</h4>
            <p className="text-sm text-slate-400">Configure hardware integrations, security guardrails, and behaviors.</p>
          </div>
          <button 
            onClick={handleSave}
            disabled={isUpdating}
            className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors cursor-pointer"
          >
            {isUpdating ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>

        <AudioSettingsCard 
          stt={localSettings.stt}
          tts={localSettings.tts}
          wakeWord={localSettings.wake_word}
          onChange={handleChange}
        />

        <SecurityCard 
          security={localSettings.security}
          onChange={handleChange}
        />
        
        <div className="h-12" /> {/* Bottom padding */}
      </div>
    </div>
  );
}
