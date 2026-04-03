import { Switch, Input } from '@shared/components/atoms';
import type { SystemSettings } from '@features/settings/types';

interface SecurityCardProps {
  security: SystemSettings['security'];
  onChange: (group: keyof SystemSettings, key: string, value: boolean | number) => void;
}

export function SecurityCard({ security, onChange }: SecurityCardProps) {
  return (
    <div className="bg-slate-800/40 rounded-xl border border-red-900/30 p-6 shadow-sm backdrop-blur-sm">
      <div className="flex items-center gap-3 mb-6">
        <span className="material-symbols-rounded text-rose-400">security</span>
        <h3 className="text-lg font-semibold text-white">Security & Guardrails</h3>
      </div>
      
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-slate-200">Confirm Dangerous Actions</div>
            <div className="text-xs text-slate-400">Prompt for confirmation before executing system commands or file deletion.</div>
          </div>
          <Switch 
            checked={security.confirm_dangerous_actions}
            onChange={(val: boolean) => onChange('security', 'confirm_dangerous_actions', val)}
          />
        </div>

        <div className="space-y-1">
          <label className="block text-xs font-medium text-slate-300 mb-1">File Delete Threshold</label>
          <Input 
            type="number"
            value={security.max_file_delete_without_confirm}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange('security', 'max_file_delete_without_confirm', parseInt(e.target.value, 10) || 0)}
          />
          <div className="text-xs text-slate-400 mt-1">Maximum number of files that can be deleted before requiring manual confirmation (0 = always confirm).</div>
        </div>
      </div>
    </div>
  );
}
