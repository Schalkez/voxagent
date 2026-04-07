import { Input, Slider, Text } from '@shared/components/atoms';
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
        <span className="material-symbols-rounded text-cyan-400">mic</span>
        <Text variant="headline" className="text-lg">Audio & Voice Ops</Text>
      </div>
      
      <div className="space-y-6">
        <div>
          <Text variant="label" className="block mb-3 opacity-60">Wake Word Detection</Text>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Text variant="label" as="label" className="block mb-2 py-px">Engine</Text>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={wakeWord.engine}
                onChange={(e) => onChange('wake_word', 'engine', e.target.value)}
              >
                {WAKE_WORD_ENGINES.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Text variant="label" as="label" className="block mb-2">Sensitivity ({wakeWord.sensitivity})</Text>
              <Slider 
                min={0.1} max={1.0} step={0.1} 
                value={wakeWord.sensitivity}
                onChange={(e) => onChange('wake_word', 'sensitivity', parseFloat(e.target.value))}
              />
            </div>
            <div className="space-y-1 py-px">
              <Text variant="label" as="label" className="block mb-2">Wake Phrase</Text>
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
          <Text variant="label" className="block mb-3 opacity-60">Speech-to-Text</Text>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Text variant="label" as="label" className="block mb-2 py-px">STT Provider</Text>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={stt.provider}
                onChange={(e) => onChange('stt', 'provider', e.target.value)}
              >
                {STT_PROVIDERS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div>
              <Text variant="label" as="label" className="block mb-2 py-px">Default Language</Text>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={stt.language}
                onChange={(e) => onChange('stt', 'language', e.target.value)}
              >
                {SUPPORTED_LANGUAGES.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Text variant="label" as="label" className="block mb-2">Model</Text>
              <Input 
                value={stt.model}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange('stt', 'model', e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="h-px bg-slate-700/50 w-full" />

        <div>
           <Text variant="label" className="block mb-3 opacity-60">Text-to-Speech</Text>
           <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Text variant="label" as="label" className="block mb-2 py-px">TTS Provider</Text>
              <select 
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700/50 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                value={tts.provider}
                onChange={(e) => onChange('tts', 'provider', e.target.value)}
              >
                {TTS_PROVIDERS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <Text variant="label" as="label" className="block mb-2">Voice Profile</Text>
              <Input 
                value={tts.voice}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange('tts', 'voice', e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Text variant="label" as="label" className="block mb-2">Speaking Speed ({tts.speed}x)</Text>
              <Slider 
                min={0.5} max={2.0} step={0.1} 
                value={tts.speed}
                onChange={(e) => onChange('tts', 'speed', parseFloat(e.target.value))}
              />
            </div>
           </div>
        </div>
      </div>
    </div>
  );
}
