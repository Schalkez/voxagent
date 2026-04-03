import { Input } from '@shared/components/atoms';
import type { SystemSettings } from '@features/settings/types';
import { STT_PROVIDERS, TTS_PROVIDERS, WAKE_WORD_ENGINES, SUPPORTED_LANGUAGES } from '@features/settings/constants';

interface AudioSettingsCardProps {
  stt: SystemSettings['stt'];
  tts: SystemSettings['tts'];
  wakeWord: SystemSettings['wake_word'];
  onChange: (group: keyof SystemSettings, key: string, value: string | number) => void;
}

export function AudioSettingsCard({ stt, tts, wakeWord, onChange }: AudioSettingsCardProps) {
  return (
    <div className="bg-slate-800/40 rounded-xl border border-slate-700/50 p-6 shadow-sm backdrop-blur-sm">
      <div className="flex items-center gap-3 mb-6">
        <span className="material-symbols-rounded text-indigo-400">mic</span>
        <h3 className="text-lg font-semibold text-white">Audio & Voice Ops</h3>
      </div>
      
      <div className="space-y-6">
        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-3">Wake Word Detection</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Engine</label>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={wakeWord.engine}
                onChange={(e) => onChange('wake_word', 'engine', e.target.value)}
              >
                {WAKE_WORD_ENGINES.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-300">Sensitivity ({wakeWord.sensitivity})</label>
              <input 
                type="range" 
                min="0.1" max="1.0" step="0.1" 
                value={wakeWord.sensitivity}
                onChange={(e) => onChange('wake_word', 'sensitivity', parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
              />
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-medium text-slate-300 mb-1">Wake Phrase</label>
              <Input 
                value={wakeWord.phrase}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange('wake_word', 'phrase', e.target.value)}
                placeholder="e.g. hey vox"
              />
            </div>
          </div>
        </div>

        <div className="h-px bg-slate-700/50 w-full" />

        <div>
          <h4 className="text-sm font-medium text-slate-400 mb-3">Speech-to-Text</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">STT Provider</label>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={stt.provider}
                onChange={(e) => onChange('stt', 'provider', e.target.value)}
              >
                {STT_PROVIDERS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Default Language</label>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={stt.language}
                onChange={(e) => onChange('stt', 'language', e.target.value)}
              >
                {SUPPORTED_LANGUAGES.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-medium text-slate-300 mb-1">Model</label>
              <Input 
                value={stt.model}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange('stt', 'model', e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="h-px bg-slate-700/50 w-full" />

        <div>
           <h4 className="text-sm font-medium text-slate-400 mb-3">Text-to-Speech</h4>
           <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">TTS Provider</label>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={tts.provider}
                onChange={(e) => onChange('tts', 'provider', e.target.value)}
              >
                {TTS_PROVIDERS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-medium text-slate-300 mb-1">Voice Profile</label>
              <Input 
                value={tts.voice}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange('tts', 'voice', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium text-slate-300">Speaking Speed ({tts.speed}x)</label>
              <input 
                type="range" 
                min="0.5" max="2.0" step="0.1" 
                value={tts.speed}
                onChange={(e) => onChange('tts', 'speed', parseFloat(e.target.value))}
                className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
              />
            </div>
           </div>
        </div>
      </div>
    </div>
  );
}
