import React, { useState } from 'react';
import { MainLayout, Input, Switch, Slider, Avatar, ProgressBar, Select, Card } from '@shared/components';
import { HeroCard, BentoGrid, TerminalLog } from '@features/dashboard/components/organisms';

export const DashboardView: React.FC = () => {
  const [switchState, setSwitchState] = useState(false);
  const [sliderValue, setSliderValue] = useState(75);

  return (
    <MainLayout
      breadcrumbPaths={['VOXAGENT', 'Overview']}
    >
      <div className="flex flex-col gap-8">
        
        {/* === COMPONENT TESTING GROUND === */}
        <Card variant="glow" padding="lg" className="border-cyan-500/50 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 blur-[100px] rounded-full pointer-events-none"></div>
          
          <h2 className="text-xl font-headline font-bold text-cyan-400 mb-6 flex items-center gap-2">
            <span className="material-symbols-outlined text-cyan-500">science</span>
            Atomic UI Arsenal Sandbox
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            
            {/* Input Testing */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest border-b border-zinc-800 pb-2">Inputs</h3>
              <Input placeholder="Search skills..." leftIcon="search" />
              <Input placeholder="Enter API Key" type="password" rightIcon="visibility_off" />
              <Input placeholder="Disabled state" disabled />
              <Input placeholder="Error state" error="Invalid signature" leftIcon="error" />
            </div>

            {/* Select & Slider */}
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest border-b border-zinc-800 pb-2">Select & Range</h3>
              <Select label="Routing Tier">
                <option>Tier 1 (Fast)</option>
                <option>Tier 2 (Balanced)</option>
                <option>Tier 3 (Reasoning)</option>
              </Select>
              
              <div className="space-y-2 pt-2">
                 <div className="flex justify-between">
                   <label className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">Master Volume</label>
                   <span className="font-mono text-[10px] text-cyan-400">{sliderValue}%</span>
                 </div>
                 <Slider value={sliderValue} onChange={(e) => setSliderValue(Number(e.target.value))} />
              </div>
            </div>

            {/* Toggles & Graphics */}
            <div className="space-y-6">
              <h3 className="text-sm font-bold text-zinc-300 uppercase tracking-widest border-b border-zinc-800 pb-2">Switches & Graphics</h3>
              
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[#FAFAFA]">Enable Auto-Routing</p>
                  <p className="text-[11px] text-zinc-500 mt-0.5">Use best model automatically.</p>
                </div>
                <Switch checked={switchState} onChange={setSwitchState} size="md" />
              </div>

              <div className="flex items-center gap-4">
                <Avatar size="sm" />
                <Avatar size="md" src="https://i.pravatar.cc/150?u=a042581f4e29026704d" />
                <Avatar size="lg" />
                <Avatar size="xl" src="https://i.pravatar.cc/150?u=default" />
              </div>

              <div className="pt-2">
                <ProgressBar progress={68} label="Token Consumption" valueText="68%" />
              </div>
            </div>
            
          </div>
        </Card>
        {/* === END TESTING GROUND === */}

        <HeroCard />
        <BentoGrid />
        <TerminalLog />
      </div>
    </MainLayout>
  );
};
