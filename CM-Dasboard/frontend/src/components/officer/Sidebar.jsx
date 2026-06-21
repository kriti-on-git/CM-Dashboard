import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FileText, Search, MessageSquare, Settings, LogOut, ShieldAlert } from 'lucide-react';

const Sidebar = () => {
  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard, end: true },
    { name: 'Submit Complaint', path: '/submit', icon: FileText, end: false },
    { name: 'Track Status', path: '/track', icon: Search, end: false },
    { name: 'Feedback', path: '/feedback', icon: MessageSquare, end: false },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 text-slate-300 flex flex-col h-full shrink-0 transition-all duration-300 shadow-xl hidden md:flex">
      <div className="h-16 flex items-center px-6 border-b border-white/5">
        <div className="flex items-center gap-3 text-white w-full group cursor-pointer">
          <div className="w-9 h-9 bg-gradient-to-br from-indigo-500 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-shadow">
            <ShieldAlert className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-[18px] tracking-tight group-hover:text-indigo-100 transition-colors">
            GovConnect
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-8 px-4 space-y-1 scrollbar-hide">
        <div className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-4 px-3">
          Overview
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.name}
              to={item.path}
              end={item.end}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-indigo-500/10 text-indigo-400'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`w-5 h-5 transition-colors duration-200 ${isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                  {item.name}
                </>
              )}
            </NavLink>
          );
        })}
      </div>

      <div className="p-4 border-t border-white/5 space-y-1 mb-2">
        <button className="group flex items-center gap-3 px-3 py-2.5 w-full text-left rounded-xl font-medium text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 transition-all duration-200">
          <Settings className="w-5 h-5 text-slate-500 group-hover:text-slate-300 transition-colors" />
          Settings
        </button>
        <button className="group flex items-center gap-3 px-3 py-2.5 w-full text-left rounded-xl font-medium text-slate-400 hover:bg-rose-500/10 hover:text-rose-400 transition-all duration-200">
          <LogOut className="w-5 h-5 text-slate-500 group-hover:text-rose-400 transition-colors" />
          Logout
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
